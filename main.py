import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np

from bot.classify import classify_board, core_template_labels, load_core_templates
from bot.clicker import click_pair
from bot.capture import capture_board
from bot.debug import RunLogger, create_run_logger, draw_classification_overlay, save_debug_snapshot
from bot.grid import draw_grid_overlay, get_board_roi, get_cell_center
from bot.solver import find_pair
from bot.state import apply_successful_move, init_runtime_state, record_failure, should_full_rescan


class ConfigError(ValueError):
    """Raised when config.json is missing keys or has invalid values."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_config(config: dict[str, Any]) -> None:
    required_types: dict[str, type] = {
        "rows": int,
        "cols": int,
        "board_center_x": int,
        "board_center_y": int,
        "cell_w": int,
        "cell_h": int,
        "gap_x": int,
        "gap_y": int,
        "block_match_threshold": float,
        "background_match_threshold": float,
        "empty_texture_threshold": float,
        "tile_similarity_threshold": float,
        "click_pause_ms": int,
        "post_click_wait_ms": int,
        "settle_wait_ms": int,
        "stability_check_frames": int,
        "stability_pixel_diff_threshold": float,
        "full_rescan_every_n_moves": int,
        "max_consecutive_failures": int,
        "debug_enabled": bool,
        "debug_dir": str,
    }

    missing = [key for key in required_types if key not in config]
    if missing:
        raise ConfigError(f"Missing required config keys: {', '.join(missing)}")

    for key, expected_type in required_types.items():
        value = config[key]
        if expected_type is float:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ConfigError(f"'{key}' must be a number, got {type(value).__name__}")
        elif expected_type is int:
            if not _is_int(value):
                raise ConfigError(f"'{key}' must be an integer, got {type(value).__name__}")
        elif not isinstance(value, expected_type):
            raise ConfigError(f"'{key}' must be {expected_type.__name__}, got {type(value).__name__}")

    if config["rows"] <= 0 or config["cols"] <= 0:
        raise ConfigError("'rows' and 'cols' must be > 0")
    if config["cell_w"] <= 0 or config["cell_h"] <= 0:
        raise ConfigError("'cell_w' and 'cell_h' must be > 0")
    if config["gap_x"] < 0 or config["gap_y"] < 0:
        raise ConfigError("'gap_x' and 'gap_y' must be >= 0")

    if not (0.0 <= float(config["block_match_threshold"]) <= 1.0):
        raise ConfigError("'block_match_threshold' must be between 0.0 and 1.0")
    if not (0.0 <= float(config["background_match_threshold"]) <= 1.0):
        raise ConfigError("'background_match_threshold' must be between 0.0 and 1.0")
    if float(config["empty_texture_threshold"]) < 0.0:
        raise ConfigError("'empty_texture_threshold' must be >= 0.0")
    if not (0.0 <= float(config["tile_similarity_threshold"]) <= 1.0):
        raise ConfigError("'tile_similarity_threshold' must be between 0.0 and 1.0")
    if float(config["stability_pixel_diff_threshold"]) < 0.0:
        raise ConfigError("'stability_pixel_diff_threshold' must be >= 0.0")

    if config["click_pause_ms"] < 0 or config["post_click_wait_ms"] < 0 or config["settle_wait_ms"] < 0:
        raise ConfigError("'click_pause_ms', 'post_click_wait_ms', and 'settle_wait_ms' must be >= 0")
    if config["stability_check_frames"] <= 0:
        raise ConfigError("'stability_check_frames' must be > 0")
    if config["full_rescan_every_n_moves"] <= 0:
        raise ConfigError("'full_rescan_every_n_moves' must be > 0")
    if config["max_consecutive_failures"] <= 0:
        raise ConfigError("'max_consecutive_failures' must be > 0")
    if not str(config["debug_dir"]).strip():
        raise ConfigError("'debug_dir' must be a non-empty string")

    pitch_x = int(config["cell_w"]) + int(config["gap_x"])
    pitch_y = int(config["cell_h"]) + int(config["gap_y"])
    grid_w = int(config["cols"]) * int(config["cell_w"]) + (int(config["cols"]) - 1) * int(config["gap_x"])
    grid_h = int(config["rows"]) * int(config["cell_h"]) + (int(config["rows"]) - 1) * int(config["gap_y"])
    if pitch_x <= 0 or pitch_y <= 0:
        raise ConfigError("Invalid pitch values from cell/gap config")

    board_x, board_y, _, _ = get_board_roi(config)
    if board_x < 0 or board_y < 0:
        raise ConfigError("Derived board ROI has negative origin; update center/rows/cols/cell/gap config")


def load_config(path: str) -> dict:
    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Config JSON parse error at line {exc.lineno}: {exc.msg}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("Config root must be a JSON object")

    _validate_config(raw)
    return raw


def _print_startup_summary(config: dict[str, Any]) -> None:
    roi = get_board_roi(config)
    print("Momo bot booted.")
    print(f"Board ROI: x={roi[0]}, y={roi[1]}, w={roi[2]}, h={roi[3]}")
    print(f"Grid size: {config['rows']}x{config['cols']}")
    print(
        "Grid geometry: "
        f"center=({config['board_center_x']}, {config['board_center_y']}), "
        f"cell={config['cell_w']}x{config['cell_h']}, "
        f"gap=({config['gap_x']},{config['gap_y']})"
    )
    print(f"Debug mode: {'on' if config['debug_enabled'] else 'off'}")
    print(f"Debug dir: {config['debug_dir']}")


def _capture_and_save_overlay(config: dict[str, Any]) -> None:
    frame = capture_board(config)
    overlay = draw_grid_overlay(frame, config)
    out_path = save_debug_snapshot(overlay, "grid_overlay", config)
    print(f"Saved grid overlay: {out_path}")


def _frame_mean_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16))
    return float(np.mean(diff))


def _emit(message: str, logger: RunLogger | None = None) -> None:
    print(message)
    if logger is not None:
        logger.log(message)


def _capture_stable_board(config: dict[str, Any], logger: RunLogger | None = None) -> np.ndarray:
    settle_wait_ms = int(config["settle_wait_ms"])
    if logger is not None:
        logger.log(
            f"capture stable start: settle_wait_ms={settle_wait_ms}, "
            f"stability_check_frames={config['stability_check_frames']}, "
            f"stability_pixel_diff_threshold={config['stability_pixel_diff_threshold']}"
        )
    if settle_wait_ms > 0:
        time.sleep(settle_wait_ms / 1000.0)

    required_stable = int(config["stability_check_frames"])
    diff_threshold = float(config["stability_pixel_diff_threshold"])
    max_attempts = max(6, required_stable * 6)

    prev = capture_board(config)
    if logger is not None:
        logger.save_snapshot(prev, "stability_frame_initial")
    stable_pairs = 0
    for attempt_idx in range(max_attempts):
        time.sleep(0.03)
        curr = capture_board(config)
        diff = _frame_mean_abs_diff(prev, curr)
        if diff <= diff_threshold:
            stable_pairs += 1
            if logger is not None:
                logger.log(
                    f"stability attempt={attempt_idx + 1}/{max_attempts} diff={diff:.3f} "
                    f"stable_pairs={stable_pairs}"
                )
            if stable_pairs >= required_stable:
                if logger is not None:
                    logger.save_snapshot(curr, "stability_frame_final")
                return curr
        else:
            stable_pairs = 0
            if logger is not None:
                logger.log(
                    f"stability attempt={attempt_idx + 1}/{max_attempts} diff={diff:.3f} "
                    "unstable reset"
                )
        prev = curr

    if logger is not None:
        logger.save_snapshot(prev, "stability_frame_fallback")
    return prev


def _classify_once(config: dict[str, Any], template_dir: str, logger: RunLogger | None = None) -> None:
    block_template, background_template = load_core_templates(template_dir)
    template_labels = core_template_labels()
    _emit("Loaded core templates: block.png, background.png", logger=logger)

    frame = _capture_stable_board(config, logger=logger)
    if logger is not None:
        logger.save_snapshot(frame, "classify_frame")
    board, confidence = classify_board(frame, block_template, background_template, config)
    unknown_count = int(np.count_nonzero(board == 0))
    _emit(f"Classification complete. Unknown cells: {unknown_count}/{board.size}", logger=logger)
    _emit("Board matrix:", logger=logger)
    _emit(str(board), logger=logger)

    overlay = draw_classification_overlay(frame, board, confidence, config, template_labels=template_labels)
    out_path = save_debug_snapshot(overlay, "classification_overlay", config)
    _emit(f"Saved classification overlay: {out_path}", logger=logger)
    if logger is not None:
        logger.save_snapshot(overlay, "classification_overlay_run")


def _click_once(
    config: dict[str, Any],
    template_dir: str,
    dry_run: bool = False,
    logger: RunLogger | None = None,
) -> None:
    runtime_state = init_runtime_state(config)
    block_template, background_template = load_core_templates(template_dir)
    template_labels = core_template_labels()
    _emit("Loaded core templates: block.png, background.png", logger=logger)
    _emit(f"Runtime state initialized: {runtime_state}", logger=logger)

    board = np.zeros((int(config["rows"]), int(config["cols"])), dtype=np.int32)
    confidence = np.zeros_like(board, dtype=np.float32)
    max_recovery_attempts = 2
    for attempt in range(max_recovery_attempts):
        frame = _capture_stable_board(config, logger=logger)
        if logger is not None:
            logger.save_snapshot(frame, f"click_frame_attempt_{attempt + 1}")
        board, confidence = classify_board(frame, block_template, background_template, config)
        unknown_count = int(np.count_nonzero(board == 0))
        _emit(
            f"Classification complete (attempt {attempt + 1}/{max_recovery_attempts}). "
            f"Unknown cells: {unknown_count}/{board.size}",
            logger=logger,
        )
        if logger is not None:
            overlay = draw_classification_overlay(
                frame,
                board,
                confidence,
                config,
                template_labels=template_labels,
            )
            logger.save_snapshot(overlay, f"click_classification_overlay_attempt_{attempt + 1}")
            logger.log(f"classification board attempt={attempt + 1}:\n{board}")

        if should_full_rescan(runtime_state, confidence, config):
            reason = runtime_state.get("last_rescan_reason")
            _emit(f"Full rescan trigger: {reason}", logger=logger)
            if attempt < max_recovery_attempts - 1:
                continue
            _emit("Proceeding with latest frame after final recovery attempt.", logger=logger)
        break

    pair = find_pair(board)
    if pair is None:
        record_failure(runtime_state)
        _emit("No valid pair found; recorded failure.", logger=logger)
        _emit(f"Runtime state: {runtime_state}", logger=logger)
        if runtime_state["consecutive_failures"] >= int(config["max_consecutive_failures"]):
            _emit(
                "Stop trigger reached: consecutive_failures >= max_consecutive_failures.",
                logger=logger,
            )
        return

    _emit(f"Selected pair: {pair}", logger=logger)
    if logger is not None:
        first, second = pair
        first_xy = get_cell_center(first[0], first[1], config)
        second_xy = get_cell_center(second[0], second[1], config)
        logger.log(f"click plan: first={first} -> {first_xy}, second={second} -> {second_xy}, dry_run={dry_run}")
    try:
        click_pair(pair, config, dry_run=dry_run)
    except Exception:
        record_failure(runtime_state)
        _emit("Click execution failed; recorded failure.", logger=logger)
        _emit(f"Runtime state: {runtime_state}", logger=logger)
        if runtime_state["consecutive_failures"] >= int(config["max_consecutive_failures"]):
            _emit(
                "Stop trigger reached: consecutive_failures >= max_consecutive_failures.",
                logger=logger,
            )
        raise

    apply_successful_move(runtime_state, pair)
    _emit(f"Runtime state: {runtime_state}", logger=logger)
    if dry_run:
        _emit("Dry run complete. No mouse clicks were executed.", logger=logger)
    else:
        _emit("Clicked selected pair.", logger=logger)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Momo iPhone mirroring bot")
    parser.add_argument(
        "--capture-once",
        action="store_true",
        help="Capture board ROI once and save a grid overlay image to debug_dir.",
    )
    parser.add_argument(
        "--classify-once",
        action="store_true",
        help="Capture once, classify all cells, and save labeled classification overlay.",
    )
    parser.add_argument(
        "--click-once",
        action="store_true",
        help="Capture/classify/solve once and click one valid pair if found.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print click coordinates without executing real clicks.",
    )
    parser.add_argument(
        "--template-dir",
        default="templates",
        help="Template directory path (default: templates).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    project_root = Path(__file__).resolve().parent
    config_path = project_root / "config.json"

    try:
        config = load_config(str(config_path))
        _print_startup_summary(config)
        run_logger: RunLogger | None = None
        if bool(config.get("debug_enabled")) and (args.capture_once or args.classify_once or args.click_once):
            run_logger = create_run_logger(config, run_name="main")
            _emit(f"Run diagnostics directory: {run_logger.run_dir}", logger=run_logger)
            run_logger.log(
                f"flags capture_once={args.capture_once} classify_once={args.classify_once} "
                f"click_once={args.click_once} dry_run={args.dry_run}"
            )
        if args.capture_once:
            _capture_and_save_overlay(config)
            if run_logger is not None:
                run_logger.log("capture-once completed")
        if args.classify_once:
            template_dir = str((project_root / args.template_dir).resolve())
            _classify_once(config, template_dir, logger=run_logger)
        if args.click_once:
            template_dir = str((project_root / args.template_dir).resolve())
            _click_once(config, template_dir, dry_run=args.dry_run, logger=run_logger)
        return 0
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - depends on OS/screen permissions
        print(f"Runtime error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

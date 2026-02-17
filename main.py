import argparse
import json
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np

from bot.classify import classify_board, load_templates_with_labels
from bot.capture import capture_board
from bot.debug import draw_classification_overlay, save_debug_snapshot
from bot.grid import draw_grid_overlay, get_board_roi


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
        "match_threshold": float,
        "min_margin_to_second_best": float,
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

    if not (0.0 <= float(config["match_threshold"]) <= 1.0):
        raise ConfigError("'match_threshold' must be between 0.0 and 1.0")
    if not (0.0 <= float(config["min_margin_to_second_best"]) <= 1.0):
        raise ConfigError("'min_margin_to_second_best' must be between 0.0 and 1.0")
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


def _capture_stable_board(config: dict[str, Any]) -> np.ndarray:
    settle_wait_ms = int(config["settle_wait_ms"])
    if settle_wait_ms > 0:
        time.sleep(settle_wait_ms / 1000.0)

    required_stable = int(config["stability_check_frames"])
    diff_threshold = float(config["stability_pixel_diff_threshold"])
    max_attempts = max(6, required_stable * 6)

    prev = capture_board(config)
    stable_pairs = 0
    for _ in range(max_attempts):
        time.sleep(0.03)
        curr = capture_board(config)
        diff = _frame_mean_abs_diff(prev, curr)
        if diff <= diff_threshold:
            stable_pairs += 1
            if stable_pairs >= required_stable:
                return curr
        else:
            stable_pairs = 0
        prev = curr

    return prev


def _classify_once(config: dict[str, Any], template_dir: str) -> None:
    templates, template_labels = load_templates_with_labels(template_dir)
    print(f"Loaded templates: {len(templates)} from {template_dir}")

    frame = _capture_stable_board(config)
    board, confidence = classify_board(frame, templates, config)
    unknown_count = int(np.count_nonzero(board == 0))
    print(f"Classification complete. Unknown cells: {unknown_count}/{board.size}")
    print("Board matrix:")
    print(board)

    overlay = draw_classification_overlay(frame, board, confidence, config, template_labels=template_labels)
    out_path = save_debug_snapshot(overlay, "classification_overlay", config)
    print(f"Saved classification overlay: {out_path}")


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
        if args.capture_once:
            _capture_and_save_overlay(config)
        if args.classify_once:
            template_dir = str((project_root / args.template_dir).resolve())
            _classify_once(config, template_dir)
        return 0
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - depends on OS/screen permissions
        print(f"Runtime error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

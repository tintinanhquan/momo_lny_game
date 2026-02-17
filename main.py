import argparse
import json
from pathlib import Path
import sys
from typing import Any

from bot.capture import capture_board
from bot.debug import save_debug_snapshot
from bot.grid import draw_grid_overlay


class ConfigError(ValueError):
    """Raised when config.json is missing keys or has invalid values."""


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_config(config: dict[str, Any]) -> None:
    required_types: dict[str, type] = {
        "board_x": int,
        "board_y": int,
        "board_w": int,
        "board_h": int,
        "rows": int,
        "cols": int,
        "match_threshold": float,
        "min_margin_to_second_best": float,
        "click_pause_ms": int,
        "post_click_wait_ms": int,
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

    if config["board_x"] < 0 or config["board_y"] < 0:
        raise ConfigError("'board_x' and 'board_y' must be >= 0")
    if config["board_w"] <= 0 or config["board_h"] <= 0:
        raise ConfigError("'board_w' and 'board_h' must be > 0")
    if config["rows"] <= 0 or config["cols"] <= 0:
        raise ConfigError("'rows' and 'cols' must be > 0")

    if not (0.0 <= float(config["match_threshold"]) <= 1.0):
        raise ConfigError("'match_threshold' must be between 0.0 and 1.0")
    if not (0.0 <= float(config["min_margin_to_second_best"]) <= 1.0):
        raise ConfigError("'min_margin_to_second_best' must be between 0.0 and 1.0")

    if config["click_pause_ms"] < 0 or config["post_click_wait_ms"] < 0:
        raise ConfigError("'click_pause_ms' and 'post_click_wait_ms' must be >= 0")
    if config["full_rescan_every_n_moves"] <= 0:
        raise ConfigError("'full_rescan_every_n_moves' must be > 0")
    if config["max_consecutive_failures"] <= 0:
        raise ConfigError("'max_consecutive_failures' must be > 0")
    if not str(config["debug_dir"]).strip():
        raise ConfigError("'debug_dir' must be a non-empty string")


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
    roi = (config["board_x"], config["board_y"], config["board_w"], config["board_h"])
    print("Momo bot booted.")
    print(f"Board ROI: x={roi[0]}, y={roi[1]}, w={roi[2]}, h={roi[3]}")
    print(f"Grid size: {config['rows']}x{config['cols']}")
    print(f"Debug mode: {'on' if config['debug_enabled'] else 'off'}")
    print(f"Debug dir: {config['debug_dir']}")


def _capture_and_save_overlay(config: dict[str, Any]) -> None:
    frame = capture_board(config)
    overlay = draw_grid_overlay(frame, config)
    out_path = save_debug_snapshot(overlay, "grid_overlay", config)
    print(f"Saved grid overlay: {out_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Momo iPhone mirroring bot")
    parser.add_argument(
        "--capture-once",
        action="store_true",
        help="Capture board ROI once and save a grid overlay image to debug_dir.",
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
        return 0
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - depends on OS/screen permissions
        print(f"Runtime error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

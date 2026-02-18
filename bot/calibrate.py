from __future__ import annotations

import json
import sys
from typing import Any

try:
    import pyautogui
except ModuleNotFoundError as exc:
    pyautogui = None  # type: ignore[assignment]
    _PYAUTOGUI_IMPORT_ERROR = exc
else:
    _PYAUTOGUI_IMPORT_ERROR = None


def _require_pyautogui() -> Any:
    """Return pyautogui or raise with setup instructions."""
    if pyautogui is None:
        raise ModuleNotFoundError(
            "Missing dependency 'pyautogui'. Install project dependencies with "
            "'uv sync' (recommended) or 'python -m pip install pyautogui'."
        ) from _PYAUTOGUI_IMPORT_ERROR
    return pyautogui


def _capture_point(prompt: str) -> tuple[int, int]:
    mouse = _require_pyautogui()
    print(prompt)
    input("Press Enter to capture current mouse position...")
    pos = mouse.position()
    print(f"Captured: ({pos.x}, {pos.y})")
    return int(pos.x), int(pos.y)


def calibrate_board() -> dict[str, int]:
    """Capture top-left and bottom-right board corners from mouse position."""
    print("ROI calibration")
    print("- Keep the game window fixed during calibration.")
    print("- Move mouse to TOP-LEFT corner of playable board.")
    top_left = _capture_point("")
    print("- Move mouse to BOTTOM-RIGHT corner of playable board.")
    bottom_right = _capture_point("")

    x1, y1 = top_left
    x2, y2 = bottom_right
    board_x = min(x1, x2)
    board_y = min(y1, y2)
    board_w = abs(x2 - x1)
    board_h = abs(y2 - y1)

    if board_w <= 0 or board_h <= 0:
        raise ValueError("Invalid ROI: width/height must be > 0.")

    return {
        "board_x": board_x,
        "board_y": board_y,
        "board_w": board_w,
        "board_h": board_h,
    }


def format_config_snippet(roi: dict[str, Any]) -> str:
    return json.dumps(roi, indent=2)


def run_calibration() -> None:
    _require_pyautogui()
    roi = calibrate_board()
    print("\nPaste these values into config.json:")
    print(format_config_snippet(roi))


if __name__ == "__main__":
    try:
        run_calibration()
    except ModuleNotFoundError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

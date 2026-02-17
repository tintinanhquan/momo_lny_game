from __future__ import annotations

import json
from typing import Any

import pyautogui


def _capture_point(prompt: str) -> tuple[int, int]:
    print(prompt)
    input("Press Enter to capture current mouse position...")
    pos = pyautogui.position()
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
    roi = calibrate_board()
    print("\nPaste these values into config.json:")
    print(format_config_snippet(roi))

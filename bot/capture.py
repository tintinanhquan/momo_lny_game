from __future__ import annotations

from typing import Any

import cv2
import mss
import numpy as np

from bot.grid import get_board_roi

Frame = np.ndarray


def capture_board(config: dict[str, Any]) -> Frame:
    """Capture board ROI using geometry-derived absolute coordinates."""
    board_x, board_y, board_w, board_h = get_board_roi(config)
    monitor = {
        "left": int(board_x),
        "top": int(board_y),
        "width": int(board_w),
        "height": int(board_h),
    }
    with mss.mss() as sct:
        raw = sct.grab(monitor)

    frame_bgra = np.array(raw)
    return cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)

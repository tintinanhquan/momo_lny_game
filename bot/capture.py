from __future__ import annotations

from typing import Any

import cv2
import mss
import numpy as np

Frame = np.ndarray


def capture_board(config: dict[str, Any]) -> Frame:
    """Capture board ROI using absolute screen coordinates from config."""
    monitor = {
        "left": int(config["board_x"]),
        "top": int(config["board_y"]),
        "width": int(config["board_w"]),
        "height": int(config["board_h"]),
    }
    with mss.mss() as sct:
        raw = sct.grab(monitor)

    frame_bgra = np.array(raw)
    return cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)

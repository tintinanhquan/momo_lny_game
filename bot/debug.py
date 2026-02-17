from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

Frame = np.ndarray


def save_debug_snapshot(frame: Frame, name: str, config: dict[str, Any]) -> Path:
    """Save a frame to configured debug_dir with timestamp."""
    debug_dir = Path(config["debug_dir"])
    debug_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_name = name.replace(" ", "_")
    out_path = debug_dir / f"{safe_name}_{timestamp}.png"

    ok = cv2.imwrite(str(out_path), frame)
    if not ok:
        raise RuntimeError(f"Failed to write debug snapshot to {out_path}")
    return out_path

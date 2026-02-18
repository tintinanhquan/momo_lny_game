from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from bot.grid import draw_grid_overlay, get_cell_center_in_frame

Frame = np.ndarray


class RunLogger:
    """Write per-run diagnostic logs and snapshots."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.run_dir / "events.log"

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{timestamp} | {message}\n")

    def save_snapshot(self, frame: Frame, name: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_name = name.replace(" ", "_")
        out_path = self.run_dir / f"{safe_name}_{timestamp}.png"
        ok = cv2.imwrite(str(out_path), frame)
        if not ok:
            raise RuntimeError(f"Failed to write run snapshot to {out_path}")
        self.log(f"snapshot saved: {out_path}")
        return out_path


def create_run_logger(config: dict[str, Any], run_name: str = "run") -> RunLogger:
    """Create a timestamped per-run logger under debug_dir/runs."""
    debug_dir = Path(config["debug_dir"])
    run_root = debug_dir / "runs"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = run_root / f"{run_name}_{timestamp}"
    logger = RunLogger(run_dir)
    logger.log("run logger initialized")
    return logger


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


def draw_classification_overlay(
    frame: Frame,
    board: np.ndarray,
    confidence: np.ndarray,
    config: dict[str, Any],
    template_labels: dict[int, str] | None = None,
) -> Frame:
    """Render tile IDs/labels and confidence values over the grid."""
    out = draw_grid_overlay(frame, config)
    rows = int(config["rows"])
    cols = int(config["cols"])
    labels = template_labels or {}

    for row in range(rows):
        for col in range(cols):
            tile_id = int(board[row, col])
            score = float(confidence[row, col])
            center_x, center_y = get_cell_center_in_frame(row, col, out, config)

            tile_label = labels.get(tile_id)
            label = f"{tile_id}:{score:.2f}" if not tile_label else f"{tile_id}/{tile_label}:{score:.2f}"
            color = (255, 255, 255) if tile_id != 0 else (0, 165, 255)
            cv2.putText(
                out,
                label,
                (max(0, center_x - 20), max(12, center_y - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.32,
                (0, 0, 0),
                2,
                cv2.LINE_AA,
            )
            cv2.putText(
                out,
                label,
                (max(0, center_x - 20), max(12, center_y - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.32,
                color,
                1,
                cv2.LINE_AA,
            )

    return out

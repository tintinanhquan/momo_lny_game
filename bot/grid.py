from __future__ import annotations

from typing import Any

import cv2
import numpy as np

Frame = np.ndarray


def _require_valid_cell(row: int, col: int, rows: int, cols: int) -> None:
    if not (0 <= row < rows):
        raise ValueError(f"row {row} out of range [0, {rows - 1}]")
    if not (0 <= col < cols):
        raise ValueError(f"col {col} out of range [0, {cols - 1}]")


def get_board_roi(config: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return absolute (x, y, w, h) for configured board grid bounds."""
    rows = int(config["rows"])
    cols = int(config["cols"])
    cell_w = int(config["cell_w"])
    cell_h = int(config["cell_h"])
    gap_x = int(config["gap_x"])
    gap_y = int(config["gap_y"])
    center_x = int(config["board_center_x"])
    center_y = int(config["board_center_y"])

    grid_w = (cols * cell_w) + ((cols - 1) * gap_x)
    grid_h = (rows * cell_h) + ((rows - 1) * gap_y)
    left = center_x - (grid_w // 2)
    top = center_y - (grid_h // 2)
    return left, top, grid_w, grid_h


def _cell_bounds_absolute(
    row: int,
    col: int,
    config: dict[str, Any],
) -> tuple[int, int, int, int]:
    rows = int(config["rows"])
    cols = int(config["cols"])
    _require_valid_cell(row, col, rows, cols)

    cell_w = int(config["cell_w"])
    cell_h = int(config["cell_h"])
    gap_x = int(config["gap_x"])
    gap_y = int(config["gap_y"])
    left, top, _, _ = get_board_roi(config)

    pitch_x = cell_w + gap_x
    pitch_y = cell_h + gap_y
    x0 = left + (col * pitch_x)
    y0 = top + (row * pitch_y)
    return x0, y0, cell_w, cell_h


def get_cell_rect(row: int, col: int, config: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return absolute screen-space (x, y, w, h) for one cell."""
    return _cell_bounds_absolute(row, col, config)


def get_cell_center(row: int, col: int, config: dict[str, Any]) -> tuple[int, int]:
    """Return absolute screen-space center (x, y) for one cell."""
    x, y, w, h = get_cell_rect(row, col, config)
    return x + (w // 2), y + (h // 2)


def get_cell_rect_in_frame(
    row: int,
    col: int,
    frame: Frame,
    config: dict[str, Any],
) -> tuple[int, int, int, int]:
    """Return ROI-local (x, y, w, h) for one cell in a captured frame."""
    _ = frame  # frame is kept for API consistency; mapping is config-driven.
    abs_x, abs_y, w, h = get_cell_rect(row, col, config)
    board_x, board_y, _, _ = get_board_roi(config)
    return abs_x - board_x, abs_y - board_y, w, h


def get_cell_center_in_frame(
    row: int,
    col: int,
    frame: Frame,
    config: dict[str, Any],
) -> tuple[int, int]:
    """Return ROI-local center (x, y) for one cell in a captured frame."""
    x, y, w, h = get_cell_rect_in_frame(row, col, frame, config)
    return x + (w // 2), y + (h // 2)


def crop_cell(
    frame: Frame,
    row: int,
    col: int,
    config: dict[str, Any],
    inset_ratio: float = 0.12,
) -> Frame:
    """
    Crop one cell from a board ROI frame.

    inset_ratio removes a small border from each cell to reduce grid-line noise.
    """
    x, y, w, h = get_cell_rect_in_frame(row, col, frame, config)
    if w <= 0 or h <= 0:
        raise ValueError(f"Invalid cell size for ({row}, {col}): w={w}, h={h}")

    inset_x = max(0, int(round(w * inset_ratio)))
    inset_y = max(0, int(round(h * inset_ratio)))

    x0 = min(frame.shape[1] - 1, x + inset_x)
    y0 = min(frame.shape[0] - 1, y + inset_y)
    x1 = max(x0 + 1, min(frame.shape[1], x + w - inset_x))
    y1 = max(y0 + 1, min(frame.shape[0], y + h - inset_y))
    return frame[y0:y1, x0:x1].copy()


def draw_grid_overlay(frame: Frame, config: dict[str, Any]) -> Frame:
    """Draw grid lines and center points on a board ROI frame."""
    out = frame.copy()
    rows = int(config["rows"])
    cols = int(config["cols"])
    height, width = out.shape[:2]

    line_color = (0, 255, 0)
    center_color = (0, 0, 255)

    for r in range(rows):
        for c in range(cols):
            x0, y0, w, h = get_cell_rect_in_frame(r, c, out, config)
            center_x = x0 + (w // 2)
            center_y = y0 + (h // 2)
            cv2.rectangle(out, (x0, y0), (x0 + w, y0 + h), line_color, 1)
            cv2.circle(out, (center_x, center_y), 2, center_color, -1)

    return out

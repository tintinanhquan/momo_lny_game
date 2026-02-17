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


def _cell_bounds_relative(
    row: int,
    col: int,
    rows: int,
    cols: int,
    board_w: int,
    board_h: int,
) -> tuple[int, int, int, int]:
    _require_valid_cell(row, col, rows, cols)

    x0 = int(round((col * board_w) / cols))
    x1 = int(round(((col + 1) * board_w) / cols))
    y0 = int(round((row * board_h) / rows))
    y1 = int(round(((row + 1) * board_h) / rows))
    return x0, y0, x1 - x0, y1 - y0


def get_cell_rect(row: int, col: int, config: dict[str, Any]) -> tuple[int, int, int, int]:
    """Return absolute screen-space (x, y, w, h) for one cell."""
    rows = int(config["rows"])
    cols = int(config["cols"])
    board_w = int(config["board_w"])
    board_h = int(config["board_h"])
    board_x = int(config["board_x"])
    board_y = int(config["board_y"])

    rel_x, rel_y, w, h = _cell_bounds_relative(row, col, rows, cols, board_w, board_h)
    return board_x + rel_x, board_y + rel_y, w, h


def get_cell_center(row: int, col: int, config: dict[str, Any]) -> tuple[int, int]:
    """Return absolute screen-space center (x, y) for one cell."""
    x, y, w, h = get_cell_rect(row, col, config)
    return x + (w // 2), y + (h // 2)


def draw_grid_overlay(frame: Frame, config: dict[str, Any]) -> Frame:
    """Draw grid lines and center points on a board ROI frame."""
    out = frame.copy()
    rows = int(config["rows"])
    cols = int(config["cols"])
    height, width = out.shape[:2]

    line_color = (0, 255, 0)
    center_color = (0, 0, 255)

    for r in range(rows + 1):
        y = int(round((r * height) / rows))
        cv2.line(out, (0, y), (width - 1, y), line_color, 1)

    for c in range(cols + 1):
        x = int(round((c * width) / cols))
        cv2.line(out, (x, 0), (x, height - 1), line_color, 1)

    for r in range(rows):
        for c in range(cols):
            x0, y0, w, h = _cell_bounds_relative(r, c, rows, cols, width, height)
            center_x = x0 + (w // 2)
            center_y = y0 + (h // 2)
            cv2.circle(out, (center_x, center_y), 2, center_color, -1)

    return out

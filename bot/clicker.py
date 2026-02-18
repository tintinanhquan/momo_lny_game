from __future__ import annotations

import time
from typing import Any

import pyautogui

from bot.grid import get_cell_center

Cell = tuple[int, int]
Pair = tuple[Cell, Cell]


def _validate_cell(cell: Cell, config: dict[str, Any]) -> None:
    row, col = cell
    rows = int(config["rows"])
    cols = int(config["cols"])
    if not (0 <= row < rows):
        raise ValueError(f"row {row} out of range [0, {rows - 1}]")
    if not (0 <= col < cols):
        raise ValueError(f"col {col} out of range [0, {cols - 1}]")


def click_cell(cell: Cell, config: dict[str, Any], dry_run: bool = False) -> None:
    """Click one cell using absolute screen coordinates."""
    _validate_cell(cell, config)
    row, col = cell
    x, y = get_cell_center(row, col, config)

    pause_seconds = int(config["click_pause_ms"]) / 1000.0
    pyautogui.PAUSE = pause_seconds

    if dry_run:
        print(f"[dry-run] click_cell row={row} col={col} -> x={x} y={y}")
        return

    pyautogui.click(x=x, y=y)


def click_pair(pair: Pair, config: dict[str, Any], dry_run: bool = False) -> None:
    """Click two cells in sequence and wait after the second click."""
    first, second = pair
    click_cell(first, config, dry_run=dry_run)
    click_cell(second, config, dry_run=dry_run)

    post_click_wait_seconds = int(config["post_click_wait_ms"]) / 1000.0
    time.sleep(post_click_wait_seconds)

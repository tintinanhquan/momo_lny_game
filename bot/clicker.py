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


def click_cell(cell: Cell, config: dict[str, Any], dry_run: bool = False, hold_ms: int | None = None) -> None:
    """Click one cell using absolute screen coordinates."""
    _validate_cell(cell, config)
    row, col = cell
    x, y = get_cell_center(row, col, config)

    pause_seconds = int(config["click_pause_ms"]) / 1000.0
    pyautogui.PAUSE = pause_seconds

    effective_hold_ms = int(config.get("tap_hold_ms", 0)) if hold_ms is None else int(hold_ms)
    hold_seconds = max(0.0, effective_hold_ms / 1000.0)

    if dry_run:
        print(f"[dry-run] click_cell row={row} col={col} -> x={x} y={y} hold_ms={effective_hold_ms}")
        return

    if hold_seconds > 0:
        pyautogui.mouseDown(x=x, y=y)
        time.sleep(hold_seconds)
        pyautogui.mouseUp(x=x, y=y)
        return

    pyautogui.click(x=x, y=y)


def click_screen_middle(config: dict[str, Any], dry_run: bool = False) -> None:
    """Click configured screen middle to dismiss transient overlays/popups."""
    x = int(config["board_center_x"])
    y = int(config["board_center_y"])
    pause_seconds = int(config["click_pause_ms"]) / 1000.0
    pyautogui.PAUSE = pause_seconds

    if dry_run:
        print(f"[dry-run] click_screen_middle -> x={x} y={y}")
        return

    pyautogui.click(x=x, y=y)


def click_pair(pair: Pair, config: dict[str, Any], dry_run: bool = False) -> None:
    """Click two cells in sequence and wait after the second click."""
    first, second = pair
    first_tile_hold_ms = int(config.get("first_tile_tap_hold_ms", config.get("tap_hold_ms", 0)))
    click_cell(first, config, dry_run=dry_run, hold_ms=first_tile_hold_ms)
    if bool(config.get("double_click_first_tile", False)):
        first_click_repeat_wait_seconds = max(0.0, float(config.get("first_tile_repeat_wait_ms", 0)) / 1000.0)
        if first_click_repeat_wait_seconds > 0:
            time.sleep(first_click_repeat_wait_seconds)
        click_cell(first, config, dry_run=dry_run, hold_ms=first_tile_hold_ms)
    inter_click_wait_seconds = max(0.0, float(config.get("inter_click_wait_ms", 0)) / 1000.0)
    if inter_click_wait_seconds > 0:
        time.sleep(inter_click_wait_seconds)
    click_cell(second, config, dry_run=dry_run)

    post_click_wait_seconds = int(config["post_click_wait_ms"]) / 1000.0
    time.sleep(post_click_wait_seconds)

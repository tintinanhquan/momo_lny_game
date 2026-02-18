import json
from pathlib import Path
import sys

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bot.debug import create_run_logger, save_debug_snapshot
from bot.grid import draw_grid_overlay, get_cell_center, get_cell_rect
from main import ConfigError, load_config


def test_config_exists_and_has_board_shape() -> None:
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["rows"] > 0
    assert config["cols"] > 0


def test_load_config_validates_missing_key(tmp_path: Path) -> None:
    bad_config = {
        "rows": 10,
        "cols": 7,
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_config), encoding="utf-8")

    with pytest.raises(ConfigError, match="Missing required config keys"):
        load_config(str(path))


def test_grid_geometry_and_overlay_shape() -> None:
    config = {
        "rows": 5,
        "cols": 4,
        "board_center_x": 110,
        "board_center_y": 70,
        "cell_w": 44,
        "cell_h": 18,
        "gap_x": 8,
        "gap_y": 2,
    }
    rect = get_cell_rect(2, 1, config)
    center = get_cell_center(2, 1, config)
    assert rect[2] > 0 and rect[3] > 0
    assert rect[0] <= center[0] <= rect[0] + rect[2]
    assert rect[1] <= center[1] <= rect[1] + rect[3]

    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    overlay = draw_grid_overlay(frame, config)
    assert overlay.shape == frame.shape


def test_save_debug_snapshot_writes_file(tmp_path: Path) -> None:
    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    config = {"debug_dir": str(tmp_path)}
    out = save_debug_snapshot(frame, "test_overlay", config)
    assert out.exists()


def test_create_run_logger_writes_events_and_snapshots(tmp_path: Path) -> None:
    config = {"debug_dir": str(tmp_path)}
    logger = create_run_logger(config, run_name="smoke")
    logger.log("hello")
    frame = np.zeros((8, 8, 3), dtype=np.uint8)
    snap = logger.save_snapshot(frame, "tiny")

    assert logger.run_dir.exists()
    assert logger.log_path.exists()
    assert "hello" in logger.log_path.read_text(encoding="utf-8")
    assert snap.exists()

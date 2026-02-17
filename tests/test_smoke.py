import json
from pathlib import Path
import sys

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bot.debug import save_debug_snapshot
from bot.grid import draw_grid_overlay, get_cell_center, get_cell_rect
from main import ConfigError, load_config


def test_config_exists_and_has_board_shape() -> None:
    config_path = Path(__file__).resolve().parents[1] / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["rows"] > 0
    assert config["cols"] > 0


def test_load_config_validates_missing_key(tmp_path: Path) -> None:
    bad_config = {
        "board_x": 0,
        "board_y": 0,
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad_config), encoding="utf-8")

    with pytest.raises(ConfigError, match="Missing required config keys"):
        load_config(str(path))


def test_grid_geometry_and_overlay_shape() -> None:
    config = {
        "board_x": 10,
        "board_y": 20,
        "board_w": 200,
        "board_h": 100,
        "rows": 5,
        "cols": 4,
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

from pathlib import Path
import sys

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bot.classify import classify_board, core_template_labels, load_core_templates


def _write_template(path: Path, bgr: tuple[int, int, int]) -> None:
    image = np.full((24, 24, 3), bgr, dtype=np.uint8)
    ok = cv2.imwrite(str(path), image)
    if not ok:
        raise RuntimeError(f"failed to write template {path}")


def test_load_core_templates_and_labels(tmp_path: Path) -> None:
    _write_template(tmp_path / "block.png", (30, 30, 30))
    _write_template(tmp_path / "background.png", (0, 0, 0))

    block_template, background_template = load_core_templates(str(tmp_path))
    labels = core_template_labels()

    assert block_template.shape == (24, 24, 3)
    assert background_template.shape == (24, 24, 3)
    assert labels[-1] == "block"
    assert labels[0] == "background"


def test_classify_board_two_template_pipeline(tmp_path: Path) -> None:
    _write_template(tmp_path / "block.png", (30, 30, 30))
    _write_template(tmp_path / "background.png", (0, 0, 0))
    block_template, background_template = load_core_templates(str(tmp_path))

    rows, cols = 2, 2
    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    frame[0:20, 0:20] = (240, 240, 240)  # tile A
    frame[0:20, 20:40] = (240, 240, 240)  # tile A
    frame[20:40, 0:20] = (30, 30, 30)  # block
    frame[20:40, 20:40] = (0, 0, 0)  # background

    config = {
        "rows": rows,
        "cols": cols,
        "board_center_x": 20,
        "board_center_y": 20,
        "cell_w": 20,
        "cell_h": 20,
        "gap_x": 0,
        "gap_y": 0,
        "block_match_threshold": 0.8,
        "background_match_threshold": 0.8,
        "empty_texture_threshold": 5.0,
        "tile_similarity_threshold": 0.7,
    }
    board, confidence = classify_board(frame, block_template, background_template, config)

    assert board.shape == (rows, cols)
    assert confidence.shape == (rows, cols)
    assert board.dtype == np.int32
    assert confidence.dtype == np.float32
    assert board[1, 0] == -1
    assert board[1, 1] == 0
    assert board[0, 0] > 0
    assert board[0, 1] == board[0, 0]


def test_similarity_grouping_marks_odd_group_as_ambiguous(tmp_path: Path) -> None:
    _write_template(tmp_path / "block.png", (30, 30, 30))
    _write_template(tmp_path / "background.png", (0, 0, 0))
    block_template, background_template = load_core_templates(str(tmp_path))

    rows, cols = 2, 2
    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    frame[0:20, 0:20] = (240, 240, 240)  # tile A
    frame[0:20, 20:40] = (240, 240, 240)  # tile A
    frame[20:40, 0:20] = (240, 240, 240)  # tile A (odd count)
    frame[20:40, 20:40] = (0, 0, 0)  # background

    config = {
        "rows": rows,
        "cols": cols,
        "board_center_x": 20,
        "board_center_y": 20,
        "cell_w": 20,
        "cell_h": 20,
        "gap_x": 0,
        "gap_y": 0,
        "block_match_threshold": 0.8,
        "background_match_threshold": 0.8,
        "empty_texture_threshold": 5.0,
        "tile_similarity_threshold": 0.7,
    }

    board, _ = classify_board(frame, block_template, background_template, config)
    assert board[1, 1] == 0
    assert board[0, 0] == 0
    assert board[0, 1] == 0
    assert board[1, 0] == 0

from pathlib import Path
import sys

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bot.classify import classify_board, load_templates_with_labels


def _write_template(path: Path, bgr: tuple[int, int, int]) -> None:
    image = np.full((24, 24, 3), bgr, dtype=np.uint8)
    ok = cv2.imwrite(str(path), image)
    if not ok:
        raise RuntimeError(f"failed to write template {path}")


def test_load_templates_and_classify_board_shapes(tmp_path: Path) -> None:
    _write_template(tmp_path / "block.png", (30, 30, 30))
    _write_template(tmp_path / "beer_blue.png", (10, 20, 220))
    _write_template(tmp_path / "hat.png", (10, 220, 20))

    templates, labels = load_templates_with_labels(str(tmp_path))
    assert -1 in templates
    assert 1 in templates
    assert 2 in templates
    assert labels[-1] == "block"
    assert labels[1] == "beer_blue"
    assert labels[2] == "hat"

    rows, cols = 2, 2
    frame = np.zeros((40, 40, 3), dtype=np.uint8)
    frame[0:20, 0:20] = (10, 20, 220)   # beer_blue
    frame[0:20, 20:40] = (10, 220, 20)  # hat
    frame[20:40, 0:20] = (30, 30, 30)   # block
    frame[20:40, 20:40] = (0, 0, 0)     # likely unknown

    config = {
        "rows": rows,
        "cols": cols,
        "board_center_x": 20,
        "board_center_y": 20,
        "cell_w": 20,
        "cell_h": 20,
        "gap_x": 0,
        "gap_y": 0,
        "match_threshold": 0.8,
        "min_margin_to_second_best": 0.02,
    }
    board, confidence = classify_board(frame, templates, config)

    assert board.shape == (rows, cols)
    assert confidence.shape == (rows, cols)
    assert board.dtype == np.int32
    assert confidence.dtype == np.float32

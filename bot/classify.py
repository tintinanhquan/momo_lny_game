from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from bot.grid import crop_cell

Board = np.ndarray
ConfidenceMap = np.ndarray
Frame = np.ndarray

TemplateLabelMap = dict[int, str]


def load_templates_with_labels(template_dir: str) -> tuple[dict[int, Frame], TemplateLabelMap]:
    """
    Load tile templates from disk.

    Naming:
    - block.png -> -1
    - all other filenames -> positive tile IDs by alphabetical order
    """
    root = Path(template_dir)
    if not root.exists():
        raise FileNotFoundError(f"Template directory not found: {root}")
    if not root.is_dir():
        raise ValueError(f"Template path is not a directory: {root}")

    templates: dict[int, Frame] = {}
    labels: TemplateLabelMap = {}
    image_files = [
        p
        for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    if not image_files:
        raise ValueError(f"No image templates found in {root}")

    sorted_files = sorted(image_files, key=lambda p: p.stem.lower())
    next_id = 1
    for path in sorted_files:
        label = path.stem.lower()
        tile_id = -1 if label == "block" else next_id

        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"Failed to read template image: {path}")
        templates[tile_id] = img
        labels[tile_id] = label
        if tile_id != -1:
            next_id += 1

    if not templates:
        raise ValueError(
            f"No templates loaded from {root}. Expected block.png and tile images."
        )

    return dict(sorted(templates.items(), key=lambda item: item[0])), labels


def load_templates(template_dir: str) -> dict[int, Frame]:
    templates, _ = load_templates_with_labels(template_dir)
    return templates


def _prepare_for_match(image: Frame, size: tuple[int, int] = (32, 32)) -> Frame:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    normalized = cv2.normalize(resized, None, 0, 255, cv2.NORM_MINMAX)
    return normalized


def classify_cell(cell_img: Frame, templates: dict[int, Frame], config: dict[str, Any]) -> tuple[int, float]:
    """Classify one cell and return (tile_id, confidence)."""
    if cell_img.size == 0:
        return 0, 0.0
    if not templates:
        raise ValueError("No templates available for classification.")

    prepared_cell = _prepare_for_match(cell_img)
    scored: list[tuple[int, float]] = []

    for tile_id, template in templates.items():
        prepared_template = _prepare_for_match(template)
        score = float(cv2.matchTemplate(prepared_cell, prepared_template, cv2.TM_CCOEFF_NORMED)[0, 0])
        scored.append((tile_id, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    best_id, best_score = scored[0]
    second_best = scored[1][1] if len(scored) > 1 else -1.0
    margin = best_score - second_best

    threshold = float(config["match_threshold"])
    min_margin = float(config["min_margin_to_second_best"])

    if best_score < threshold or margin < min_margin:
        return 0, best_score
    return best_id, best_score


def classify_board(
    frame: Frame,
    templates: dict[int, Frame],
    config: dict[str, Any],
) -> tuple[Board, ConfidenceMap]:
    """Classify all cells in board ROI frame."""
    rows = int(config["rows"])
    cols = int(config["cols"])

    board = np.zeros((rows, cols), dtype=np.int32)
    confidence = np.zeros((rows, cols), dtype=np.float32)

    for row in range(rows):
        for col in range(cols):
            cell_img = crop_cell(frame, row, col, config)
            tile_id, score = classify_cell(cell_img, templates, config)
            board[row, col] = tile_id
            confidence[row, col] = np.float32(score)

    return board, confidence

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from bot.grid import crop_cell

Board = np.ndarray
ConfidenceMap = np.ndarray
Frame = np.ndarray

Cell = tuple[int, int]
TemplateLabelMap = dict[int, str]
_UNRESOLVED_TILE = -2


def load_core_templates(template_dir: str) -> tuple[Frame, Frame]:
    """Load required core templates: block.png and background.png."""
    root = Path(template_dir)
    if not root.exists():
        raise FileNotFoundError(f"Template directory not found: {root}")
    if not root.is_dir():
        raise ValueError(f"Template path is not a directory: {root}")

    block_path = root / "block.png"
    background_path = root / "background.png"
    if not block_path.exists():
        raise FileNotFoundError(f"Required template not found: {block_path}")
    if not background_path.exists():
        raise FileNotFoundError(f"Required template not found: {background_path}")

    block_template = cv2.imread(str(block_path), cv2.IMREAD_COLOR)
    background_template = cv2.imread(str(background_path), cv2.IMREAD_COLOR)
    if block_template is None:
        raise RuntimeError(f"Failed to read template image: {block_path}")
    if background_template is None:
        raise RuntimeError(f"Failed to read template image: {background_path}")
    return block_template, background_template


def core_template_labels() -> TemplateLabelMap:
    """Return labels for overlay/debug rendering."""
    return {-1: "block", 0: "background"}


def _prepare_for_match(image: Frame, size: tuple[int, int] = (32, 32)) -> Frame:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
    return resized


def _score_similarity(cell_img: Frame, template_img: Frame) -> float:
    prepared_cell = _prepare_for_match(cell_img)
    prepared_template = _prepare_for_match(template_img)
    diff = np.abs(prepared_cell.astype(np.int16) - prepared_template.astype(np.int16))
    return 1.0 - float(np.mean(diff) / 255.0)


def _texture_std(cell_img: Frame) -> float:
    gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
    return float(np.std(gray))


def _center_crop(cell_img: Frame, ratio: float = 0.6) -> Frame:
    h, w = cell_img.shape[:2]
    if h == 0 or w == 0:
        return cell_img
    ch = max(1, int(h * ratio))
    cw = max(1, int(w * ratio))
    y0 = max(0, (h - ch) // 2)
    x0 = max(0, (w - cw) // 2)
    return cell_img[y0 : y0 + ch, x0 : x0 + cw]


def _pink_ratio(cell_img: Frame) -> float:
    cropped = _center_crop(cell_img, ratio=0.6)
    if cropped.size == 0:
        return 0.0
    hsv = cv2.cvtColor(cropped, cv2.COLOR_BGR2HSV)
    # Red/pink wraps around HSV hue endpoints.
    mask1 = cv2.inRange(hsv, (0, 80, 80), (12, 255, 255))
    mask2 = cv2.inRange(hsv, (170, 80, 80), (179, 255, 255))
    mask = cv2.bitwise_or(mask1, mask2)
    return float(np.count_nonzero(mask) / mask.size)


def classify_block_or_empty(
    cell_img: Frame,
    block_template: Frame,
    background_template: Frame,
    config: dict[str, Any],
) -> tuple[int, float]:
    """
    First-pass classifier:
    - returns -1 for block
    - returns 0 for background/empty
    - returns _UNRESOLVED_TILE for non-block/non-empty tiles
    """
    if cell_img.size == 0:
        return 0, 0.0
    block_score = _score_similarity(cell_img, block_template)
    pink_ratio = _pink_ratio(cell_img)
    texture_std = _texture_std(cell_img)

    block_threshold = float(config["block_match_threshold"])
    empty_pink_ratio_threshold = float(config["empty_pink_ratio_threshold"])
    empty_texture_threshold = float(config["empty_texture_threshold"])

    if block_score >= block_threshold:
        return -1, block_score
    if (
        pink_ratio >= empty_pink_ratio_threshold
        and texture_std <= empty_texture_threshold
    ):
        return 0, pink_ratio
    return _UNRESOLVED_TILE, max(block_score, pink_ratio)


def _pair_similarity(a: Frame, b: Frame) -> float:
    return float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0, 0])


def group_tiles_by_similarity(
    cell_imgs: dict[Cell, Frame],
    config: dict[str, Any],
) -> tuple[dict[Cell, int], dict[Cell, float]]:
    """
    Group unresolved tile cells by pairwise visual similarity.
    Groups with odd size are marked ambiguous (ID 0) for safety.
    """
    if not cell_imgs:
        return {}, {}

    threshold = float(config["tile_similarity_threshold"])
    cells = sorted(cell_imgs.keys())
    prepared: dict[Cell, Frame] = {cell: _prepare_for_match(cell_imgs[cell]) for cell in cells}
    index_by_cell = {cell: idx for idx, cell in enumerate(cells)}
    parent = list(range(len(cells)))

    def find(idx: int) -> int:
        while parent[idx] != idx:
            parent[idx] = parent[parent[idx]]
            idx = parent[idx]
        return idx

    def union(a_idx: int, b_idx: int) -> None:
        ra = find(a_idx)
        rb = find(b_idx)
        if ra != rb:
            parent[rb] = ra

    pair_scores: dict[tuple[Cell, Cell], float] = {}
    for i in range(len(cells)):
        for j in range(i + 1, len(cells)):
            sim = _pair_similarity(prepared[cells[i]], prepared[cells[j]])
            pair_scores[(cells[i], cells[j])] = sim
            if sim >= threshold:
                union(i, j)

    groups: dict[int, list[Cell]] = {}
    for cell in cells:
        root = find(index_by_cell[cell])
        groups.setdefault(root, []).append(cell)

    sorted_groups = sorted((sorted(group_cells) for group_cells in groups.values()), key=lambda g: g[0])

    ids: dict[Cell, int] = {}
    confidence: dict[Cell, float] = {}
    next_id = 1
    for group_cells in sorted_groups:
        group_size = len(group_cells)
        if group_size < 2 or (group_size % 2) != 0:
            for cell in group_cells:
                ids[cell] = 0
                confidence[cell] = 0.0
            continue

        for cell in group_cells:
            sims: list[float] = []
            for other in group_cells:
                if other == cell:
                    continue
                a, b = (cell, other) if cell < other else (other, cell)
                sims.append(pair_scores.get((a, b), 0.0))
            mean_sim = float(np.mean(sims)) if sims else 1.0
            ids[cell] = next_id
            confidence[cell] = mean_sim
        next_id += 1
    return ids, confidence


def classify_board(
    frame: Frame,
    block_template: Frame,
    background_template: Frame,
    config: dict[str, Any],
) -> tuple[Board, ConfidenceMap]:
    """Classify all cells using block/background templates + similarity grouping."""
    rows = int(config["rows"])
    cols = int(config["cols"])

    board = np.zeros((rows, cols), dtype=np.int32)
    confidence = np.zeros((rows, cols), dtype=np.float32)
    unresolved_cells: dict[Cell, Frame] = {}

    for row in range(rows):
        for col in range(cols):
            cell_img = crop_cell(frame, row, col, config)
            tile_id, score = classify_block_or_empty(
                cell_img,
                block_template,
                background_template,
                config,
            )
            if tile_id == _UNRESOLVED_TILE:
                unresolved_cells[(row, col)] = cell_img
            else:
                board[row, col] = tile_id
                confidence[row, col] = np.float32(score)

    grouped_ids, grouped_conf = group_tiles_by_similarity(unresolved_cells, config)
    for (row, col), tile_id in grouped_ids.items():
        board[row, col] = tile_id
        confidence[row, col] = np.float32(grouped_conf.get((row, col), 0.0))

    return board, confidence

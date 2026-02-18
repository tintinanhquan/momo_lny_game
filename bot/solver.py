from __future__ import annotations

from collections import deque

import numpy as np

Board = np.ndarray
PaddedBoard = np.ndarray
Cell = tuple[int, int]
Pair = tuple[Cell, Cell]

_DIRS: tuple[tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))


def pad_board(board: Board) -> PaddedBoard:
    """Pad board with a one-cell zero border."""
    if board.ndim != 2:
        raise ValueError("board must be a 2D array")
    rows, cols = board.shape
    padded = np.zeros((rows + 2, cols + 2), dtype=np.int32)
    padded[1 : rows + 1, 1 : cols + 1] = board.astype(np.int32, copy=False)
    return padded


def can_connect(padded: PaddedBoard, a: Cell, b: Cell) -> bool:
    """
    Return whether two padded-board cells connect with <=2 turns.

    `a` and `b` are coordinates on the padded board.
    """
    if padded.ndim != 2:
        raise ValueError("padded must be a 2D array")
    if a == b:
        return False

    rows, cols = padded.shape
    ar, ac = a
    br, bc = b
    if not (0 <= ar < rows and 0 <= ac < cols and 0 <= br < rows and 0 <= bc < cols):
        return False

    tile_a = int(padded[ar, ac])
    tile_b = int(padded[br, bc])
    if tile_a <= 0 or tile_b <= 0 or tile_a != tile_b:
        return False

    # (row, col, dir_idx, turns_used); dir_idx=-1 for the origin state.
    queue: deque[tuple[int, int, int, int]] = deque([(ar, ac, -1, 0)])
    best_turns: dict[tuple[int, int, int], int] = {}

    while queue:
        r, c, dir_idx, turns = queue.popleft()
        for next_dir, (dr, dc) in enumerate(_DIRS):
            next_turns = turns if dir_idx in (-1, next_dir) else turns + 1
            if next_turns > 2:
                continue

            nr, nc = r + dr, c + dc
            while 0 <= nr < rows and 0 <= nc < cols:
                if (nr, nc) != b and int(padded[nr, nc]) != 0:
                    break
                if (nr, nc) == b:
                    return True

                state_key = (nr, nc, next_dir)
                prev_best = best_turns.get(state_key)
                if prev_best is None or next_turns < prev_best:
                    best_turns[state_key] = next_turns
                    queue.append((nr, nc, next_dir, next_turns))

                nr += dr
                nc += dc

    return False


def find_pair(board: Board) -> Pair | None:
    """Return first valid pair in row-major deterministic order."""
    if board.ndim != 2:
        raise ValueError("board must be a 2D array")

    rows, cols = board.shape
    padded = pad_board(board)

    for r1 in range(rows):
        for c1 in range(cols):
            tile = int(board[r1, c1])
            if tile <= 0:
                continue
            for r2 in range(r1, rows):
                c2_start = c1 + 1 if r2 == r1 else 0
                for c2 in range(c2_start, cols):
                    if int(board[r2, c2]) != tile:
                        continue
                    if can_connect(padded, (r1 + 1, c1 + 1), (r2 + 1, c2 + 1)):
                        return (r1, c1), (r2, c2)
    return None

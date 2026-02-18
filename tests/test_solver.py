from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bot.solver import can_connect, find_pair, pad_board


def test_can_connect_direct_line() -> None:
    board = np.array([[1, 0, 1]], dtype=np.int32)
    padded = pad_board(board)
    assert can_connect(padded, (1, 1), (1, 3))


def test_can_connect_one_turn_path() -> None:
    board = np.array(
        [
            [1, 0],
            [0, 1],
        ],
        dtype=np.int32,
    )
    padded = pad_board(board)
    assert can_connect(padded, (1, 1), (2, 2))


def test_can_connect_two_turn_path() -> None:
    board = np.array(
        [
            [1, 0, -1],
            [-1, 0, -1],
            [0, 0, 1],
        ],
        dtype=np.int32,
    )
    padded = pad_board(board)
    assert can_connect(padded, (1, 1), (3, 3))


def test_can_connect_blocked_path() -> None:
    board = np.array(
        [
            [-1, -1, -1, -1, -1],
            [-1, 1, -1, 1, -1],
            [-1, -1, -1, -1, -1],
        ],
        dtype=np.int32,
    )
    padded = pad_board(board)
    assert not can_connect(padded, (2, 2), (2, 4))


def test_can_connect_border_routing_path() -> None:
    board = np.array([[1, -1, 1]], dtype=np.int32)
    padded = pad_board(board)
    assert can_connect(padded, (1, 1), (1, 3))


def test_different_ids_never_connect() -> None:
    board = np.array([[1, 0, 2]], dtype=np.int32)
    padded = pad_board(board)
    assert not can_connect(padded, (1, 1), (1, 3))


def test_find_pair_deterministic_order() -> None:
    board = np.array(
        [
            [1, 0, 1],
            [2, 0, 2],
        ],
        dtype=np.int32,
    )
    assert find_pair(board) == ((0, 0), (0, 2))


def test_find_pair_returns_none_for_dead_board() -> None:
    board = np.array(
        [
            [-1, -1, -1, -1, -1],
            [-1, 1, -1, 1, -1],
            [-1, -1, -1, -1, -1],
            [-1, 2, -1, 2, -1],
            [-1, -1, -1, -1, -1],
        ],
        dtype=np.int32,
    )
    assert find_pair(board) is None

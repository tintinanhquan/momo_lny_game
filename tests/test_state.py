from pathlib import Path
import sys

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bot.state import apply_successful_move, init_runtime_state, record_failure, should_full_rescan


def _config() -> dict:
    return {
        "full_rescan_every_n_moves": 5,
        "match_threshold": 0.3,
        "max_consecutive_failures": 4,
    }


def test_init_runtime_state_defaults() -> None:
    state = init_runtime_state(_config())
    assert state["move_count"] == 0
    assert state["consecutive_failures"] == 0
    assert state["last_full_rescan_move"] == 0
    assert state["rescan_requested"] is False
    assert state["last_rescan_reason"] is None
    assert state["last_event"] == "init"
    assert state["last_pair"] is None


def test_should_full_rescan_periodic_trigger() -> None:
    state = init_runtime_state(_config())
    state["move_count"] = 5
    confidence = np.full((3, 3), 0.95, dtype=np.float32)

    triggered = should_full_rescan(state, confidence, _config())

    assert triggered is True
    assert state["last_full_rescan_move"] == 5
    assert "periodic" in state["last_rescan_reason"]
    assert state["last_event"] == "full_rescan"


def test_should_full_rescan_low_confidence_trigger() -> None:
    state = init_runtime_state(_config())
    confidence = np.array(
        [
            [0.9, 0.9, 0.9],
            [0.9, 0.1, 0.9],
            [0.9, 0.9, 0.9],
        ],
        dtype=np.float32,
    )

    triggered = should_full_rescan(state, confidence, _config())

    assert triggered is True
    assert "low_confidence" in state["last_rescan_reason"]


def test_record_failure_requests_rescan_and_increments_counter() -> None:
    state = init_runtime_state(_config())
    record_failure(state)

    assert state["consecutive_failures"] == 1
    assert state["rescan_requested"] is True
    assert state["last_event"] == "failure"

    confidence = np.full((3, 3), 0.95, dtype=np.float32)
    triggered = should_full_rescan(state, confidence, _config())
    assert triggered is True
    assert "failure_or_mismatch" in state["last_rescan_reason"]
    assert state["rescan_requested"] is False


def test_apply_successful_move_resets_failures_and_updates_counters() -> None:
    state = init_runtime_state(_config())
    state["consecutive_failures"] = 3
    pair = ((0, 1), (2, 2))

    apply_successful_move(state, pair)

    assert state["move_count"] == 1
    assert state["consecutive_failures"] == 0
    assert state["last_pair"] == pair
    assert state["last_event"] == "move_success"
    assert state["rescan_requested"] is False


def test_stop_condition_reaches_max_failures() -> None:
    state = init_runtime_state(_config())
    for _ in range(4):
        record_failure(state)

    assert state["consecutive_failures"] == _config()["max_consecutive_failures"]


def test_should_full_rescan_false_when_conditions_not_met() -> None:
    state = init_runtime_state(_config())
    state["move_count"] = 1
    confidence = np.full((3, 3), 0.95, dtype=np.float32)

    triggered = should_full_rescan(state, confidence, _config())

    assert triggered is False
    assert state["last_rescan_reason"] is None

from __future__ import annotations

from typing import Any

import numpy as np

ConfidenceMap = np.ndarray
Pair = tuple[tuple[int, int], tuple[int, int]]


def init_runtime_state(config: dict[str, Any]) -> dict[str, Any]:
    """Initialize deterministic runtime counters and trace fields."""
    _ = config  # Config is part of the stable API for future extensions.
    return {
        "move_count": 0,
        "consecutive_failures": 0,
        "last_full_rescan_move": 0,
        "rescan_requested": False,
        "last_rescan_reason": None,
        "last_event": "init",
        "last_pair": None,
    }


def should_full_rescan(
    state: dict[str, Any],
    confidence: ConfidenceMap,
    config: dict[str, Any],
) -> bool:
    """
    Decide whether to perform a full board rescan.

    Triggers:
    - periodic cadence (`full_rescan_every_n_moves`)
    - low confidence in current frame
    - explicit failure/mismatch request (`rescan_requested`)

    This function updates state when a rescan is triggered so repeated calls are deterministic.
    """
    reasons: list[str] = []
    move_count = int(state.get("move_count", 0))
    every_n = int(config["full_rescan_every_n_moves"])
    last_rescan_move = int(state.get("last_full_rescan_move", 0))

    if move_count > 0 and (move_count - last_rescan_move) >= every_n:
        reasons.append("periodic")

    if bool(state.get("rescan_requested", False)):
        reasons.append("failure_or_mismatch")

    threshold = float(config["match_threshold"])
    if confidence.size == 0:
        reasons.append("empty_confidence")
    elif bool(np.any(confidence < threshold)):
        reasons.append("low_confidence")

    if not reasons:
        state["last_rescan_reason"] = None
        return False

    state["last_full_rescan_move"] = move_count
    state["rescan_requested"] = False
    state["last_rescan_reason"] = ",".join(reasons)
    state["last_event"] = "full_rescan"
    return True


def apply_successful_move(state: dict[str, Any], pair: Pair) -> None:
    """Record successful move and reset failure streak."""
    state["move_count"] = int(state.get("move_count", 0)) + 1
    state["consecutive_failures"] = 0
    state["last_pair"] = pair
    state["last_event"] = "move_success"
    state["rescan_requested"] = False


def record_failure(state: dict[str, Any]) -> None:
    """Record a runtime failure and request a full rescan."""
    state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
    state["rescan_requested"] = True
    state["last_event"] = "failure"

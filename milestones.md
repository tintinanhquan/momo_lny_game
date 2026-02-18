# Momo Bot Implementation Milestones

## Purpose

This file is an execution-focused guide for implementing the bot defined in `plan.md`.
It is written so an engineering agent can pick each milestone and implement it end-to-end.

Use this with the following principles:

- implement one milestone at a time
- do not skip validation gates
- keep code simple and testable
- preserve stable interfaces between modules

## Current Progress

- Milestone 0: completed
- Milestone 1: completed
- Milestone 2: completed
- Milestone 3: completed
- Milestone 4: completed
- Milestone 5: completed
- Last validated artifact: `uv run pytest` (26 passed)
- Current focus: Milestone 6 (full loop integration)

---

## Global Constraints

- Use Python 3.10+ and `uv` for environment/dependencies.
- Assume iPhone Mirroring window is fixed in position and scale.
- Use fixed board ROI from `config.json` for V1.
- Board geometry uses fixed center + pitch:
  - `board_center_x=3183`, `board_center_y=542`
  - `cell_w=72`, `cell_h=70`
  - `gap_x=6`, `gap_y=4`
- Board encoding:
  - `0` = empty
  - `-1` = blocked tile
  - `1..N` = tile IDs
- Internal board must be padded by 1 cell on all sides.
- Avoid hidden global state; pass data through function inputs/outputs.
- Board contents can shift after matches (up/down/left/right), but always remain inside capture ROI.
- Post-match transient animation can corrupt one-shot captures; classification must use a settled/stable frame.

---

## Target Project Layout

```text
main.py
config.json
templates/
  .gitkeep
bot/
  __init__.py
  capture.py
  calibrate.py
  grid.py
  classify.py
  solver.py
  clicker.py
  state.py
  debug.py
tests/
  test_smoke.py
  test_solver.py
```

---

## Shared Data Contracts

Keep these contracts stable while implementing.

### Config Schema (`config.json`)

Required keys:

- `rows`: int
- `cols`: int
- `board_center_x`: int
- `board_center_y`: int
- `cell_w`: int
- `cell_h`: int
- `gap_x`: int
- `gap_y`: int
- `match_threshold`: float
- `min_margin_to_second_best`: float
- `click_pause_ms`: int
- `post_click_wait_ms`: int
- `settle_wait_ms`: int
- `stability_check_frames`: int
- `stability_pixel_diff_threshold`: float
- `full_rescan_every_n_moves`: int
- `max_consecutive_failures`: int
- `debug_enabled`: bool
- `debug_dir`: string

### Core Types

- `Frame`: `np.ndarray` in BGR color space
- `Board`: `np.ndarray` shape `(rows, cols)` with int32
- `PaddedBoard`: `np.ndarray` shape `(rows+2, cols+2)` with int32
- `ConfidenceMap`: `np.ndarray` shape `(rows, cols)` with float32
- `Cell`: tuple `(row, col)` zero-indexed, non-padded coordinates
- `Pair`: tuple `(cell_a, cell_b)`

---

## Milestone 0 - Bootstrap and Config Loading

### Goal

Project runs from `uv run python main.py`, loads config, and prints a startup summary.

### Files to implement

- `main.py`
- `config.json`
- optional helper: `bot/state.py` for config/state dataclasses

### Required tasks

1. Add a `load_config(path: str) -> dict` function with validation.
2. Fail fast with clear error messages for missing keys or invalid values.
3. Print startup summary:
   - board ROI
   - grid size
   - debug mode
4. Keep `main.py` executable as script entry point.

### Acceptance criteria

- `uv run python main.py` exits with status `0` when config valid.
- invalid config exits non-zero with actionable error text.

### Status

Completed.

Implemented:

- `load_config(path: str) -> dict` with schema validation and fast-fail errors
- startup summary output for board ROI, grid size, and debug mode
- script entry point via `if __name__ == "__main__": raise SystemExit(main())`

Validated:

- `uv run python main.py`
- `uv run pytest`

---

## Milestone 1 - Capture + Grid Mapping

### Goal

Capture the board ROI from screen and map it to cell rectangles/centers correctly.

### Files to implement

- `bot/capture.py`
- `bot/grid.py`
- `bot/debug.py`
- `main.py` (wire a one-shot command path)

### Required functions

- `capture_board(config: dict) -> Frame`
- `get_cell_rect(row: int, col: int, config: dict) -> tuple[int, int, int, int]`
- `get_cell_center(row: int, col: int, config: dict) -> tuple[int, int]`
- `draw_grid_overlay(frame: Frame, config: dict) -> Frame`

### Required tasks

1. Use `mss` to grab exact ROI derived from geometry (`board_center_x`, `board_center_y`, `rows`, `cols`, `cell_w`, `cell_h`, `gap_x`, `gap_y`).
2. Compute per-cell geometry from `rows` and `cols`.
3. Draw visible grid lines and center points for debug.
4. Save one overlay image to `debug_dir`.

### Acceptance criteria

- overlay image exists and matches expected dimensions.
- center points are visually aligned with tile centers.

### Status

Completed.

Implemented:

- `capture_board(config)` using `mss` and ROI from `config.json`
- `get_cell_rect(...)` and `get_cell_center(...)` in `bot/grid.py`
- `draw_grid_overlay(frame, config)` with grid lines and center dots
- one-shot capture path via `uv run python main.py --capture-once`
- debug image save to `debug_dir` via `save_debug_snapshot(...)`
- interactive ROI helper script `calibrate_roi.py`

Validated:

- overlay files generated in `debug/`
- alignment manually confirmed on real mirrored board

---

## Milestone 2 - Template Loader + Classification

### Goal

Convert each board cell into tile ID + confidence with template matching.

### Files to implement

- `bot/classify.py`
- `bot/grid.py` (cell crop helpers)
- `bot/debug.py`
- `main.py` (classification one-shot command)

### Required functions

- `load_templates(template_dir: str) -> dict[int, Frame]`
- `classify_cell(cell_img: Frame, templates: dict[int, Frame], config: dict) -> tuple[int, float]`
- `classify_board(frame: Frame, templates: dict[int, Frame], config: dict) -> tuple[Board, ConfidenceMap]`

### Required tasks

1. Define template naming convention:
   - `block.png` maps to `-1`
   - every other template filename maps to positive integer IDs by alphabetical order
2. Per-cell classification:
   - optional preprocessing (grayscale, normalization)
   - match all templates
   - best score and second-best score
3. Apply thresholds:
   - if below `match_threshold`, mark as `0` (unknown/empty for V1)
   - if best-second margin below `min_margin_to_second_best`, mark uncertain
4. Add pre-classification stabilization:
   - wait for `settle_wait_ms` after moves
   - optionally require `stability_check_frames` captures whose pixel diff stays below `stability_pixel_diff_threshold`
5. Emit confidence map and unknown count.
6. Save a debug image with IDs and labels rendered on top of grid.

### Acceptance criteria

- classification runs on a captured frame without crashing.
- output matrix shape is `(rows, cols)`.
- debug image shows per-cell labels and scores.
- semantic template set works without requiring `tile_XX.png` naming.

### Status

Completed.

Implemented:

- `load_templates_with_labels(...)` with deterministic semantic filename mapping (`block.png -> -1`, others alphabetical `1..N`)
- `classify_cell(...)` and `classify_board(...)` with preprocessing, thresholding, and confidence map output
- fixed geometry cell cropping from `board_center`, `cell_w/cell_h`, and `gap_x/gap_y`
- stable-frame capture guard before classification (`settle_wait_ms`, `stability_check_frames`, `stability_pixel_diff_threshold`)
- one-shot classification path via `uv run python main.py --classify-once`
- classification overlay with per-cell ID/label/score rendering

Validated:

- `uv run pytest` (all tests passing)
- one-shot classification path integrated with template loading and overlay output

---

## Milestone 3 - Onet Solver (<=2 Turns)

### Goal

Find at least one valid pair on a board using Onet constraints.

### Files to implement

- `bot/solver.py`
- `tests/test_solver.py`

### Required functions

- `pad_board(board: Board) -> PaddedBoard`
- `can_connect(padded: PaddedBoard, a: tuple[int, int], b: tuple[int, int]) -> bool`
- `find_pair(board: Board) -> Pair | None`

### Solver rules

- two cells must have same positive tile ID
- path can move orthogonally only
- path may pass through `0` only
- path may not pass through positive IDs or `-1`
- path may use at most two turns
- path may route through padded border

### Required tasks

1. Implement BFS state `(r, c, dir, turns)`.
2. Prune states when `turns > 2`.
3. Ensure deterministic pair selection (stable order).
4. Add tests:
   - direct line
   - one-turn path
   - two-turn path
   - blocked path
   - border-routing path
   - different IDs never connect

### Acceptance criteria

- `uv run pytest -k solver` passes all tests.
- `find_pair` returns `None` on dead boards.

### Status

Completed.

Implemented:

- `pad_board(...)` with one-cell zero border and shape validation
- `can_connect(...)` using BFS over states `(r, c, dir, turns)` with turn pruning (`<=2`)
- deterministic `find_pair(...)` scan order in row-major order
- solver test coverage for direct, one-turn, two-turn, blocked, border-routing, and different-ID cases

Validated:

- `uv run pytest -k solver` (8 passed)
- dead-board case returns `None` in solver tests

---

## Milestone 4 - Click Execution

### Goal

Given a valid pair, click two corresponding screen coordinates safely.

### Files to implement

- `bot/clicker.py`
- `bot/grid.py`
- `main.py`

### Required functions

- `click_cell(cell: Cell, config: dict) -> None`
- `click_pair(pair: Pair, config: dict) -> None`

### Required tasks

1. Convert `(row, col)` to absolute screen center using board ROI.
2. Set `pyautogui.PAUSE` from config.
3. Click first cell, then second cell.
4. Wait `post_click_wait_ms` after second click.
5. Add `dry_run` mode to print clicks without moving mouse.

### Acceptance criteria

- dry run prints correct coordinates.
- real run clicks expected cells with consistent timing.

### Status

Completed.

Implemented:

- `click_cell(cell, config, dry_run=False)` with bounds validation, center mapping, and `pyautogui.PAUSE` from `click_pause_ms`
- `click_pair(pair, config, dry_run=False)` that clicks first then second, then waits `post_click_wait_ms`
- CLI wiring for `--click-once` and `--dry-run` in `main.py` using one-shot flow: stable capture -> classify -> solve -> click
- dry-run logging format for deterministic coordinate verification before real clicking
- unit tests in `tests/test_clicker.py` for dry-run behavior, click ordering, pause/wait timing, and bounds errors

Validated:

- `uv run pytest -k clicker` (5 passed)
- `uv run pytest` (18 passed)

---

## Milestone 5 - Runtime State + Recovery

### Goal

Maintain reliable runtime behavior across many moves.

### Files to implement

- `bot/state.py`
- `bot/classify.py`
- `main.py`

### Required functions

- `init_runtime_state(config: dict) -> dict`
- `should_full_rescan(state: dict, confidence: ConfidenceMap, config: dict) -> bool`
- `apply_successful_move(state: dict, pair: Pair) -> None`
- `record_failure(state: dict) -> None`

### Required tasks

1. Track:
   - `move_count`
   - `consecutive_failures`
   - `last_full_rescan_move`
2. Rescan triggers:
   - every `full_rescan_every_n_moves`
   - low confidence on active frame
   - after failure or mismatch
3. Stop triggers:
   - `consecutive_failures >= max_consecutive_failures`

### Acceptance criteria

- state transitions are deterministic and logged.
- bot stops safely on repeated failure.

### Status

Completed.

Implemented:

- runtime state API in `bot/state.py`: `init_runtime_state(...)`, `should_full_rescan(...)`, `apply_successful_move(...)`, `record_failure(...)`
- deterministic counters/traces: `move_count`, `consecutive_failures`, `last_full_rescan_move`, rescan reason/request flags, and last event/pair metadata
- rescan policy covering periodic cadence (`full_rescan_every_n_moves`), low-confidence frames, and failure/mismatch requests
- one-shot runtime wiring in `main.py` for state initialization, transition logging, recovery attempts, and safe-stop trigger checks
- new unit coverage in `tests/test_state.py` for initialization, transitions, triggers, and stop condition behavior

Validated:

- `uv run pytest -k state` (7 passed)
- `uv run pytest` (26 passed)

---

## Milestone 6 - Full Loop Integration

### Goal

Integrate capture, classify, solve, click, and state into one continuous loop.

### Files to implement

- `main.py`
- all `bot/*.py` modules

### Required flow

1. load config
2. load templates
3. init state
4. loop:
   - capture frame
   - classify board (or partial update if implemented)
   - find pair
   - if no pair: stop gracefully
   - click pair
   - update state
   - write debug artifacts if enabled

### Required runtime controls

- command-line flags:
  - `--once` (single loop)
  - `--dry-run` (no clicks)
  - `--debug` (force debug artifacts)

### Acceptance criteria

- `uv run python main.py --once --dry-run` completes one full cycle.
- full run performs repeated moves until stop condition.

---

## Milestone 7 - Observability + Diagnostics

### Goal

Make failures diagnosable without guessing.

### Files to implement

- `bot/debug.py`
- `main.py`

### Required outputs per iteration (if debug enabled)

- raw ROI capture
- grid overlay
- classified board overlay (IDs + confidences)
- selected pair summary
- timing metrics:
  - capture ms
  - classify ms
  - solve ms
  - click ms

### Acceptance criteria

- each loop produces a structured log line.
- debug images saved with timestamped filenames.

---

## Milestone 8 - Final Validation

### Goal

Confirm V1 readiness on real gameplay.

### Test checklist

1. Static frame test: classification quality acceptable on at least 5 screenshots.
2. Solver test suite: all passing.
3. Dry-run coordinate test: no off-grid clicks.
4. Live run:
   - completes >=20 moves without drift
   - handles blocked cells correctly
   - stops cleanly when no pair exists

### Exit criteria

Mark V1 complete only when all checklist items pass.

---

## Suggested Work Order for Agent

1. Milestone 0
2. Milestone 1
3. Milestone 2
4. Milestone 3
5. Milestone 4
6. Milestone 5
7. Milestone 6
8. Milestone 7
9. Milestone 8

At the end of each milestone:

- run relevant tests/commands
- record what was completed
- list blockers before moving to next milestone

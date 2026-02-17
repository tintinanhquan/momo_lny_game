# Momo iPhone Mirroring Bot - Project Plan

## 1) Project Goal

Build a Python bot that plays an Onet-style iPhone game through iPhone Mirroring on macOS by:

1. Capturing a fixed board area from screen
2. Detecting tile IDs for each grid cell
3. Finding a valid pair path (<= 2 turns)
4. Clicking both tiles
5. Repeating until the board is cleared or no valid move remains

---

## 2) Scope

### In Scope (V1)

- Fixed board region from manual calibration
- Configurable board size (`rows`, `cols`)
- Template-based tile classification
- Blocked-cell support (`-1`)
- Onet solver with <= 2 turns using BFS
- Automated clicking and loop execution
- Debug snapshots and logs

### Out of Scope (V1)

- Full automatic mirror-window detection
- Universal support for every UI popup/state
- Deep-learning classifier

---

## 3) Tech Stack

- Python 3.10+
- `uv` for environment and dependency management
- `opencv-python` for image matching
- `numpy` for board matrix + solver
- `mss` for fast screen capture
- `pyautogui` for clicking
- `pillow` for optional image utilities

Install and manage dependencies with `uv`:

```bash
uv init
uv add opencv-python numpy pyautogui mss pillow
uv add --dev pytest
```

Run commands:

```bash
uv run python main.py
uv run pytest
```

Lock/sync workflow:

- Add package: `uv add <package>`
- Remove package: `uv remove <package>`
- Sync env from lock file: `uv sync`
- Commit `pyproject.toml` and `uv.lock` for reproducibility

---

## 4) Project Structure

```text
momo-bot/
  main.py
  config.json
  templates/
    block.png
    tile_01.png
    tile_02.png
    ...
  bot/
    capture.py
    calibrate.py
    grid.py
    classify.py
    solver.py
    clicker.py
    state.py
    debug.py
  tests/
    test_solver.py
```

---

## 5) Data Model

### Board Encoding

- `0` = empty
- `-1` = blocked/permanent obstacle
- `1..N` = tile class IDs

### Padded Board

If visible board is `R x C`, internal board is `(R+2) x (C+2)` with outer zeros.
This simplifies pathfinding around edges.

### Runtime State

- current board matrix
- confidence map per cell
- move counter
- consecutive failure counter
- last action timestamps

---

## 6) Module Responsibilities

### `capture.py`

- Capture board ROI from screen via `mss`
- Return frame as numpy image

### `calibrate.py`

- Capture board corners manually
- Save `board_x`, `board_y`, `board_w`, `board_h`, `rows`, `cols` to `config.json`

### `grid.py`

- Split captured frame into cell crops
- Convert `(row, col)` <-> pixel center `(x, y)`

### `classify.py`

- Load templates from `templates/`
- Classify each cell by highest template score
- Return ID matrix and confidence matrix

### `solver.py`

- Find valid match pair with Onet rules (<=2 turns)
- BFS state: `(r, c, direction, turns_used)`

### `clicker.py`

- Click two board cells using screen coordinates
- Apply configurable click delay and post-click wait

### `state.py`

- Maintain internal board updates after successful moves
- Trigger full rescan when confidence is low or state is uncertain

### `debug.py`

- Save overlay images (grid, IDs, selected pair path)
- Write action logs and timing metrics

---

## 7) Configuration

`config.json` fields:

- `board_x`, `board_y`, `board_w`, `board_h`
- `rows`, `cols`
- `match_threshold`
- `min_margin_to_second_best`
- `click_pause_ms`
- `post_click_wait_ms`
- `full_rescan_every_n_moves`
- `max_consecutive_failures`
- `debug_enabled`

---

## 8) Main Loop Design

1. Capture board frame
2. Build/update board matrix from classifier
3. Ask solver for one valid pair
4. If no pair -> stop (level complete or dead board)
5. Click first tile, then second tile
6. Wait for animation
7. Update internal state (or full rescan if needed)
8. Repeat

Pseudo:

```python
while running:
    frame = capture_board()
    board, confidence = build_board(frame)
    pair = solver.find_pair(board)
    if not pair:
        break
    click_pair(pair)
    wait_animation()
    update_or_rescan(pair, confidence)
```

---

## 9) Implementation Roadmap

## Phase 0 - Environment Setup

- Initialize project with `uv`
- Add runtime and dev dependencies
- Create project folders and starter files
- Verify runtime and tests execute through `uv run`

Phase 0 commands:

```bash
uv init
uv add opencv-python numpy pyautogui mss pillow
uv add --dev pytest
uv run python main.py
uv run pytest
```

Deliverable: project boots with `uv run python main.py`.

## Phase 1 - Calibration + Board Overlay

- Implement manual ROI calibration
- Render grid overlay on captured frame
- Validate cell centers align with real tiles

Deliverable: accurate board capture and grid mapping.

## Phase 2 - Tile Classification

- Load templates
- Classify all cells with score thresholds
- Output board matrix and unknown count

Deliverable: stable tile ID matrix on static screenshots.

## Phase 3 - Solver Engine

- Implement padded board BFS with <=2 turns
- Add solver tests (normal, blocked, edge-routing cases)

Deliverable: `find_pair(board)` works on tests.

## Phase 4 - Click Execution

- Convert cell index to absolute screen coordinate
- Single-step one move with safety delay

Deliverable: one valid pair gets removed consistently.

## Phase 5 - Full Automation Loop

- Integrate capture + classify + solve + click
- Add recovery logic (periodic full rescan, fail limits)
- Add stop/start hotkeys

Deliverable: autonomous multi-move run on real level.

---

## 10) Testing Plan

### Unit Tests

- solver path validity (0, 1, 2 turns)
- blocked cells cannot be crossed
- no false positives across different tile IDs

### Integration Tests

- classification accuracy on saved board screenshots
- coordinate mapping correctness for click targets

### Live Run Checks

- run at least 3 levels with same board layout
- verify no drift after 20+ moves
- verify graceful stop on no-move state

---

## 11) Risk Controls

- Keep mirroring window fixed (position, size, scale)
- Use full-rescan fallback when confidence drops
- Stop on repeated mismatches instead of blind clicking
- Keep debug snapshots enabled until stable

---

## 12) Definition of Done (V1)

V1 is complete when all are true:

1. Bot can clear or progress through multiple real levels without manual clicks.
2. Solver correctly handles blocked cells and <=2-turn constraint.
3. Classification and clicking are stable under fixed mirror setup.
4. Logs/debug artifacts are sufficient to diagnose failures quickly.

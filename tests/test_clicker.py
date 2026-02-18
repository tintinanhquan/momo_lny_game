from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from bot.clicker import click_cell, click_pair


def _config() -> dict:
    return {
        "rows": 3,
        "cols": 3,
        "board_center_x": 200,
        "board_center_y": 200,
        "cell_w": 20,
        "cell_h": 20,
        "gap_x": 0,
        "gap_y": 0,
        "click_pause_ms": 80,
        "post_click_wait_ms": 250,
    }


def test_click_cell_dry_run_prints_and_does_not_click(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    clicked: list[tuple[int, int]] = []

    def _fake_click(*, x: int, y: int) -> None:
        clicked.append((x, y))

    monkeypatch.setattr("bot.clicker.pyautogui.click", _fake_click)

    click_cell((0, 0), _config(), dry_run=True)

    out = capsys.readouterr().out
    assert "[dry-run] click_cell row=0 col=0 -> x=180 y=180" in out
    assert clicked == []


def test_click_pair_real_mode_clicks_in_order_and_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    clicked: list[tuple[int, int]] = []
    slept: list[float] = []

    def _fake_click(*, x: int, y: int) -> None:
        clicked.append((x, y))

    def _fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("bot.clicker.pyautogui.click", _fake_click)
    monkeypatch.setattr("bot.clicker.time.sleep", _fake_sleep)

    cfg = _config()
    click_pair(((0, 0), (2, 2)), cfg, dry_run=False)

    assert clicked == [(180, 180), (220, 220)]
    assert slept == [0.25]
    assert cfg["click_pause_ms"] / 1000.0 == pytest.approx(0.08)


def test_click_pair_dry_run_does_not_click_but_still_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    clicked: list[tuple[int, int]] = []
    slept: list[float] = []

    monkeypatch.setattr("bot.clicker.pyautogui.click", lambda **kwargs: clicked.append((kwargs["x"], kwargs["y"])))
    monkeypatch.setattr("bot.clicker.time.sleep", lambda seconds: slept.append(seconds))

    click_pair(((0, 1), (1, 1)), _config(), dry_run=True)

    assert clicked == []
    assert slept == [0.25]


def test_click_cell_sets_pyautogui_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("bot.clicker.pyautogui.click", lambda **kwargs: None)
    click_cell((1, 1), _config(), dry_run=False)
    assert pytest.approx(0.08) == sys.modules["bot.clicker"].pyautogui.PAUSE


def test_click_cell_out_of_range_raises() -> None:
    with pytest.raises(ValueError, match="row"):
        click_cell((3, 0), _config(), dry_run=True)
    with pytest.raises(ValueError, match="col"):
        click_cell((0, 3), _config(), dry_run=True)

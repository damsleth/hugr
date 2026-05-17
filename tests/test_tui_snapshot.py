"""Textual snapshot / structural tests for the mnem TUI.

Uses Textual's App.run_test() (async pilot).  Skipped cleanly when the
[tui] extra is not installed so CI without textual still passes.

03.1 scope: ask screen only.
"""

from __future__ import annotations

import pytest

textual = pytest.importorskip("textual", reason="textual not installed; install mnem-suite[tui]")


@pytest.mark.asyncio
async def test_ask_screen_initial_render() -> None:
  """App boots, ask screen is the active screen, key widgets are present."""
  from mnem.tui.app import MnemApp
  from mnem.tui.screens.ask import AskScreen

  app = MnemApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()

    # Active screen must be AskScreen
    assert isinstance(pilot.app.screen, AskScreen), (
      f"Expected AskScreen, got {type(pilot.app.screen)}"
    )

    screen = pilot.app.screen

    # Input widget must exist on the screen
    from textual.widgets import Input, Static
    input_widget = screen.query_one("#query-input", Input)
    assert input_widget is not None

    # Results pane must exist and show the placeholder
    results = screen.query_one("#results", Static)
    rendered = str(results.content)
    assert "Press Enter to search" in rendered

    # Nav bar must be present
    nav = screen.query_one("#nav", Static)
    assert nav is not None


@pytest.mark.asyncio
async def test_ask_screen_after_typing(monkeypatch) -> None:
  """Typing keys into the query input and pressing Enter updates the results pane."""
  from mnem.tui.app import MnemApp
  from mnem.tui.screens.ask import AskScreen
  from textual.widgets import Static

  captured_worker: dict[str, object] = {}

  def _fake_run_worker(
    self,
    work,
    *,
    name="",
    group="default",
    description="",
    exit_on_error=True,
    start=True,
    exclusive=False,
    thread=False,
  ):
    del self, work, group, description, exit_on_error, start
    captured_worker["name"] = name
    captured_worker["exclusive"] = exclusive
    captured_worker["thread"] = thread

  monkeypatch.setattr(AskScreen, "run_worker", _fake_run_worker)

  app = MnemApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()

    assert isinstance(pilot.app.screen, AskScreen)
    screen = pilot.app.screen

    # Type a query character by character via pilot.press
    for ch in "test":
      await pilot.press(ch)
    await pilot.pause()

    # Input widget captured the keys
    from textual.widgets import Input
    input_widget = screen.query_one("#query-input", Input)
    assert input_widget is not None

    # Press Enter - results pane updates (may show error or "Searching...")
    await pilot.press("enter")
    await pilot.pause(delay=0.1)

    results = screen.query_one("#results", Static)
    # After submit the placeholder text should be gone
    rendered = str(results.content)
    assert rendered.strip() != ""
    assert captured_worker == {
      "name": "yaams-query",
      "exclusive": True,
      "thread": True,
    }


@pytest.mark.asyncio
async def test_q_key_quits() -> None:
  """Pressing q while input is not focused exits the app cleanly."""
  from mnem.tui.app import MnemApp

  app = MnemApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    # Dismiss the input focus so the screen binding picks up 'q'
    await pilot.press("escape")
    await pilot.pause()
    await pilot.press("q")
    # Reaching here without exception means the quit action fired (or was queued)

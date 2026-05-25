"""Snapshot tests for the 03.2 TUI screens.

Each screen renders an initial placeholder and uses run_worker to fetch
data. Tests verify that pressing the nav key swaps screens and that the
results pane reflects the api response.
"""

from __future__ import annotations

import pytest

textual = pytest.importorskip("textual", reason="textual not installed; install hugr-cli[tui]")


@pytest.mark.asyncio
async def test_inbox_screen_loads_doc(monkeypatch) -> None:
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.inbox import InboxScreen
  from textual.widgets import Static

  import hugr.api as api
  monkeypatch.setattr(
    api,
    "inbox",
    lambda: {
      "tool": "hugr",
      "command": "inbox",
      "sources": [
        {"source": "owa-mail", "command": "list", "ok": True, "data": [{"id": "m1"}]},
        {"source": "owa-cal", "command": "events", "ok": True, "data": []},
        {"source": "ledger", "command": "loops", "ok": True, "data": {"loops": [{"id": "l1"}, {"id": "l2"}]}},
        {"source": "yaams", "command": "promote list", "ok": False, "data": None},
      ],
      "warnings": [],
    },
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    # Switch to inbox
    pilot.app.action_inbox_screen()
    await pilot.pause(delay=0.1)

    assert isinstance(pilot.app.screen, InboxScreen)
    # Wait for the worker to finish
    for _ in range(40):
      rendered = str(pilot.app.screen.query_one("#results", Static).content)
      if "owa-mail" in rendered:
        break
      await pilot.pause(delay=0.05)
    assert "owa-mail" in rendered
    assert "(2 items)" in rendered  # ledger loops


@pytest.mark.asyncio
async def test_find_screen_runs_query(monkeypatch) -> None:
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.find import FindScreen
  from textual.widgets import Static

  import hugr.api as api
  monkeypatch.setattr(
    api,
    "find",
    lambda kind, query, **kw: {
      "tool": "hugr",
      "command": "find",
      "kind": kind,
      "query": query,
      "source": {
        "source": "owa-people",
        "command": "lookup",
        "ok": True,
        "data": [{"name": "Nina"}, {"name": "Nora"}],
      },
      "warnings": [],
    },
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_find_screen()
    await pilot.pause(delay=0.1)

    assert isinstance(pilot.app.screen, FindScreen)
    for ch in "nina":
      await pilot.press(ch)
    await pilot.press("enter")
    for _ in range(40):
      rendered = str(pilot.app.screen.query_one("#results", Static).content)
      if "Nina" in rendered:
        break
      await pilot.pause(delay=0.05)
    assert "Nina" in rendered


@pytest.mark.asyncio
async def test_doctor_screen_renders_report(monkeypatch) -> None:
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.doctor import DoctorScreen
  from textual.widgets import Static

  import hugr.api as api
  monkeypatch.setattr(
    api,
    "doctor",
    lambda: {
      "tool": "hugr",
      "summary": "ok",
      "findings": [{"severity": "info", "tool": "yaams", "message": "all good"}],
      "components": [{"tool": "yaams", "state": "ok"}],
    },
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_doctor_screen()
    await pilot.pause(delay=0.1)

    assert isinstance(pilot.app.screen, DoctorScreen)
    for _ in range(40):
      rendered = str(pilot.app.screen.query_one("#results", Static).content)
      if "hugr doctor: ok" in rendered:
        break
      await pilot.pause(delay=0.05)
    assert "hugr doctor: ok" in rendered
    assert "yaams" in rendered


@pytest.mark.asyncio
async def test_session_screen_shows_active(monkeypatch, tmp_path) -> None:
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "hugr-home"))
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
  from hugr import session as session_mod
  meta = session_mod.start_session()
  monkeypatch.setenv("HUGR_SESSION", meta.id)

  from hugr.tui.app import HugrApp
  from hugr.tui.screens.session import SessionScreen
  from textual.widgets import Static

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_session_screen()
    await pilot.pause(delay=0.1)

    assert isinstance(pilot.app.screen, SessionScreen)
    for _ in range(40):
      rendered = str(pilot.app.screen.query_one("#results", Static).content)
      if meta.id in rendered:
        break
      await pilot.pause(delay=0.05)
    assert meta.id in rendered
    assert "current:" in rendered


@pytest.mark.asyncio
async def test_remember_screen_requires_confirm(monkeypatch) -> None:
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.remember import RememberScreen
  from textual.widgets import Checkbox, Input, Static

  called: list[bool] = []
  import hugr.api as api
  monkeypatch.setattr(api, "remember", lambda *a, **k: called.append(True) or {"ok": True, "fact": "x"})

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_remember_screen()
    await pilot.pause(delay=0.1)
    assert isinstance(pilot.app.screen, RememberScreen)

    screen = pilot.app.screen
    screen.query_one("#fact-input", Input).value = "Nina prefers early flights"
    await pilot.pause(delay=0.05)

    # Without confirm: submit, expect warning, no api call
    await pilot.press("enter")
    await pilot.pause(delay=0.1)
    assert called == []
    assert "Tick the confirm" in str(screen.query_one("#results", Static).content)

    # With confirm: api fires
    screen.query_one("#confirm-box", Checkbox).value = True
    await pilot.pause(delay=0.05)
    await pilot.press("enter")
    for _ in range(40):
      if called:
        break
      await pilot.pause(delay=0.05)
    assert called == [True]


@pytest.mark.asyncio
async def test_nav_returns_to_ask(monkeypatch) -> None:
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.ask import AskScreen
  from hugr.tui.screens.inbox import InboxScreen

  import hugr.api as api
  monkeypatch.setattr(api, "inbox", lambda: {"tool": "hugr", "command": "inbox", "sources": [], "warnings": []})

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_inbox_screen()
    await pilot.pause(delay=0.05)
    assert isinstance(pilot.app.screen, InboxScreen)
    pilot.app.action_ask_screen()
    await pilot.pause(delay=0.05)
    assert isinstance(pilot.app.screen, AskScreen)

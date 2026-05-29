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


# ---------------------------------------------------------------------------
# SendMailScreen tests (03.5b)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_mail_screen_requires_confirm(monkeypatch) -> None:
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.send_mail import SendMailScreen
  from textual.widgets import Checkbox, Input, Static

  called: list[bool] = []
  import hugr.api as api
  monkeypatch.setattr(
    api,
    "send_mail",
    lambda *a, **k: called.append(True) or {"ok": True, "request": {"to": ["x@x.com"]}, "command": "send mail"},
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_send_mail_screen()
    await pilot.pause(delay=0.1)
    assert isinstance(pilot.app.screen, SendMailScreen)

    screen = pilot.app.screen
    screen.query_one("#mail-to", Input).value = "alice@example.com"
    screen.query_one("#mail-subject", Input).value = "Hello"
    await pilot.pause(delay=0.05)

    # Without confirm: submit via Enter on subject, expect warning, no api call
    screen.query_one("#mail-subject", Input).focus()
    await pilot.press("enter")
    await pilot.pause(delay=0.1)
    assert called == []
    assert "Tick the confirm" in str(screen.query_one("#results", Static).content)

    # With confirm: api fires
    screen.query_one("#confirm-box", Checkbox).value = True
    await pilot.pause(delay=0.05)
    screen.query_one("#mail-subject", Input).focus()
    await pilot.press("enter")
    for _ in range(40):
      if called:
        break
      await pilot.pause(delay=0.05)
    assert called == [True]


@pytest.mark.asyncio
async def test_send_mail_calls_api_with_fields(monkeypatch, tmp_path) -> None:
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "hugr-home"))
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.send_mail import SendMailScreen
  from textual.widgets import Checkbox, Input

  captured: list[tuple] = []
  import hugr.api as api
  monkeypatch.setattr(
    api,
    "send_mail",
    lambda to, subject, body, **k: captured.append((list(to), subject, body))
    or {"ok": True, "request": {"to": list(to)}, "command": "send mail"},
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_send_mail_screen()
    await pilot.pause(delay=0.1)
    assert isinstance(pilot.app.screen, SendMailScreen)

    screen = pilot.app.screen
    screen.query_one("#mail-to", Input).value = "bob@example.com, carol@example.com"
    screen.query_one("#mail-subject", Input).value = "Meeting notes"
    screen.query_one("#confirm-box", Checkbox).value = True
    await pilot.pause(delay=0.05)

    screen.query_one("#mail-subject", Input).focus()
    await pilot.press("enter")
    for _ in range(40):
      if captured:
        break
      await pilot.pause(delay=0.05)

    assert captured, "api.send_mail was not called"
    to_list, subject, _body = captured[0]
    assert "bob@example.com" in to_list
    assert "carol@example.com" in to_list
    assert subject == "Meeting notes"


@pytest.mark.asyncio
async def test_send_mail_writes_last_send_json(monkeypatch, tmp_path) -> None:
  import json
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "hugr-home"))
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
  from hugr import session as session_mod
  meta = session_mod.start_session()
  monkeypatch.setenv("HUGR_SESSION", meta.id)

  from hugr.tui.app import HugrApp
  from hugr.tui.screens.send_mail import SendMailScreen
  from textual.widgets import Checkbox, Input

  import hugr.api as api
  monkeypatch.setattr(
    api,
    "send_mail",
    lambda to, subject, body, **k: {
      "ok": True,
      "command": "send mail",
      "request": {"to": list(to), "subject": subject},
    },
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_send_mail_screen()
    await pilot.pause(delay=0.1)

    screen = pilot.app.screen
    assert isinstance(screen, SendMailScreen)
    screen.query_one("#mail-to", Input).value = "dana@example.com"
    screen.query_one("#mail-subject", Input).value = "Test subject"
    screen.query_one("#confirm-box", Checkbox).value = True
    await pilot.pause(delay=0.05)

    screen.query_one("#mail-subject", Input).focus()
    await pilot.press("enter")
    for _ in range(40):
      last_send = session_mod.session_dir(meta.id) / "last_send.json"
      if last_send.exists():
        break
      await pilot.pause(delay=0.05)

    last_send_path = session_mod.session_dir(meta.id) / "last_send.json"
    assert last_send_path.exists(), "last_send.json was not written"
    doc = json.loads(last_send_path.read_text(encoding="utf-8"))
    assert doc.get("command") == "send mail"


# ---------------------------------------------------------------------------
# SendInviteScreen tests (03.5b)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_invite_screen_requires_confirm(monkeypatch) -> None:
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.send_invite import SendInviteScreen
  from textual.widgets import Checkbox, Input, Static

  called: list[bool] = []
  import hugr.api as api
  monkeypatch.setattr(
    api,
    "send_invite",
    lambda title, **k: called.append(True)
    or {"ok": True, "request": {"subject": title}, "command": "send invite"},
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_send_invite_screen()
    await pilot.pause(delay=0.1)
    assert isinstance(pilot.app.screen, SendInviteScreen)

    screen = pilot.app.screen
    screen.query_one("#invite-title", Input).value = "Sprint planning"
    screen.query_one("#invite-body", Input).value = "Agenda TBD"
    await pilot.pause(delay=0.05)

    # Without confirm, expect warning
    screen.query_one("#invite-body", Input).focus()
    await pilot.press("enter")
    await pilot.pause(delay=0.1)
    assert called == []
    assert "Tick the confirm" in str(screen.query_one("#results", Static).content)

    # With confirm: api fires
    screen.query_one("#confirm-box", Checkbox).value = True
    await pilot.pause(delay=0.05)
    screen.query_one("#invite-body", Input).focus()
    await pilot.press("enter")
    for _ in range(40):
      if called:
        break
      await pilot.pause(delay=0.05)
    assert called == [True]


@pytest.mark.asyncio
async def test_send_invite_calls_api_with_fields(monkeypatch) -> None:
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.send_invite import SendInviteScreen
  from textual.widgets import Checkbox, Input

  captured: list[dict] = []
  import hugr.api as api
  monkeypatch.setattr(
    api,
    "send_invite",
    lambda title, **k: captured.append({"title": title, **k})
    or {"ok": True, "request": {"subject": title}, "command": "send invite"},
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_send_invite_screen()
    await pilot.pause(delay=0.1)
    assert isinstance(pilot.app.screen, SendInviteScreen)

    screen = pilot.app.screen
    screen.query_one("#invite-title", Input).value = "Design review"
    screen.query_one("#invite-start", Input).value = "2026-06-10T14:00"
    screen.query_one("#invite-end", Input).value = "2026-06-10T15:00"
    screen.query_one("#confirm-box", Checkbox).value = True
    await pilot.pause(delay=0.05)

    screen.query_one("#invite-body", Input).focus()
    await pilot.press("enter")
    for _ in range(40):
      if captured:
        break
      await pilot.pause(delay=0.05)

    assert captured, "api.send_invite was not called"
    assert captured[0]["title"] == "Design review"
    assert captured[0].get("start") == "2026-06-10T14:00"
    assert captured[0].get("end") == "2026-06-10T15:00"


# ---------------------------------------------------------------------------
# BookScreen tests (03.5b)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_book_screen_propose_renders_slots(monkeypatch) -> None:
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.book import BookScreen
  from textual.widgets import Input, Static

  import hugr.api as api
  monkeypatch.setattr(
    api,
    "schedule",
    lambda intent, **k: {
      "ok": True,
      "command": "schedule",
      "proposed_subject": intent,
      "slots": [
        {"date": "2026-06-10", "start": "10:00", "end": "11:00"},
        {"date": "2026-06-11", "start": "14:00", "end": "15:00"},
      ],
      "exit_code": 0,
    },
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_book_screen()
    await pilot.pause(delay=0.1)
    assert isinstance(pilot.app.screen, BookScreen)

    screen = pilot.app.screen
    screen.query_one("#book-intent", Input).value = "design review"
    screen.query_one("#book-who", Input).value = "alice@example.com"
    await pilot.pause(delay=0.05)

    # Trigger propose via Enter on date field
    screen.query_one("#book-date", Input).focus()
    await pilot.press("enter")
    for _ in range(40):
      rendered = str(screen.query_one("#results", Static).content)
      if "[0]" in rendered:
        break
      await pilot.pause(delay=0.05)

    rendered = str(screen.query_one("#results", Static).content)
    assert "[0]" in rendered
    assert "[1]" in rendered
    assert "design review" in rendered


@pytest.mark.asyncio
async def test_book_screen_commit_requires_confirm(monkeypatch) -> None:
  from hugr.tui.app import HugrApp
  from hugr.tui.screens.book import BookScreen
  from textual.widgets import Checkbox, Input, Static

  import hugr.api as api
  monkeypatch.setattr(
    api,
    "schedule",
    lambda intent, **k: {
      "ok": True,
      "command": "schedule",
      "proposed_subject": intent,
      "slots": [{"date": "2026-06-10", "start": "10:00", "end": "11:00"}],
      "exit_code": 0,
    },
  )
  committed: list[bool] = []
  monkeypatch.setattr(
    api,
    "schedule_commit",
    lambda intent, **k: committed.append(True)
    or {"ok": True, "command": "send invite", "request": {"subject": intent}},
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_book_screen()
    await pilot.pause(delay=0.1)
    assert isinstance(pilot.app.screen, BookScreen)

    screen = pilot.app.screen
    screen.query_one("#book-intent", Input).value = "planning"
    screen.query_one("#book-who", Input).value = "bob@example.com"
    await pilot.pause(delay=0.05)

    # Propose first
    screen.query_one("#book-date", Input).focus()
    await pilot.press("enter")
    for _ in range(40):
      rendered = str(screen.query_one("#results", Static).content)
      if "[0]" in rendered:
        break
      await pilot.pause(delay=0.05)

    # Without confirm: no commit
    screen.query_one("#book-slot", Input).value = "0"
    screen.query_one("#book-slot", Input).focus()
    await pilot.press("enter")
    await pilot.pause(delay=0.1)
    assert committed == []
    assert "Tick the confirm" in str(screen.query_one("#results", Static).content)

    # With confirm: commit fires
    screen.query_one("#confirm-box", Checkbox).value = True
    await pilot.pause(delay=0.05)
    screen.query_one("#book-slot", Input).focus()
    await pilot.press("enter")
    for _ in range(40):
      if committed:
        break
      await pilot.pause(delay=0.05)
    assert committed == [True]


@pytest.mark.asyncio
async def test_book_writes_last_book_json(monkeypatch, tmp_path) -> None:
  import json
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "hugr-home"))
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
  from hugr import session as session_mod
  meta = session_mod.start_session()
  monkeypatch.setenv("HUGR_SESSION", meta.id)

  from hugr.tui.app import HugrApp
  from hugr.tui.screens.book import BookScreen
  from textual.widgets import Checkbox, Input

  import hugr.api as api
  monkeypatch.setattr(
    api,
    "schedule",
    lambda intent, **k: {
      "ok": True,
      "command": "schedule",
      "proposed_subject": intent,
      "slots": [{"date": "2026-06-10", "start": "10:00", "end": "11:00"}],
      "exit_code": 0,
    },
  )
  monkeypatch.setattr(
    api,
    "schedule_commit",
    lambda intent, **k: {
      "ok": True,
      "command": "send invite",
      "request": {"subject": intent},
    },
  )

  app = HugrApp()
  async with app.run_test(size=(120, 40)) as pilot:
    await pilot.pause()
    await pilot.pause()
    pilot.app.action_book_screen()
    await pilot.pause(delay=0.1)
    assert isinstance(pilot.app.screen, BookScreen)

    screen = pilot.app.screen
    screen.query_one("#book-intent", Input).value = "retro"
    screen.query_one("#book-who", Input).value = "carol@example.com"
    await pilot.pause(delay=0.05)

    # Propose
    screen.query_one("#book-date", Input).focus()
    await pilot.press("enter")
    for _ in range(40):
      from textual.widgets import Static
      rendered = str(screen.query_one("#results", Static).content)
      if "[0]" in rendered:
        break
      await pilot.pause(delay=0.05)

    # Commit
    screen.query_one("#book-slot", Input).value = "0"
    screen.query_one("#confirm-box", Checkbox).value = True
    await pilot.pause(delay=0.05)
    screen.query_one("#book-slot", Input).focus()
    await pilot.press("enter")

    last_book_path = session_mod.session_dir(meta.id) / "last_book.json"
    for _ in range(40):
      if last_book_path.exists():
        break
      await pilot.pause(delay=0.05)

    assert last_book_path.exists(), "last_book.json was not written"
    doc = json.loads(last_book_path.read_text(encoding="utf-8"))
    assert doc.get("command") == "send invite"

"""hugr.tui.screens.book - propose and commit a meeting slot.

Two-step flow:
  1. Propose: fill intent + attendees + duration → hugr.api.schedule()
              → renders proposed slots as a numbered list.
  2. Commit:  user selects a slot index, ticks confirm → hugr.api.schedule_commit()
              → result written to last_book.json in the active session.

The confirm checkbox gates the commit mutation (step 2 only).
"""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Checkbox, Footer, Header, Input, Static


_NAV_MARKUP = (
  "[@click='app.ask_screen()'][a]sk[/]  "
  "[@click='app.find_screen()'][f]ind[/]  "
  "[@click='app.inbox_screen()'][i]nbox[/]  "
  "[@click='app.doctor_screen()'][d]octor[/]  "
  "[@click='app.session_screen()'][s]ession[/]  "
  "[@click='app.remember_screen()'][r]emember[/]  "
  "[@click='app.send_mail_screen()'][m]ail[/]  "
  "[@click='app.book_screen()'][b]ook[/]  "
  "[q]uit"
)


class BookScreen(Screen):
  """Two-step booking: propose slots then commit one."""

  BINDINGS = [
    ("q", "app.quit", "Quit"),
    ("a", "app.ask_screen", "Ask"),
    ("f", "app.find_screen", "Find"),
    ("i", "app.inbox_screen", "Inbox"),
    ("d", "app.doctor_screen", "Doctor"),
    ("s", "app.session_screen", "Session"),
    ("r", "app.remember_screen", "Remember"),
  ]

  def __init__(self, **kwargs: Any) -> None:
    super().__init__(**kwargs)
    self._proposal: dict[str, Any] | None = None

  def compose(self) -> ComposeResult:
    yield Header(show_clock=False)
    yield Static(_NAV_MARKUP, id="nav", markup=True)
    yield Input(placeholder="meeting intent (e.g. 'sprint planning')", id="book-intent")
    yield Input(placeholder="attendees (comma-separated)", id="book-who")
    yield Input(placeholder="duration minutes (default 30)", id="book-duration")
    yield Input(placeholder="date / week (optional)", id="book-date")
    yield Input(placeholder="slot index to commit (after propose)", id="book-slot")
    yield Checkbox("Confirm: this will create the calendar event", id="confirm-box")
    yield Static(
      "(fill intent+attendees, press Enter to propose; fill slot index, tick confirm, Enter to book)",
      id="results",
    )
    yield Footer()

  def on_mount(self) -> None:
    self.query_one("#book-intent", Input).focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    widget_id = event.input.id
    if widget_id == "book-intent":
      self.query_one("#book-who", Input).focus()
      return
    if widget_id == "book-who":
      self.query_one("#book-duration", Input).focus()
      return
    if widget_id == "book-duration":
      self.query_one("#book-date", Input).focus()
      return
    if widget_id == "book-date":
      # Trigger propose when Enter is pressed on date
      self._try_propose()
      return
    if widget_id == "book-slot":
      self._try_commit()
      return

  def _try_propose(self) -> None:
    intent = self.query_one("#book-intent", Input).value.strip()
    who_raw = self.query_one("#book-who", Input).value.strip()
    if not intent or not who_raw:
      self.query_one("#results", Static).update("[yellow]intent and attendees are required.[/yellow]")
      return
    who = [w.strip() for w in who_raw.split(",") if w.strip()]
    dur_raw = self.query_one("#book-duration", Input).value.strip()
    duration = int(dur_raw) if dur_raw.isdigit() else 30
    date = self.query_one("#book-date", Input).value.strip() or None
    self.query_one("#results", Static).update("Fetching slots...")
    self.run_worker(
      lambda: self._propose(intent, who, duration, date),
      name="book_propose",
      group="book",
      exclusive=True,
      exit_on_error=False,
      thread=True,
    )

  def _propose(
    self,
    intent: str,
    who: list[str],
    duration: int,
    date: str | None,
  ) -> None:
    import hugr.api as api
    try:
      doc = api.schedule(intent, who=who, duration_minutes=duration, date=date)
    except Exception as exc:
      self.app.call_from_thread(
        self._render_error,
        f"{type(exc).__name__}: {exc}",
      )
      return
    self.app.call_from_thread(self._render_proposal, doc)

  def _render_proposal(self, doc: dict[str, Any]) -> None:
    self._proposal = doc
    widget = self.query_one("#results", Static)
    if not doc.get("ok"):
      err = doc.get("error") or {}
      widget.update(f"[red]propose failed:[/red] {err.get('message', 'unknown error')}")
      return
    slots = doc.get("slots") or []
    if not slots:
      widget.update("[yellow]no slots found[/yellow]")
      return
    lines = [f"proposed: {doc.get('proposed_subject') or ''}", ""]
    for idx, slot in enumerate(slots):
      label = " - ".join(
        str(slot.get(k))
        for k in ("date", "day", "start", "from", "end", "to")
        if slot.get(k)
      )
      lines.append(f"  [{idx}] {label}".rstrip())
    lines.append("")
    lines.append("Enter slot index above, tick confirm, press Enter to book.")
    widget.update("\n".join(lines))
    self.query_one("#book-slot", Input).focus()

  def _try_commit(self) -> None:
    if self._proposal is None:
      self.query_one("#results", Static).update("[yellow]Run propose first (press Enter in date field).[/yellow]")
      return
    slot_raw = self.query_one("#book-slot", Input).value.strip()
    if not slot_raw.isdigit():
      self.query_one("#results", Static).update("[yellow]Enter a numeric slot index.[/yellow]")
      return
    slot_idx = int(slot_raw)
    if not self.query_one("#confirm-box", Checkbox).value:
      self.query_one("#results", Static).update("[yellow]Tick the confirm box first.[/yellow]")
      return
    slots = self._proposal.get("slots") or []
    if slot_idx < 0 or slot_idx >= len(slots):
      self.query_one("#results", Static).update(
        f"[yellow]Slot {slot_idx} not in proposal (found {len(slots)}).[/yellow]"
      )
      return
    intent = self.query_one("#book-intent", Input).value.strip()
    who_raw = self.query_one("#book-who", Input).value.strip()
    who = [w.strip() for w in who_raw.split(",") if w.strip()]
    slot = slots[slot_idx]
    self.query_one("#results", Static).update("Booking slot...")
    self.run_worker(
      lambda: self._commit(intent, who, slot),
      name="book_commit",
      group="book",
      exclusive=True,
      exit_on_error=False,
      thread=True,
    )

  def _commit(self, intent: str, who: list[str], slot: dict[str, Any]) -> None:
    import hugr.api as api
    try:
      doc = api.schedule_commit(intent, who=who, slot=slot)
    except Exception as exc:
      self.app.call_from_thread(
        self._render_error,
        f"{type(exc).__name__}: {exc}",
      )
      return
    self._write_session(doc)
    self.app.call_from_thread(self._render_commit_doc, doc)

  def _write_session(self, doc: dict[str, Any]) -> None:
    import hugr.session as session_mod
    sid = session_mod.current_session_id()
    if not sid:
      return
    try:
      session_mod._write_json(  # type: ignore[attr-defined]
        session_mod.session_dir(sid) / "last_book.json",
        doc,
      )
    except Exception:
      pass

  def _render_commit_doc(self, doc: dict[str, Any]) -> None:
    widget = self.query_one("#results", Static)
    if doc.get("ok"):
      req = doc.get("request") or {}
      widget.update(f"[green]booked:[/green] {req.get('subject') or '(event)'}")
      self.query_one("#book-slot", Input).value = ""
      self.query_one("#confirm-box", Checkbox).value = False
      self._proposal = None
    else:
      err = doc.get("error") or {}
      widget.update(f"[red]commit failed:[/red] {err.get('message', 'unknown error')}")

  def _render_error(self, detail: str) -> None:
    self.query_one("#results", Static).update(f"[red]Book failed[/red]\n{detail}")

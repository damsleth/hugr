"""hugr.tui.screens.send_invite - compose and send a calendar invite.

Fields: title (subject), start, end (or duration), location, body.
Attendees via owa-cal create are a known upstream gap (owa-tools v0.2);
the screen still gathers title/time/location for solo/room events.
Confirmation checkbox gates the mutation before calling hugr.api.send_invite().
Result envelope is written to last_send.json in the active session dir.
"""

from __future__ import annotations

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
  "[@click='app.send_invite_screen()'][v] invite[/]  "
  "[q]uit"
)

_FIELDS = ["invite-title", "invite-start", "invite-end", "invite-location", "invite-body"]


class SendInviteScreen(Screen):
  """Fill title/start/end, tick confirm, press Enter to create the event."""

  BINDINGS = [
    ("q", "app.quit", "Quit"),
    ("a", "app.ask_screen", "Ask"),
    ("f", "app.find_screen", "Find"),
    ("i", "app.inbox_screen", "Inbox"),
    ("d", "app.doctor_screen", "Doctor"),
    ("s", "app.session_screen", "Session"),
    ("r", "app.remember_screen", "Remember"),
  ]

  def compose(self) -> ComposeResult:
    yield Header(show_clock=False)
    yield Static(_NAV_MARKUP, id="nav", markup=True)
    yield Input(placeholder="title / subject", id="invite-title")
    yield Input(placeholder="start (e.g. 2026-06-01T10:00)", id="invite-start")
    yield Input(placeholder="end   (e.g. 2026-06-01T11:00)", id="invite-end")
    yield Input(placeholder="location (optional)", id="invite-location")
    yield Input(placeholder="body / description (optional)", id="invite-body")
    yield Checkbox("Confirm: this will create a calendar event", id="confirm-box")
    yield Static("(fill fields, tick confirm, press Enter in body)", id="results")
    yield Footer()

  def on_mount(self) -> None:
    self.query_one("#invite-title", Input).focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    widget_id = event.input.id
    idx = _FIELDS.index(widget_id) if widget_id in _FIELDS else -1
    if idx >= 0 and idx < len(_FIELDS) - 1:
      # Advance to next field
      self.query_one(f"#{_FIELDS[idx + 1]}", Input).focus()
      return
    # Enter on last field (body) triggers submit
    if widget_id == "invite-body":
      self._try_send()

  def _try_send(self) -> None:
    title = self.query_one("#invite-title", Input).value.strip()
    start = self.query_one("#invite-start", Input).value.strip() or None
    end = self.query_one("#invite-end", Input).value.strip() or None
    location = self.query_one("#invite-location", Input).value.strip() or None
    body = self.query_one("#invite-body", Input).value.strip() or None
    if not title:
      self.query_one("#results", Static).update("[yellow]title is required.[/yellow]")
      return
    if not self.query_one("#confirm-box", Checkbox).value:
      self.query_one("#results", Static).update("[yellow]Tick the confirm box first.[/yellow]")
      return
    self.query_one("#results", Static).update("Creating event...")
    self.run_worker(
      lambda: self._create(title, start, end, location, body),
      name="send_invite",
      group="send_invite",
      exclusive=True,
      exit_on_error=False,
      thread=True,
    )

  def _create(
    self,
    title: str,
    start: str | None,
    end: str | None,
    location: str | None,
    body: str | None,
  ) -> None:
    import hugr.api as api
    try:
      doc = api.send_invite(title, start=start, end=end, location=location, body=body)
    except Exception as exc:
      self.app.call_from_thread(
        self._render_error,
        f"{type(exc).__name__}: {exc}",
      )
      return
    self._write_session(doc)
    self.app.call_from_thread(self._render_doc, doc)

  def _write_session(self, doc: dict) -> None:
    import hugr.session as session_mod
    sid = session_mod.current_session_id()
    if not sid:
      return
    try:
      session_mod._write_json(  # type: ignore[attr-defined]
        session_mod.session_dir(sid) / "last_send.json",
        doc,
      )
    except Exception:
      pass

  def _render_doc(self, doc: dict) -> None:
    widget = self.query_one("#results", Static)
    if doc.get("ok"):
      req = doc.get("request") or {}
      widget.update(f"[green]created:[/green] {req.get('subject') or '(event)'}")
      for fid in _FIELDS:
        self.query_one(f"#{fid}", Input).value = ""
      self.query_one("#confirm-box", Checkbox).value = False
    else:
      err = doc.get("error") or {}
      widget.update(f"[red]failed:[/red] {err.get('message', 'unknown error')}")

  def _render_error(self, detail: str) -> None:
    self.query_one("#results", Static).update(f"[red]Create event failed[/red]\n{detail}")

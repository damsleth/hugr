"""hugr.tui.screens.send_mail - compose and send a mail message.

Fields: to (comma-split), subject, body (multiline).
Confirmation checkbox gates the mutation before calling hugr.api.send_mail().
Result envelope is written to last_send.json in the active session dir.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Checkbox, Footer, Header, Input, Static, TextArea


_NAV_MARKUP = (
  "[@click='app.ask_screen()'][a]sk[/]  "
  "[@click='app.find_screen()'][f]ind[/]  "
  "[@click='app.inbox_screen()'][i]nbox[/]  "
  "[@click='app.doctor_screen()'][d]octor[/]  "
  "[@click='app.session_screen()'][s]ession[/]  "
  "[@click='app.remember_screen()'][r]emember[/]  "
  "[@click='app.send_mail_screen()'][m]ail[/]  "
  "[q]uit"
)


class SendMailScreen(Screen):
  """Fill to/subject/body, tick confirm, press Enter on subject to send."""

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
    yield Input(placeholder="to (comma-separated)", id="mail-to")
    yield Input(placeholder="subject", id="mail-subject")
    yield TextArea(id="mail-body")
    yield Checkbox("Confirm: this will send the message", id="confirm-box")
    yield Static("(fill fields, tick confirm, press Enter in subject)", id="results")
    yield Footer()

  def on_mount(self) -> None:
    self.query_one("#mail-to", Input).focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    if event.input.id == "mail-to":
      self.query_one("#mail-subject", Input).focus()
      return
    # Enter on subject line triggers send
    if event.input.id == "mail-subject":
      self._try_send()

  def _try_send(self) -> None:
    to_raw = self.query_one("#mail-to", Input).value.strip()
    subject = self.query_one("#mail-subject", Input).value.strip()
    body = self.query_one("#mail-body", TextArea).text.strip()
    if not to_raw or not subject:
      self.query_one("#results", Static).update("[yellow]to and subject are required.[/yellow]")
      return
    if not self.query_one("#confirm-box", Checkbox).value:
      self.query_one("#results", Static).update("[yellow]Tick the confirm box first.[/yellow]")
      return
    recipients = [r.strip() for r in to_raw.split(",") if r.strip()]
    self.query_one("#results", Static).update("Sending...")
    self.run_worker(
      lambda: self._send(recipients, subject, body),
      name="send_mail",
      group="send_mail",
      exclusive=True,
      exit_on_error=False,
      thread=True,
    )

  def _send(self, to: list[str], subject: str, body: str) -> None:
    import hugr.api as api
    try:
      doc = api.send_mail(to, subject, body)
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
      widget.update(f"[green]sent:[/green] → {','.join(req.get('to') or [])}")
      self.query_one("#mail-to", Input).value = ""
      self.query_one("#mail-subject", Input).value = ""
      self.query_one("#mail-body", TextArea).clear()
      self.query_one("#confirm-box", Checkbox).value = False
    else:
      err = doc.get("error") or {}
      widget.update(f"[red]failed:[/red] {err.get('message', 'unknown error')}")

  def _render_error(self, detail: str) -> None:
    self.query_one("#results", Static).update(f"[red]Send failed[/red]\n{detail}")

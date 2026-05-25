"""hugr.tui.screens.remember - capture a fact into the ledger.

The simplest 03.5 mutation surface: one textarea + a confirm checkbox.
SendMailScreen and SendInviteScreen are deferred to 03.5b; their form
shape is a better fit for the web UI than the TUI.
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
  "[q]uit"
)


class RememberScreen(Screen):
  """Type a fact, tick confirm, submit. Calls hugr.api.remember()."""

  BINDINGS = [
    ("q", "app.quit", "Quit"),
    ("a", "app.ask_screen", "Ask"),
    ("f", "app.find_screen", "Find"),
    ("i", "app.inbox_screen", "Inbox"),
    ("d", "app.doctor_screen", "Doctor"),
    ("s", "app.session_screen", "Session"),
  ]

  def compose(self) -> ComposeResult:
    yield Header(show_clock=False)
    yield Static(_NAV_MARKUP, id="nav", markup=True)
    yield Input(placeholder="fact to remember", id="fact-input")
    yield Checkbox("Confirm: this writes to the ledger", id="confirm-box")
    yield Static("(type a fact, tick confirm, press Enter)", id="results")
    yield Footer()

  def on_mount(self) -> None:
    self.query_one("#fact-input", Input).focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    fact = event.value.strip()
    if not fact:
      return
    if not self.query_one("#confirm-box", Checkbox).value:
      self.query_one("#results", Static).update("[yellow]Tick the confirm box first.[/yellow]")
      return
    self.query_one("#results", Static).update("Remembering...")
    self.run_worker(
      lambda: self._remember(fact),
      name="remember",
      group="remember",
      exclusive=True,
      exit_on_error=False,
      thread=True,
    )

  def _remember(self, fact: str) -> None:
    import hugr.api as api
    try:
      doc = api.remember(fact, yes=True)
    except Exception as exc:
      self.app.call_from_thread(
        self._render_error,
        f"{type(exc).__name__}: {exc}",
      )
      return
    self.app.call_from_thread(self._render_doc, doc)

  def _render_doc(self, doc: dict) -> None:
    widget = self.query_one("#results", Static)
    if doc.get("ok"):
      widget.update(f"[green]remembered:[/green] {doc.get('fact')}")
      self.query_one("#fact-input", Input).value = ""
      self.query_one("#confirm-box", Checkbox).value = False
    else:
      err = doc.get("error") or {}
      widget.update(f"[red]failed:[/red] {err.get('message', 'unknown error')}")

  def _render_error(self, detail: str) -> None:
    self.query_one("#results", Static).update(f"[red]Remember failed[/red]\n{detail}")

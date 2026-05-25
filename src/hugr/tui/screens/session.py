"""hugr.tui.screens.session - active session + working set summary."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from hugr.tui.screens._render import render_session_doc


_NAV_MARKUP = (
  "[@click='app.ask_screen()'][a]sk[/]  "
  "[@click='app.find_screen()'][f]ind[/]  "
  "[@click='app.inbox_screen()'][i]nbox[/]  "
  "[@click='app.doctor_screen()'][d]octor[/]  "
  "[@click='app.session_screen()'][s]ession[/]  "
  "[q]uit"
)


class SessionScreen(Screen):
  """Show sessions (active + others) and the active working set."""

  BINDINGS = [
    ("q", "app.quit", "Quit"),
    ("a", "app.ask_screen", "Ask"),
    ("f", "app.find_screen", "Find"),
    ("i", "app.inbox_screen", "Inbox"),
    ("d", "app.doctor_screen", "Doctor"),
    ("r", "refresh", "Refresh"),
  ]

  def compose(self) -> ComposeResult:
    yield Header(show_clock=False)
    yield Static(_NAV_MARKUP, id="nav", markup=True)
    yield Static("Loading sessions...", id="results")
    yield Footer()

  def on_mount(self) -> None:
    self._load()

  def action_refresh(self) -> None:
    self._load()

  def _load(self) -> None:
    self.run_worker(
      self._fetch,
      name="session-status",
      group="session-status",
      exclusive=True,
      exit_on_error=False,
      thread=True,
    )

  def _fetch(self) -> None:
    from hugr import session as session_mod
    try:
      doc = session_mod.status()
    except Exception as exc:
      self.app.call_from_thread(
        self._render_error,
        f"{type(exc).__name__}: {exc}",
      )
      return
    self.app.call_from_thread(self._render_doc, doc)

  def _render_doc(self, doc: dict) -> None:
    self.query_one("#results", Static).update(render_session_doc(doc))

  def _render_error(self, detail: str) -> None:
    self.query_one("#results", Static).update(f"[red]Session status failed[/red]\n{detail}")

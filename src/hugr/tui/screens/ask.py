"""hugr.tui.screens.ask - the Ask screen.

Calls hugr.api.recall() for fused cross-tool search and renders the
result document in the results pane. Worker name is "recall".

Nav keys f/i/d/s push the matching screens; q quits.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static

from hugr.tui.screens._render import render_recall_doc


_PLACEHOLDER_TEXT = "Press Enter to search"

_NAV_MARKUP = (
  "[@click='app.ask_screen()'][a]sk[/]  "
  "[@click='app.find_screen()'][f]ind[/]  "
  "[@click='app.inbox_screen()'][i]nbox[/]  "
  "[@click='app.doctor_screen()'][d]octor[/]  "
  "[@click='app.session_screen()'][s]ession[/]  "
  "[@click='app.remember_screen()'][r]emember[/]  "
  "[q]uit"
)


class AskScreen(Screen):
  """The Ask screen - default TUI surface."""

  BINDINGS = [
    ("q", "app.quit", "Quit"),
    ("f", "app.find_screen", "Find"),
    ("i", "app.inbox_screen", "Inbox"),
    ("d", "app.doctor_screen", "Doctor"),
    ("s", "app.session_screen", "Session"),
    ("r", "app.remember_screen", "Remember"),
  ]

  def compose(self) -> ComposeResult:
    yield Header(show_clock=False)
    yield Static(_NAV_MARKUP, id="nav", markup=True)
    yield Input(placeholder="ask: what did Nina say about Easter dinner?", id="query-input")
    yield Static(_PLACEHOLDER_TEXT, id="results")
    yield Footer()

  def on_mount(self) -> None:
    self.query_one("#query-input", Input).focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    query = event.value.strip()
    if not query:
      return
    results_widget = self.query_one("#results", Static)
    results_widget.update("Searching...")
    self.run_worker(
      lambda: self._run_recall(query),
      name="recall",
      group="recall",
      exclusive=True,
      exit_on_error=False,
      thread=True,
    )

  def _run_recall(self, query: str) -> None:
    import hugr.api as api
    try:
      doc = api.recall(query)
    except Exception as exc:
      self.app.call_from_thread(
        self._render_error,
        1,
        f"{type(exc).__name__}: {exc}",
      )
      return
    self.app.call_from_thread(self._render_doc, doc)

  def _render_doc(self, doc: dict) -> None:
    results_widget = self.query_one("#results", Static)
    results_widget.update(render_recall_doc(doc) or "(no results)")

  def _render_error(self, exit_code: int, detail: str) -> None:
    results_widget = self.query_one("#results", Static)
    results_widget.update(f"[red]Query failed (exit {exit_code})[/red]\n{detail}")

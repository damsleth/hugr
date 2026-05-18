"""hugr.tui.screens.ask - the Ask screen.

Layout:
  - Header: app title + doctor status
  - Nav bar: [a]sk [f]ind [i]nbox [r]emember [d]octor [q]uit
  - Input: query field
  - Results: ranked result list (raw text from hugr.api.yaams_query)

TODO (01.2): replace yaams_query call with hugr.api.recall() once that
function ships in plan 01.2.  The ask() function will return a fused
cross-tool ranked result instead of the raw yaams passthrough bytes.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Static


_PLACEHOLDER_TEXT = "Press Enter to search"

_NAV_MARKUP = (
  "[@click='app.ask_screen()'][a]sk[/]  "
  "[@click='app.bell()'][f]ind[/]  "
  "[@click='app.bell()'][i]nbox[/]  "
  "[@click='app.bell()'][r]emember[/]  "
  "[@click='app.bell()'][d]octor[/]  "
  "[@click='app.bell()'][q]uit[/]"
)


class AskScreen(Screen):
  """Ask screen - the default TUI surface.

  Provides a query input and a result pane.  Calls hugr.api.yaams_query
  on Enter.  Nav keys for other screens ring the bell in 03.1; they wire
  up to real screens in 03.2.
  """

  BINDINGS = [
    ("q", "app.quit", "Quit"),
    ("f", "app.bell", "Find (03.2)"),
    ("i", "app.bell", "Inbox (03.2)"),
    ("r", "app.bell", "Remember (03.2)"),
    ("d", "app.bell", "Doctor (03.2)"),
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
      lambda: self._run_query(query),
      name="yaams-query",
      group="yaams-query",
      exclusive=True,
      exit_on_error=False,
      thread=True,
    )

  def _run_query(self, query: str) -> None:
    """Call hugr.api.yaams_query and render the raw result.

    TODO (01.2): swap for hugr.api.recall(query) once plan 01.2 ships.
    ask() will return a fused, ranked cross-tool result instead of raw
    yaams passthrough bytes.
    """
    import hugr.api as api

    try:
      exit_code, stdout_bytes = api.yaams_query([query])
    except Exception as exc:
      self.app.call_from_thread(
        self._render_query_error,
        1,
        f"{type(exc).__name__}: {exc}",
      )
      return

    self.app.call_from_thread(
      self._render_query_result,
      exit_code,
      stdout_bytes,
    )

  def _render_query_result(self, exit_code: int, stdout_bytes: bytes) -> None:
    """Render query output on the Textual app thread."""
    results_widget = self.query_one("#results", Static)

    if exit_code != 0 or not stdout_bytes:
      self._render_query_error(
        exit_code,
        stdout_bytes.decode("utf-8", errors="replace"),
      )
      return

    text = stdout_bytes.decode("utf-8", errors="replace").strip()
    if not text:
      results_widget.update("(no results)")
    else:
      results_widget.update(text)

  def _render_query_error(self, exit_code: int, detail: str) -> None:
    """Render a query failure on the Textual app thread."""
    results_widget = self.query_one("#results", Static)
    results_widget.update(f"[red]Query failed (exit {exit_code})[/red]\n{detail}")

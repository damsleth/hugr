"""hugr.tui.screens.find - typed search across the suite."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, Select, Static

from hugr.tui.screens._render import render_find_doc


_KINDS = [
  ("person", "person"),
  ("event", "event"),
  ("message", "message"),
  ("note", "note"),
  ("file", "file"),
]

_NAV_MARKUP = (
  "[@click='app.ask_screen()'][a]sk[/]  "
  "[@click='app.find_screen()'][f]ind[/]  "
  "[@click='app.inbox_screen()'][i]nbox[/]  "
  "[@click='app.doctor_screen()'][d]octor[/]  "
  "[@click='app.session_screen()'][s]ession[/]  "
  "[q]uit"
)


class FindScreen(Screen):
  """Typed search. Pick a kind, enter a query."""

  BINDINGS = [
    ("q", "app.quit", "Quit"),
    ("a", "app.ask_screen", "Ask"),
    ("i", "app.inbox_screen", "Inbox"),
    ("d", "app.doctor_screen", "Doctor"),
    ("s", "app.session_screen", "Session"),
  ]

  def compose(self) -> ComposeResult:
    yield Header(show_clock=False)
    yield Static(_NAV_MARKUP, id="nav", markup=True)
    with Horizontal(id="find-row"):
      yield Select(_KINDS, id="kind-select", value="person", allow_blank=False)
      yield Input(placeholder="find query", id="find-input")
    yield Static("(enter a query)", id="results")
    yield Footer()

  def on_mount(self) -> None:
    self.query_one("#find-input", Input).focus()

  def on_input_submitted(self, event: Input.Submitted) -> None:
    query = event.value.strip()
    if not query:
      return
    kind = self.query_one("#kind-select", Select).value or "person"
    self.query_one("#results", Static).update(f"Searching {kind}...")
    self.run_worker(
      lambda: self._run_find(str(kind), query),
      name="find",
      group="find",
      exclusive=True,
      exit_on_error=False,
      thread=True,
    )

  def _run_find(self, kind: str, query: str) -> None:
    import hugr.api as api
    try:
      doc = api.find(kind, query)
    except Exception as exc:
      self.app.call_from_thread(
        self._render_error,
        f"{type(exc).__name__}: {exc}",
      )
      return
    self.app.call_from_thread(self._render_doc, doc)

  def _render_doc(self, doc: dict) -> None:
    self.query_one("#results", Static).update(render_find_doc(doc))

  def _render_error(self, detail: str) -> None:
    self.query_one("#results", Static).update(f"[red]Find failed[/red]\n{detail}")

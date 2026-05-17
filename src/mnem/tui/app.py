"""mnem.tui.app - Textual App entry point.

Run with:  mnem tui
Or directly:  python -m mnem.tui.app

Default screen: AskScreen.

03.1 scope: Ask screen only.  Inbox, Find, Doctor, Session land in 03.2.
"""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

from mnem.tui.screens.ask import AskScreen

CSS = """
#nav {
  background: $primary-darken-2;
  color: $text;
  padding: 0 1;
  height: 1;
}

#query-input {
  margin: 1 0 0 0;
}

#results {
  border: solid $primary;
  height: 1fr;
  padding: 1;
  overflow-y: auto;
}
"""


class MnemApp(App):
  """The mnem terminal UI.

  Keyboard-first.  Default screen is AskScreen.
  Other screens (inbox, find, doctor, session) wire up in 03.2.
  """

  TITLE = "mnem"
  SUB_TITLE = "doctor: ok"
  CSS = CSS

  BINDINGS = [
    ("q", "quit", "Quit"),
    ("ctrl+c", "quit", "Quit"),
  ]

  def on_mount(self) -> None:
    self.push_screen(AskScreen())

  def action_ask_screen(self) -> None:
    """Navigate to the Ask screen (already the default in 03.1)."""
    # pop everything except the base screen, then push Ask
    # In 03.1 we only have one screen, so this is a no-op safety guard.
    pass


def run() -> None:
  """Launch the TUI.  Called by ``mnem tui``."""
  MnemApp().run()


if __name__ == "__main__":
  run()

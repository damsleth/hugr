"""hugr.tui.app - Textual App entry point.

Run with:  hugr tui
Or directly:  python -m hugr.tui.app

Default screen: AskScreen. Navigation via a/f/i/d/s keys pushes the
matching screen.
"""

from __future__ import annotations

from textual.app import App

from hugr.tui.screens.ask import AskScreen
from hugr.tui.screens.doctor import DoctorScreen
from hugr.tui.screens.find import FindScreen
from hugr.tui.screens.inbox import InboxScreen
from hugr.tui.screens.session import SessionScreen

CSS = """
#nav {
  background: $primary-darken-2;
  color: $text;
  padding: 0 1;
  height: 1;
}

#query-input,
#find-input {
  margin: 1 0 0 0;
}

#find-row {
  height: 3;
}

#results {
  border: solid $primary;
  height: 1fr;
  padding: 1;
  overflow-y: auto;
}
"""


class HugrApp(App):
  """The hugr terminal UI.

  Keyboard-first. Default screen is AskScreen.
  """

  TITLE = "hugr"
  SUB_TITLE = "doctor: ok"
  CSS = CSS

  BINDINGS = [
    ("ctrl+c", "quit", "Quit"),
  ]

  def on_mount(self) -> None:
    self.push_screen(AskScreen())

  def _navigate_to(self, screen_cls: type) -> None:
    """Replace the active screen with a fresh instance of *screen_cls*."""
    if isinstance(self.screen, screen_cls):
      return
    self.pop_screen() if len(self.screen_stack) > 1 else None
    self.push_screen(screen_cls())

  def action_ask_screen(self) -> None:
    self._navigate_to(AskScreen)

  def action_find_screen(self) -> None:
    self._navigate_to(FindScreen)

  def action_inbox_screen(self) -> None:
    self._navigate_to(InboxScreen)

  def action_doctor_screen(self) -> None:
    self._navigate_to(DoctorScreen)

  def action_session_screen(self) -> None:
    self._navigate_to(SessionScreen)


def run() -> None:
  """Launch the TUI. Called by ``hugr tui``."""
  HugrApp().run()


if __name__ == "__main__":
  run()

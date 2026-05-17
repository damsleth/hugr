"""``mnem tui`` - launch the interactive Textual terminal UI.

Requires the [tui] extra:

    pipx install "mnem-suite[tui]"

If textual is not installed the command prints a friendly message and
exits with code 4 (EXIT_NOT_FOUND per CONVENTIONS.md).
"""

from __future__ import annotations

import sys

import click


@click.command("tui")
def run_tui() -> None:
  """Launch the interactive Textual TUI (requires [tui] extra)."""
  try:
    from mnem.tui.app import run
  except ImportError:
    click.echo(
      'tui extra not installed; pipx install "mnem-suite[tui]"',
      err=True,
    )
    sys.exit(4)

  run()

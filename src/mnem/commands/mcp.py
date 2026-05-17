"""``mnem mcp`` - serve mnem.api as MCP tools.

Requires the [mcp] extra:

    pipx install "mnem-suite[mcp]"

If the mcp package is not installed the command prints a friendly message
and exits with code 4 (EXIT_NOT_FOUND per CONVENTIONS.md).

Currently supports ``--stdio`` only (plan 04.1).
HTTP transport (``--http``) is plan 04.6.
"""

from __future__ import annotations

import sys

import click


@click.command("mcp")
@click.option(
  "--stdio",
  "transport",
  flag_value="stdio",
  default=True,
  help="Serve over stdio (default, for Claude Code / local MCP clients).",
)
@click.option(
  "--http",
  "transport",
  flag_value="http",
  help="Serve over HTTP (plan 04.6; not yet implemented).",
)
def run_mcp(transport: str) -> None:
  """Serve mnem.api as MCP tools (requires [mcp] extra)."""
  try:
    import mcp  # noqa: F401 - presence check only
  except ImportError:
    click.echo(
      'mcp extra not installed; pipx install "mnem-suite[mcp]"',
      err=True,
    )
    sys.exit(4)

  if transport == "http":
    click.echo("mnem mcp --http is not yet implemented (plan 04.6).", err=True)
    sys.exit(4)

  # stdio transport
  import asyncio
  from mnem.mcp.stdio import run
  asyncio.run(run())

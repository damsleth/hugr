"""Launch ``hugr server``."""

from __future__ import annotations

import sys

import click

from hugr.server.auth import bind_refusal_message, can_bind


def launch(*, host: str = "127.0.0.1", port: int = 7777, mcp: bool = False, insecure: bool = False) -> None:
  if not can_bind(host, insecure=insecure):
    click.echo(bind_refusal_message(host), err=True)
    sys.exit(3)

  try:
    import uvicorn
    from hugr.web.app import create_app
    app = create_app()
  except (ImportError, RuntimeError):
    click.echo('server extra not installed; pipx install "hugr-cli[server]"', err=True)
    sys.exit(4)

  if mcp:
    click.echo("hugr server --mcp HTTP transport is not yet implemented; continuing without MCP.", err=True)

  uvicorn.run(app, host=host, port=port)

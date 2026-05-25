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
    try:
      from hugr.mcp.http import mount as mount_mcp
    except ImportError:
      click.echo(
        '--mcp requires the mcp extra; pipx install "hugr-cli[mcp]"',
        err=True,
      )
      sys.exit(4)

    manager = mount_mcp(app)

    # The streamable HTTP manager owns a task group that has to be
    # entered for the lifetime of the app. Hook it into Starlette's
    # lifespan via add_event_handler so it starts before the first
    # request and stops cleanly on shutdown.
    import contextlib

    stack = contextlib.AsyncExitStack()

    async def _start() -> None:
      await stack.__aenter__()
      await stack.enter_async_context(manager.run())

    async def _stop() -> None:
      await stack.__aexit__(None, None, None)

    app.add_event_handler("startup", _start)
    app.add_event_handler("shutdown", _stop)

  uvicorn.run(app, host=host, port=port)

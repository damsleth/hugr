"""``mnem web`` - launch the FastAPI web surface.

Requires the [web] extra:

    pipx install "mnem-suite[web]"
"""

from __future__ import annotations

import os
import sys

import click


def _is_loopback(host: str) -> bool:
  return host in {"127.0.0.1", "localhost", "::1"}


@click.command("web")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=7777, show_default=True, type=int)
@click.option("--public", "public", is_flag=True, default=False, help="Allow non-loopback bind with MNEM_WEB_TOKEN.")
def run_web(host: str, port: int, public: bool) -> None:
  launch(host=host, port=port, public=public)


def launch(*, host: str = "127.0.0.1", port: int = 7777, public: bool = False) -> None:
  if not _is_loopback(host) and not public:
    click.echo("refusing non-loopback bind without --public", err=True)
    sys.exit(3)
  if public and not os.environ.get("MNEM_WEB_TOKEN"):
    click.echo("mnem web --public requires MNEM_WEB_TOKEN", err=True)
    sys.exit(3)

  try:
    import uvicorn
    from mnem.web.app import create_app
    app = create_app()
  except (ImportError, RuntimeError):
    click.echo('web extra not installed; pipx install "mnem-suite[web]"', err=True)
    sys.exit(4)

  uvicorn.run(app, host=host, port=port)

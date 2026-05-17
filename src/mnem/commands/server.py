"""``mnem server`` - deploy/runtime entrypoint."""

from __future__ import annotations

import click


@click.command("server")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=7777, show_default=True, type=int)
@click.option("--mcp", is_flag=True, default=False, help="Also expose MCP HTTP transport when available.")
@click.option("--insecure", is_flag=True, default=False, help="Allow non-loopback bind without an auth proxy.")
def run_server(host: str, port: int, mcp: bool, insecure: bool) -> None:
  from mnem.server.app import launch
  launch(host=host, port=port, mcp=mcp, insecure=insecure)

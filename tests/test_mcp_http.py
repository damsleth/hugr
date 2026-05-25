"""Plan 04.6 tests: HTTP transport for hugr mcp.

Goal: prove the module imports, builds tools through the shared
``_server.build_server`` path, and that ``mount()`` registers routes
on a FastAPI app. The full Streamable HTTP round-trip is exercised by
the upstream mcp SDK's own test suite; here we cover the wiring.
"""

from __future__ import annotations

import pytest

pytest.importorskip("mcp", reason="mcp extra not installed")
pytest.importorskip("fastapi", reason="fastapi extra not installed")


def test_build_server_lists_tools():
  from hugr.mcp._server import build_server

  server = build_server()
  # The Server keeps registered handlers; tools come from build_tool_defs
  from hugr.mcp.tools import build_tool_defs

  tools = build_tool_defs()
  names = {t.name for t in tools}
  assert "hugr.recall" in names
  assert "hugr.find" in names
  assert "hugr.inbox" in names
  assert server.name == "hugr"


def test_mount_registers_mcp_route_on_fastapi_app():
  from fastapi import FastAPI

  from hugr.mcp.http import mount

  app = FastAPI()
  manager = mount(app, path="/mcp")
  routes = {getattr(r, "path", None) for r in app.routes}
  assert "/mcp" in routes
  assert "/mcp/" in routes
  assert manager is not None


def test_mount_uses_custom_path():
  from fastapi import FastAPI

  from hugr.mcp.http import mount

  app = FastAPI()
  mount(app, path="/api/mcp")
  routes = {getattr(r, "path", None) for r in app.routes}
  assert "/api/mcp" in routes


def test_cli_mcp_http_flag_routes_to_http_run(monkeypatch):
  """Verify the CLI dispatch picks the HTTP entry point."""
  import sys

  from click.testing import CliRunner

  from hugr.cli import cli

  calls: dict[str, object] = {}

  async def fake_http(*, host: str, port: int) -> None:
    calls["host"] = host
    calls["port"] = port

  # Drop into hugr.mcp.http at the right module path
  import hugr.mcp.http as http_mod
  monkeypatch.setattr(http_mod, "run", fake_http)

  result = CliRunner().invoke(cli, ["mcp", "--http", "--host", "0.0.0.0", "--port", "9090"])
  # asyncio.run wraps fake_http; exit code 0 means it ran without raising.
  assert result.exit_code == 0
  assert calls == {"host": "0.0.0.0", "port": 9090}

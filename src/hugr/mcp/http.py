"""HTTP transport for the hugr MCP server (plan 04.6).

Two entry points:

- ``mount(fastapi_app, path="/mcp")`` plugs the StreamableHTTP MCP
  transport into an existing FastAPI / Starlette app. Used by
  ``hugr server --mcp`` to expose tools on ``/mcp``.
- ``run(host, port)`` starts a standalone uvicorn server for
  ``hugr mcp --http``.

Both routes the same tool surface registered in
``hugr.mcp._server.build_server``.
"""

from __future__ import annotations

import contextlib
from typing import Any, AsyncIterator

from hugr.mcp._server import build_server


def _build_session_manager(*, stateless: bool = False) -> Any:
  """Return a StreamableHTTPSessionManager wired to the hugr MCP server."""
  from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

  server = build_server()
  return StreamableHTTPSessionManager(app=server, stateless=stateless)


def mount(app: Any, *, path: str = "/mcp", stateless: bool = False) -> Any:
  """Mount the MCP HTTP transport on *app* at *path*.

  Returns the session manager so callers can drive its lifecycle (it
  needs to be entered as an async context to start its task group).
  """
  manager = _build_session_manager(stateless=stateless)

  async def _handle(scope, receive, send):
    await manager.handle_request(scope, receive, send)

  # Starlette/FastAPI: route both the bare path and trailing-slash variant.
  app.add_route(path, _handle, methods=["GET", "POST", "DELETE"])
  app.add_route(path + "/", _handle, methods=["GET", "POST", "DELETE"])
  return manager


@contextlib.asynccontextmanager
async def lifespan(manager: Any) -> AsyncIterator[None]:
  """Drive the manager's task group across the app's lifespan."""
  async with manager.run():
    yield


async def run(*, host: str = "127.0.0.1", port: int = 7777) -> None:
  """Standalone HTTP MCP server (no other hugr routes)."""
  import uvicorn
  from starlette.applications import Starlette

  manager = _build_session_manager(stateless=False)

  async def _starlette_lifespan(app):
    async with manager.run():
      yield

  app = Starlette(lifespan=_starlette_lifespan)

  async def _handle(scope, receive, send):
    await manager.handle_request(scope, receive, send)

  app.add_route("/mcp", _handle, methods=["GET", "POST", "DELETE"])
  app.add_route("/mcp/", _handle, methods=["GET", "POST", "DELETE"])

  config = uvicorn.Config(app=app, host=host, port=port, log_level="info")
  server = uvicorn.Server(config)
  await server.serve()

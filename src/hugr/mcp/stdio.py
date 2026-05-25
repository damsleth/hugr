"""Async stdio MCP server entry point for ``hugr mcp --stdio``."""

from __future__ import annotations

from hugr.mcp._server import build_server


async def run() -> None:
  """Start the MCP stdio server and block until the client disconnects."""
  from mcp.server.stdio import stdio_server

  server = build_server()
  async with stdio_server() as (read_stream, write_stream):
    init_opts = server.create_initialization_options()
    await server.run(read_stream, write_stream, init_opts)

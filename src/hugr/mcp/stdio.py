"""Async stdio MCP server entry point for ``hugr mcp --stdio``.

Starts an MCP server that communicates over stdin/stdout using the
MCP stdio transport (newline-delimited JSON-RPC).  Tools are generated
at startup from ``hugr.api`` signatures via ``hugr.mcp.tools``.
"""

from __future__ import annotations

import asyncio
import inspect

import hugr.api as api
from hugr.mcp._adapter import adapt
from hugr.mcp.tools import _reverse_name_map, build_tool_defs


async def run() -> None:
  """Start the MCP stdio server and block until the client disconnects."""
  from mcp.server import Server
  from mcp.server.stdio import stdio_server
  from mcp.types import CallToolResult

  server = Server("hugr")
  tools = build_tool_defs()
  reverse_map = _reverse_name_map()

  @server.list_tools()
  async def list_tools():
    return tools

  @server.call_tool()
  async def call_tool(name: str, arguments: dict) -> CallToolResult:
    # Resolve MCP tool name back to api function name.
    fn_name = reverse_map.get(name)
    if fn_name is None:
      # Try stripping the "hugr." prefix and replacing dots with underscores.
      fn_name = name.removeprefix("hugr.").replace(".", "_")
    func = getattr(api, fn_name, None)
    if func is None:
      from mcp.types import TextContent
      return CallToolResult(
        content=[TextContent(type="text", text=f"Unknown tool: {name}")],
        isError=True,
      )
    try:
      sig = inspect.signature(func)
      if "args" in sig.parameters:
        result = func(arguments.get("args", []))
      elif fn_name == "recall":
        result = func(
          arguments["question"],
          k=arguments.get("k", 10),
          live=arguments.get("live", True),
        )
      elif fn_name == "find":
        result = func(
          arguments["kind"],
          arguments["query"],
          k=arguments.get("k", 10),
        )
      elif fn_name == "remember":
        result = func(
          arguments["fact_text"],
          note_type=arguments.get("note_type", "fact"),
          links=arguments.get("links", []),
          yes=arguments.get("yes", False),
        )
      else:
        result = func()
    except Exception as exc:
      from mcp.types import TextContent
      return CallToolResult(
        content=[TextContent(type="text", text=f"Error calling {name}: {exc}")],
        isError=True,
      )
    content, is_error = adapt(result)
    return CallToolResult(content=content, isError=is_error)

  async with stdio_server() as (read_stream, write_stream):
    init_opts = server.create_initialization_options()
    await server.run(read_stream, write_stream, init_opts)

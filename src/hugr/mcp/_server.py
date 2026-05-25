"""Build a configured ``mcp.server.lowlevel.Server`` for hugr.

Shared between the stdio and HTTP transports - both pull from this so
the tool surface stays identical regardless of how the client connects.
"""

from __future__ import annotations

import inspect

import hugr.api as api
from hugr.mcp._adapter import adapt
from hugr.mcp.tools import _reverse_name_map, build_tool_defs


def build_server():
  """Return an MCP Server with tools registered."""
  from mcp.server import Server
  from mcp.types import CallToolResult, TextContent

  server = Server("hugr")
  tools = build_tool_defs()
  reverse_map = _reverse_name_map()

  @server.list_tools()
  async def list_tools():
    return tools

  @server.call_tool()
  async def call_tool(name: str, arguments: dict) -> CallToolResult:
    fn_name = reverse_map.get(name)
    if fn_name is None:
      fn_name = name.removeprefix("hugr.").replace(".", "_")
    func = getattr(api, fn_name, None)
    if func is None:
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
      elif fn_name == "send_mail":
        result = func(
          arguments["to"],
          arguments["subject"],
          arguments["body"],
          cc=arguments.get("cc", []),
          bcc=arguments.get("bcc", []),
          html=arguments.get("html", False),
        )
      elif fn_name == "send_invite":
        result = func(
          arguments["subject"],
          date=arguments.get("date"),
          start=arguments.get("start"),
          end=arguments.get("end"),
          location=arguments.get("location"),
          body=arguments.get("body"),
          category=arguments.get("category"),
          showas=arguments.get("showas"),
        )
      elif fn_name == "schedule":
        result = func(
          arguments["intent"],
          who=arguments["who"],
          duration_minutes=arguments.get("duration_minutes", 30),
          date=arguments.get("date"),
          week=arguments.get("week"),
          year=arguments.get("year"),
        )
      elif fn_name == "schedule_commit":
        result = func(
          arguments["intent"],
          who=arguments["who"],
          slot=arguments["slot"],
          location=arguments.get("location"),
          body=arguments.get("body"),
          category=arguments.get("category"),
        )
      else:
        result = func()
    except Exception as exc:
      return CallToolResult(
        content=[TextContent(type="text", text=f"Error calling {name}: {exc}")],
        isError=True,
      )
    content, is_error = adapt(result)
    return CallToolResult(content=content, isError=is_error)

  return server

"""Tests for MCP tool generation from hugr.api signatures.

Skipped cleanly if the mcp package is not installed.
"""

from __future__ import annotations

import pytest

mcp = pytest.importorskip("mcp", reason="mcp extra not installed")

import hugr.api as api
from hugr.mcp.tools import NAME_MAP, build_tool_defs


def test_every_api_fn_has_a_tool():
  """Every name in hugr.api.__all__ must have a corresponding tool def."""
  tools = build_tool_defs()
  tool_names_by_fn = {fn: NAME_MAP.get(fn, "hugr." + fn.replace("_", ".")) for fn in api.__all__}
  generated_mcp_names = {t.name for t in tools}
  for fn_name, expected_mcp_name in tool_names_by_fn.items():
    assert expected_mcp_name in generated_mcp_names, (
      f"api function '{fn_name}' should map to MCP tool '{expected_mcp_name}' "
      f"but it was not found in the generated tool list"
    )


def test_tool_count_matches_api():
  """Tool count must equal the number of entries in hugr.api.__all__."""
  tools = build_tool_defs()
  assert len(tools) == len(api.__all__), (
    f"Expected {len(api.__all__)} tools (one per api.__all__ entry), "
    f"got {len(tools)}"
  )


def test_every_tool_has_required_fields():
  """Every tool definition must have name, description, and inputSchema."""
  tools = build_tool_defs()
  for tool in tools:
    assert tool.name, f"Tool missing name: {tool!r}"
    assert tool.description, f"Tool '{tool.name}' missing description"
    assert isinstance(tool.inputSchema, dict), (
      f"Tool '{tool.name}' inputSchema must be a dict, got {type(tool.inputSchema)}"
    )


def test_passthrough_tools_have_args_array_schema():
  """Passthrough wrappers (args: list[str]) must have an args array property."""
  tools = build_tool_defs()
  # All tools except doctor and version are passthrough wrappers.
  non_passthrough = {
    "hugr.doctor", "hugr.version",
    "hugr.recall", "hugr.find", "hugr.inbox", "hugr.remember",
    "hugr.send.mail", "hugr.send.invite",
    "hugr.book.propose", "hugr.book.commit",
  }
  for tool in tools:
    if tool.name in non_passthrough:
      continue
    schema = tool.inputSchema
    assert schema.get("type") == "object", (
      f"Tool '{tool.name}' schema type must be 'object', got {schema.get('type')!r}"
    )
    props = schema.get("properties", {})
    assert "args" in props, (
      f"Tool '{tool.name}' schema must have an 'args' property"
    )
    assert props["args"].get("type") == "array", (
      f"Tool '{tool.name}' args property must be type 'array'"
    )
    assert props["args"].get("items", {}).get("type") == "string", (
      f"Tool '{tool.name}' args items must be type 'string'"
    )


def test_no_arg_tools_have_empty_properties():
  """doctor() and version() take no args; their schemas must have no properties."""
  tools = build_tool_defs()
  no_arg_tools = {"hugr.doctor", "hugr.version", "hugr.inbox"}
  for tool in tools:
    if tool.name not in no_arg_tools:
      continue
    schema = tool.inputSchema
    assert schema.get("type") == "object", (
      f"Tool '{tool.name}' schema type must be 'object'"
    )
    assert schema.get("properties") == {}, (
      f"Tool '{tool.name}' must have empty properties dict, got {schema.get('properties')!r}"
    )


def test_all_tool_names_are_strings():
  """Tool names must be non-empty strings."""
  tools = build_tool_defs()
  for tool in tools:
    assert isinstance(tool.name, str) and tool.name, (
      f"Tool name must be a non-empty string, got {tool.name!r}"
    )


def test_known_tool_names_present():
  """Spot-check that the expected MCP names are present."""
  tools = build_tool_defs()
  generated_names = {t.name for t in tools}
  expected = {
    "hugr.doctor",
    "hugr.version",
    "hugr.recall",
    "hugr.find",
    "hugr.inbox",
    "hugr.remember",
    "hugr.yaams.query",
    "hugr.ledger.query",
    "hugr.cal",
    "hugr.mail",
    "hugr.auth",
  }
  for name in expected:
    assert name in generated_names, f"Expected tool '{name}' not found"

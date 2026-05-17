"""MCP tool definitions generated from mnem.api signatures.

Introspects ``mnem.api.__all__`` and builds a list of ``mcp.types.Tool``
objects - one per exported function - using a name-mapping table and the
function docstrings for descriptions.

No hand-rolled tool definitions: every entry derives from the live api.
"""

from __future__ import annotations

import inspect
from typing import Any

# ---------------------------------------------------------------------------
# Name mapping: api function name -> MCP tool name
# ---------------------------------------------------------------------------
# Only functions actually present in mnem.api.__all__ are mapped.
# Future verbs (ask, find, send, …) will be added when their api functions land.

NAME_MAP: dict[str, str] = {
  "doctor": "mnem.doctor",
  "version": "mnem.version",
  "yaams_query": "mnem.yaams.query",
  "yaams_ingest": "mnem.yaams.ingest",
  "yaams_promote_generate": "mnem.yaams.promote.generate",
  "yaams_promote_list": "mnem.yaams.promote.list",
  "ledger_init": "mnem.ledger.init",
  "ledger_paths": "mnem.ledger.paths",
  "ledger_query": "mnem.ledger.query",
  "ledger_loops": "mnem.ledger.loops",
  "ledger_notes": "mnem.ledger.notes",
  "ledger_context": "mnem.ledger.context",
  "ledger_context_build": "mnem.ledger.context.build",
  "ledger_context_profiles": "mnem.ledger.context.profiles",
  "owa_piggy": "mnem.auth",
  "owa_cal": "mnem.calendar",
  "owa_mail": "mnem.mail",
  "owa_graph": "mnem.graph",
  "owa_people": "mnem.people",
  "owa_sched": "mnem.schedule",
  "owa_drive": "mnem.drive",
}

# JSON schema for passthrough wrappers (args: list[str]) and no-arg functions.
_PASSTHROUGH_SCHEMA: dict[str, Any] = {
  "type": "object",
  "properties": {
    "args": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Arguments forwarded verbatim to the underlying CLI tool.",
    }
  },
  "required": [],
}

_NO_ARG_SCHEMA: dict[str, Any] = {
  "type": "object",
  "properties": {},
  "required": [],
}


def _build_schema(func: Any) -> dict[str, Any]:
  """Return a JSON Schema dict for the given api function.

  Functions with no parameters get an empty-properties object schema.
  Functions with an ``args: list[str]`` parameter get the passthrough schema.
  """
  sig = inspect.signature(func)
  params = {
    name: p
    for name, p in sig.parameters.items()
    if name != "self"
  }
  if not params:
    return _NO_ARG_SCHEMA
  # Passthrough wrappers declare a single ``args`` parameter typed list[str].
  if list(params.keys()) == ["args"]:
    return _PASSTHROUGH_SCHEMA
  # Fallback: treat as no-arg (shouldn't happen for current api surface).
  return _NO_ARG_SCHEMA


def _first_docstring_line(func: Any) -> str:
  """Return the first non-blank line of a function's docstring."""
  doc = inspect.getdoc(func) or ""
  for line in doc.splitlines():
    line = line.strip()
    if line:
      return line
  return f"Call mnem.api.{func.__name__}"


def build_tool_defs() -> list[Any]:
  """Build and return the list of MCP Tool objects for all mnem.api functions.

  Imports ``mcp.types.Tool`` at call time so this module can be imported
  without the mcp package installed (the ImportError surfaces only when
  ``build_tool_defs`` is called, not at module load).
  """
  from mcp.types import Tool
  import mnem.api as api

  tools: list[Tool] = []
  for fn_name in api.__all__:
    mcp_name = NAME_MAP.get(fn_name)
    if mcp_name is None:
      # Unmapped function: derive a name automatically (safety net).
      mcp_name = "mnem." + fn_name.replace("_", ".")
    func = getattr(api, fn_name)
    tools.append(
      Tool(
        name=mcp_name,
        description=_first_docstring_line(func),
        inputSchema=_build_schema(func),
      )
    )
  return tools


# Reverse lookup: MCP tool name -> api function name
def _reverse_name_map() -> dict[str, str]:
  """Return {mcp_tool_name: api_fn_name}."""
  return {v: k for k, v in NAME_MAP.items()}

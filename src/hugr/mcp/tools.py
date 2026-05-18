"""MCP tool definitions generated from hugr.api signatures.

Introspects ``hugr.api.__all__`` and builds a list of ``mcp.types.Tool``
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
# Only functions actually present in hugr.api.__all__ are mapped.

NAME_MAP: dict[str, str] = {
  "doctor": "hugr.doctor",
  "version": "hugr.version",
  "recall": "hugr.recall",
  "find": "hugr.find",
  "inbox": "hugr.inbox",
  "remember": "hugr.remember",
  "yaams_query": "hugr.yaams.query",
  "yaams_ingest": "hugr.yaams.ingest",
  "yaams_promote_generate": "hugr.yaams.promote.generate",
  "yaams_promote_list": "hugr.yaams.promote.list",
  "ledger_init": "hugr.ledger.init",
  "ledger_paths": "hugr.ledger.paths",
  "ledger_query": "hugr.ledger.query",
  "ledger_loops": "hugr.ledger.loops",
  "ledger_notes": "hugr.ledger.notes",
  "ledger_context": "hugr.ledger.context",
  "ledger_context_build": "hugr.ledger.context.build",
  "ledger_context_profiles": "hugr.ledger.context.profiles",
  "owa_piggy": "hugr.auth",
  "owa_cal": "hugr.cal",
  "owa_mail": "hugr.mail",
  "owa_graph": "hugr.graph",
  "owa_people": "hugr.people",
  "owa_sched": "hugr.schedule",
  "owa_drive": "hugr.drive",
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

_FUSED_SCHEMAS: dict[str, dict[str, Any]] = {
  "recall": {
    "type": "object",
    "properties": {
      "question": {"type": "string"},
      "k": {"type": "integer", "default": 10},
      "live": {"type": "boolean", "default": True},
    },
    "required": ["question"],
  },
  "find": {
    "type": "object",
    "properties": {
      "kind": {"type": "string"},
      "query": {"type": "string"},
      "k": {"type": "integer", "default": 10},
    },
    "required": ["kind", "query"],
  },
  "remember": {
    "type": "object",
    "properties": {
      "fact_text": {"type": "string"},
      "note_type": {"type": "string", "default": "fact"},
      "links": {"type": "array", "items": {"type": "string"}},
      "yes": {"type": "boolean", "default": False},
    },
    "required": ["fact_text"],
  },
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
  if func.__name__ in _FUSED_SCHEMAS:
    return _FUSED_SCHEMAS[func.__name__]
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
  return f"Call hugr.api.{func.__name__}"


def build_tool_defs() -> list[Any]:
  """Build and return the list of MCP Tool objects for all hugr.api functions.

  Imports ``mcp.types.Tool`` at call time so this module can be imported
  without the mcp package installed (the ImportError surfaces only when
  ``build_tool_defs`` is called, not at module load).
  """
  from mcp.types import Tool
  import hugr.api as api

  tools: list[Tool] = []
  for fn_name in api.__all__:
    mcp_name = NAME_MAP.get(fn_name)
    if mcp_name is None:
      # Unmapped function: derive a name automatically (safety net).
      mcp_name = "hugr." + fn_name.replace("_", ".")
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

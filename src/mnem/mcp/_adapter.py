"""Adapts mnem.api return values to MCP CallToolResult content.

mnem.api return conventions
---------------------------
- ``tuple[int, bytes]``  - passthrough wrappers: (exit_code, stdout_bytes)
- ``tuple[dict, int]``   - doctor(): (data_dict, exit_code)
- ``dict``               - version(): plain dict

MCP result conventions
----------------------
- Success: list of TextContent blocks (isError=False)
- Failure: list of TextContent blocks (isError=True)
"""

from __future__ import annotations

import json
from typing import Any


def adapt(result: Any) -> tuple[list[Any], bool]:
  """Convert an mnem.api return value to (content_blocks, is_error).

  ``content_blocks`` is a list of ``mcp.types.TextContent`` objects.
  ``is_error`` is True when the underlying tool reported failure.

  Imports mcp.types lazily so this module does not require the mcp
  package at import time.
  """
  from mcp.types import TextContent

  # --- dict (version()) ---------------------------------------------------
  if isinstance(result, dict):
    return [TextContent(type="text", text=json.dumps(result, indent=2))], False

  # --- tuple[dict, int] (doctor()) ----------------------------------------
  if (
    isinstance(result, tuple)
    and len(result) == 2
    and isinstance(result[0], dict)
    and isinstance(result[1], int)
  ):
    data, exit_code = result
    text = json.dumps(data, indent=2)
    is_error = exit_code != 0
    return [TextContent(type="text", text=text)], is_error

  # --- tuple[int, bytes] (passthrough wrappers) ---------------------------
  if (
    isinstance(result, tuple)
    and len(result) == 2
    and isinstance(result[0], int)
    and isinstance(result[1], bytes)
  ):
    exit_code, stdout_bytes = result
    text = stdout_bytes.decode("utf-8", errors="replace")
    if exit_code == 0:
      return [TextContent(type="text", text=text)], False
    else:
      error_text = f"exit_code={exit_code}\n{text}"
      return [TextContent(type="text", text=error_text)], True

  # --- fallback: stringify whatever we got --------------------------------
  return [TextContent(type="text", text=str(result))], False

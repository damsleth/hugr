"""Subprocess handshake test for ``mnem mcp --stdio``.

Spawns the server as a child process, sends JSON-RPC messages over
stdin/stdout, and validates the responses.

Skipped cleanly if the mcp package is not installed.

The MCP stdio transport uses newline-delimited JSON-RPC (one JSON
object per line), NOT length-prefixed framing.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading

import pytest

pytest.importorskip("mcp", reason="mcp extra not installed")

TIMEOUT = 10  # seconds


def _send(proc: subprocess.Popen, obj: dict) -> None:
  """Write a single JSON-RPC message to the process stdin."""
  line = json.dumps(obj) + "\n"
  proc.stdin.write(line.encode())
  proc.stdin.flush()


def _make_reader(proc: subprocess.Popen) -> queue.Queue:
  """Spawn a background thread that reads stdout lines into a queue."""
  q: queue.Queue = queue.Queue()

  def _read():
    try:
      for raw in proc.stdout:
        raw = raw.strip()
        if raw:
          q.put(raw)
    except Exception:
      pass
    finally:
      q.put(None)  # sentinel: stdout closed

  t = threading.Thread(target=_read, daemon=True)
  t.start()
  return q


def _recv(q: queue.Queue, timeout: float = TIMEOUT) -> dict:
  """Get one JSON-RPC message from the reader queue."""
  item = q.get(timeout=timeout)
  if item is None:
    raise EOFError("MCP server closed stdout unexpectedly")
  return json.loads(item)


@pytest.fixture
def mcp_proc():
  """Start ``mnem mcp --stdio`` as a subprocess, yield (proc, reader_queue), then terminate."""
  python = sys.executable
  proc = subprocess.Popen(
    [python, "-m", "mnem", "mcp", "--stdio"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
  )
  q = _make_reader(proc)
  yield proc, q
  proc.terminate()
  try:
    proc.wait(timeout=3)
  except subprocess.TimeoutExpired:
    proc.kill()


def test_initialize_handshake(mcp_proc):
  """Server must respond to the MCP initialize request."""
  proc, q = mcp_proc
  _send(proc, {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test-client", "version": "0.0.1"},
    },
  })
  response = _recv(q)
  assert response.get("jsonrpc") == "2.0", f"Unexpected response: {response}"
  assert response.get("id") == 1
  result = response.get("result", {})
  assert "protocolVersion" in result, f"Missing protocolVersion in: {result}"
  assert "capabilities" in result, f"Missing capabilities in: {result}"


def test_tools_list_contains_expected(mcp_proc):
  """After initialize, tools/list must contain mnem.doctor and mnem.version."""
  proc, q = mcp_proc

  # --- initialize ---
  _send(proc, {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test-client", "version": "0.0.1"},
    },
  })
  _recv(q)  # consume initialize response

  # --- initialized notification ---
  _send(proc, {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
  })

  # --- tools/list ---
  _send(proc, {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {},
  })
  response = _recv(q)
  assert response.get("id") == 2, f"Unexpected response id: {response}"
  result = response.get("result", {})
  tools = result.get("tools", [])
  assert len(tools) > 0, "tools/list returned no tools"
  tool_names = {t["name"] for t in tools}
  assert "mnem.doctor" in tool_names, f"mnem.doctor not in tool list: {tool_names}"
  assert "mnem.version" in tool_names, f"mnem.version not in tool list: {tool_names}"


def test_tools_call_accepts_empty_passthrough_args(mcp_proc):
  """Passthrough MCP tools with args=[] must call api.fn([]), not api.fn()."""
  proc, q = mcp_proc

  _send(proc, {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": {"name": "test-client", "version": "0.0.1"},
    },
  })
  _recv(q)
  _send(proc, {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
  })

  _send(proc, {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "mnem.ledger.paths",
      "arguments": {"args": []},
    },
  })
  response = _recv(q)

  assert response.get("id") == 2, f"Unexpected response: {response}"
  result = response.get("result", {})
  rendered = "\n".join(block.get("text", "") for block in result.get("content", []))
  assert "missing 1 required positional argument" not in rendered

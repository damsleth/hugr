"""Tests for the exit-2 / usage-error classification in passthrough.run().

Piece A of router-passthrough-hardening: when an underlying tool exits 2
(argparse EXIT_USAGE) with no envelope on stdout, hugr must surface the
tool's own stderr usage text instead of "tool crashed - file bug".

See .plans/router-passthrough-hardening.md §Piece A.
"""
from __future__ import annotations

import pytest

from hugr.commands import passthrough


def _spy_stream_returns(monkeypatch, rc: int, stdout: str, stderr: str):
  """Patch _stream_subprocess to return a fixed (rc, stdout, stderr)."""
  def _fake(argv, **_kwargs):
    return rc, stdout, stderr

  monkeypatch.setattr(passthrough, "_stream_subprocess", _fake)


# --- Piece A tests ----------------------------------------------------------

def test_usage_error_not_reported_as_crash(monkeypatch, capsys):
  """rc=2 with empty stdout => usage error message, NOT 'tool crashed'."""
  usage_text = (
    "usage: ledger notes [-h] --type {facts,...}\n"
    "ledger notes: error: the following arguments are required: --type\n"
  )
  _spy_stream_returns(monkeypatch, rc=2, stdout="", stderr=usage_text)

  rc = passthrough.run(["ledger", "notes"])

  assert rc == 2
  err = capsys.readouterr().err
  # Must NOT say "tool crashed - file bug"
  assert "tool crashed" not in err
  assert "file bug" not in err
  # Must surface the tool's own stderr usage text
  assert "usage error" in err.lower() or "ledger notes" in err or "--type" in err


def test_genuine_crash_still_says_file_bug(monkeypatch, capsys):
  """rc=1 with empty stdout (no envelope) => still reports 'tool crashed'."""
  _spy_stream_returns(
    monkeypatch,
    rc=1,
    stdout="",
    stderr="Traceback (most recent call last):\n  File ...\nRuntimeError: boom\n",
  )

  rc = passthrough.run(["ledger", "paths"])

  assert rc == 1
  err = capsys.readouterr().err
  assert "tool crashed - file bug" in err


def test_structured_tool_error_unchanged(monkeypatch, capsys):
  """Structured envelope with ok=false still uses the structured error path."""
  _spy_stream_returns(
    monkeypatch,
    rc=1,
    stdout='{"tool":"ledger","ok":false,"error":{"message":"boom","hint":"do y"}}\n',
    stderr="",
  )

  rc = passthrough.run(["ledger", "paths"])

  assert rc == 1
  err = capsys.readouterr().err
  # Structured-error path: shows the message from the envelope
  assert "boom" in err
  # Should NOT say "tool crashed" (that's reserved for unstructured crashes)
  assert "tool crashed" not in err


def test_exit_2_with_envelope_is_not_a_usage_error(monkeypatch, capsys):
  """If the child exits 2 but wrote a valid envelope, usage_error must be
  False — envelope presence means the tool managed to produce structured
  output, so the normal rc!=0 path fires, not the usage-error branch."""
  _spy_stream_returns(
    monkeypatch,
    rc=2,
    stdout='{"tool":"ledger","ok":false,"error":{"message":"structured two"}}\n',
    stderr="",
  )

  rc = passthrough.run(["ledger", "paths"])

  assert rc == 2
  err = capsys.readouterr().err
  # Structured-error path fires (not usage-error, not crash)
  assert "structured two" in err
  assert "tool crashed" not in err

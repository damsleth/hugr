"""Tests for -v/--verbose/--debug forwarding to the underlying tools.

hugr forwards the user's verbose intent to the connected tools so you
can see what is happening under the hood. The mechanism is per-row in
the router (env var vs flag), so these tests pin both the router
overlay and the end-to-end wiring through the passthrough/CLI layers.
"""
from __future__ import annotations

import pytest

from hugr.router import TABLE, lookup, verbose_overlay


# ---------------------------------------------------------------------------
# Router-level overlay
# ---------------------------------------------------------------------------

def test_owa_rows_forward_via_debug_env_var():
  """Every owa-* tool reads <TOOL>_DEBUG=1 — position-independent, so we
  prefer the env var over a flag (works for all subcommands)."""
  expected = {
    ("mail",): ("MAIL_DEBUG", "1"),
    ("cal",): ("CAL_DEBUG", "1"),
    ("graph",): ("GRAPH_DEBUG", "1"),
    ("people",): ("PEOPLE_DEBUG", "1"),
    ("schedule",): ("SCHED_DEBUG", "1"),
    ("drive",): ("DRIVE_DEBUG", "1"),
  }
  for verb, (name, value) in expected.items():
    mapping = TABLE[verb]
    env, flag = verbose_overlay(mapping)
    assert env == {name: value}, verb
    assert flag == [], verb


def test_yaams_ingest_forwards_via_flag():
  """yaams ingest has no debug env var; it takes -v after the subcommand."""
  env, flag = verbose_overlay(TABLE[("ingest",)])
  assert env == {}
  assert flag == ["-v"]


def test_ledger_loops_and_notes_forward_via_flag():
  for verb in [("loops",), ("notes",), ("ledger", "loops"), ("ledger", "notes")]:
    env, flag = verbose_overlay(TABLE[verb])
    assert env == {}, verb
    assert flag == ["--verbose"], verb


def test_rows_without_a_verbose_mechanism_are_a_noop():
  """auth (owa-piggy) and yaams query have no verbose mechanism upstream,
  so we must NOT inject a flag that the subcommand would reject."""
  for verb in [("query",), ("auth", "status"), ("briefing",), ("stats",)]:
    env, flag = verbose_overlay(TABLE[verb])
    assert env == {}, verb
    assert flag == [], verb


# ---------------------------------------------------------------------------
# End-to-end through commands/passthrough.run()
# ---------------------------------------------------------------------------

@pytest.fixture
def capture_argv(monkeypatch):
  """Patch the streaming subprocess and record argv + extra_env."""
  seen: dict[str, object] = {}

  def fake_stream(argv, *, extra_env=None, echo_stderr=False):
    seen["argv"] = list(argv)
    seen["extra_env"] = dict(extra_env) if extra_env else {}
    return 0, '{"ok": true}', ""

  import hugr.commands.passthrough as pt
  monkeypatch.setattr(pt, "_stream_subprocess", fake_stream)
  return seen


def test_passthrough_verbose_appends_yaams_flag(capture_argv):
  from hugr.commands.passthrough import run
  run(["ingest"], verbose=True)
  assert "-v" in capture_argv["argv"]
  assert "MAIL_DEBUG" not in capture_argv["extra_env"]


def test_passthrough_verbose_sets_owa_debug_env(capture_argv):
  from hugr.commands.passthrough import run
  run(["mail", "messages"], verbose=True)
  assert capture_argv["extra_env"].get("MAIL_DEBUG") == "1"
  # owa tools take the env var, never the flag.
  assert "-v" not in capture_argv["argv"]
  assert "--verbose" not in capture_argv["argv"]


def test_passthrough_not_verbose_forwards_nothing(capture_argv):
  from hugr.commands.passthrough import run
  run(["mail", "messages"], verbose=False)
  assert "MAIL_DEBUG" not in capture_argv["extra_env"]
  assert "-v" not in capture_argv["argv"]


def test_passthrough_verbose_does_not_double_append_flag(capture_argv):
  """If the flag is somehow already present, don't add a second copy."""
  from hugr.commands.passthrough import run
  run(["loops", "--verbose"], verbose=True)
  assert capture_argv["argv"].count("--verbose") == 1


# ---------------------------------------------------------------------------
# _split_verbose: accept the flag after the verb, honor the -- separator
# ---------------------------------------------------------------------------

def test_split_verbose_strips_each_token():
  from hugr.cli import _split_verbose
  for tok in ("-v", "--verbose", "--debug"):
    kept, found = _split_verbose(("messages", tok, "--limit", "5"))
    assert found is True
    assert kept == ("messages", "--limit", "5")


def test_split_verbose_absent():
  from hugr.cli import _split_verbose
  kept, found = _split_verbose(("messages", "--limit", "5"))
  assert found is False
  assert kept == ("messages", "--limit", "5")


def test_split_verbose_preserves_payload_after_double_dash():
  """A literal --verbose after `--` is a payload, not hugr's flag."""
  from hugr.cli import _split_verbose
  kept, found = _split_verbose(("search", "--", "--verbose"))
  assert found is False
  assert kept == ("search", "--", "--verbose")


# ---------------------------------------------------------------------------
# CLI: both `hugr -v mail ...` and `hugr mail ... --verbose` forward
# ---------------------------------------------------------------------------

@pytest.fixture
def cli_capture(monkeypatch):
  seen: dict[str, object] = {}

  def fake_stream(argv, *, extra_env=None, echo_stderr=False):
    seen["argv"] = list(argv)
    seen["extra_env"] = dict(extra_env) if extra_env else {}
    return 0, '{"ok": true}', ""

  import hugr.commands.passthrough as pt
  monkeypatch.setattr(pt, "_stream_subprocess", fake_stream)
  return seen


def test_cli_verbose_before_verb_forwards(cli_capture):
  from click.testing import CliRunner
  from hugr.cli import cli
  CliRunner().invoke(cli, ["-v", "mail", "messages"])
  assert cli_capture["extra_env"].get("MAIL_DEBUG") == "1"


def test_cli_verbose_after_verb_forwards(cli_capture):
  """The natural `hugr mail messages --verbose` must work too — the flag
  lands in the subcommand tail and is normalized, not passed verbatim."""
  from click.testing import CliRunner
  from hugr.cli import cli
  CliRunner().invoke(cli, ["mail", "messages", "--verbose"])
  assert cli_capture["extra_env"].get("MAIL_DEBUG") == "1"
  # Not forwarded verbatim into argv (owa rejects --verbose after subcommand).
  assert "--verbose" not in cli_capture["argv"]


def test_cli_debug_alias_after_verb_forwards(cli_capture):
  from click.testing import CliRunner
  from hugr.cli import cli
  CliRunner().invoke(cli, ["mail", "messages", "--debug"])
  assert cli_capture["extra_env"].get("MAIL_DEBUG") == "1"

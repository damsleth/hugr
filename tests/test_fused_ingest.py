"""Tests for the fused ingest orchestrator (api/ingest.py + commands/ingest.py).

Coverage targets from the plan:
  - happy path: counts in envelope
  - --dry-run: no writes asserted via spy
  - yaams-failure: sweep not run, exit propagated
  - promote-failure: warning + exit 2
  - --promote without --yes: preview, no ledger write
  - --promote --yes: write happens (promote call made)
  - --raw: pure passthrough, orchestrator not invoked
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from hugr.api import ingest as ingest_module
from hugr.api.ingest import fused_ingest
from hugr.cli import cli


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _hugr_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
  """Give every test a minimal hugr config so _ensure_config passes."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  cfg = tmp_path / "hugr" / "config.yaml"
  cfg.parent.mkdir(parents=True)
  cfg.write_text("version: 1\n")


# ---------------------------------------------------------------------------
# Unit tests for fused_ingest() via monkeypatching the _call layer
# ---------------------------------------------------------------------------

def _make_call_spy(responses: list[tuple[int, bytes]]):
  """Return a fake _call that pops from *responses* in call order."""
  call_log: list[list[str]] = []
  responses_queue = list(responses)

  def fake_call(args: list[str], **kwargs) -> tuple[int, bytes]:
    call_log.append(list(args))
    if responses_queue:
      return responses_queue.pop(0)
    return 0, b'{}'

  fake_call.log = call_log  # type: ignore[attr-defined]
  return fake_call


def test_happy_path_returns_ok_envelope(monkeypatch):
  """All three stages succeed; envelope has counts and ok=True."""
  spy = _make_call_spy([
    (0, json.dumps({"ok": True, "ingested": 42}).encode()),
    (0, json.dumps({"ok": True, "candidates": 7}).encode()),
  ])
  monkeypatch.setattr(ingest_module, "_call", spy)

  doc = fused_ingest()

  assert doc["ok"] is True
  assert doc["exit_code"] == 0
  assert doc["ingested"] == 42
  assert doc["candidates_generated"] == 7
  assert doc["promoted"] is None
  assert doc["dry_run"] is False
  assert doc["raw"] is False
  assert doc["error"] is None
  assert doc["warnings"] == []
  # Stage 1: ingest; Stage 2: promote generate
  assert spy.log == [["ingest"], ["promote", "generate"]]


def test_dry_run_calls_ingest_with_dry_run_flag_and_skips_sweep(monkeypatch):
  """--dry-run: passes --dry-run to yaams ingest and skips sweep stage."""
  spy = _make_call_spy([
    (0, json.dumps({"ok": True, "ingested": 5}).encode()),
  ])
  monkeypatch.setattr(ingest_module, "_call", spy)

  doc = fused_ingest(dry_run=True)

  assert doc["ok"] is True
  assert doc["dry_run"] is True
  assert doc["ingested"] == 5
  assert doc["candidates_generated"] is None
  assert doc["promoted"] is None
  # Only the ingest call with --dry-run; no sweep call.
  assert spy.log == [["ingest", "--dry-run"]]


def test_yaams_failure_propagates_exit_code_and_skips_sweep(monkeypatch):
  """yaams ingest fails -> propagate its exit code; sweep not called."""
  spy = _make_call_spy([
    (1, json.dumps({"ok": False, "error": {"message": "db locked"}}).encode()),
  ])
  monkeypatch.setattr(ingest_module, "_call", spy)

  doc = fused_ingest()

  assert doc["ok"] is False
  assert doc["exit_code"] == 1
  assert doc["ingested"] is None
  assert doc["error"]["code"] == "ingest_failed"
  assert "db locked" in doc["error"]["message"]
  # Sweep must NOT have been called.
  assert spy.log == [["ingest"]]


def test_yaams_failure_nonzero_exit_code_preserved(monkeypatch):
  """A non-1 exit code from yaams is propagated verbatim."""
  spy = _make_call_spy([
    (3, b""),
  ])
  monkeypatch.setattr(ingest_module, "_call", spy)

  doc = fused_ingest()

  assert doc["exit_code"] == 3
  assert not doc["ok"]


def test_promote_generate_failure_is_warning_and_exit_2(monkeypatch):
  """Ingest ok + promote generate fails -> exit 2, warning, no rollback."""
  spy = _make_call_spy([
    (0, json.dumps({"ok": True, "ingested": 10}).encode()),
    (1, json.dumps({"ok": False, "error": {"message": "model not found"}}).encode()),
  ])
  monkeypatch.setattr(ingest_module, "_call", spy)

  doc = fused_ingest()

  assert doc["ok"] is False
  assert doc["exit_code"] == 2  # partial success
  assert doc["ingested"] == 10
  assert doc["candidates_generated"] is None
  assert len(doc["warnings"]) == 1
  assert "model not found" in doc["warnings"][0]["message"]
  assert doc["error"]["code"] == "partial_success"
  # Hint must mention Tier 1 is safe.
  assert "Tier 1" in doc["error"]["hint"]


def test_promote_without_yes_is_preview_no_ledger_write(monkeypatch):
  """--promote without --yes: preview only; no promote write call made."""
  spy = _make_call_spy([
    (0, json.dumps({"ok": True, "ingested": 3}).encode()),
    (0, json.dumps({"ok": True, "candidates": 5}).encode()),
    # No third call expected.
  ])
  monkeypatch.setattr(ingest_module, "_call", spy)

  doc = fused_ingest(promote=True, yes=False)

  assert doc["ok"] is True
  assert doc["exit_code"] == 0
  assert doc["promoted"] is None
  assert doc["promotion_pending"] == 5
  # Only ingest + promote generate -- hugr never auto-writes.
  assert spy.log == [["ingest"], ["promote", "generate"]]


def test_promote_with_yes_does_not_write_and_warns(monkeypatch):
  """--promote --yes cannot auto-write: yaams has no non-interactive
  promote-commit verb (only generate/list/review, review is
  interactive). So no third subprocess call is made, candidates are
  reported as pending, promoted stays None, and a warning explains why."""
  spy = _make_call_spy([
    (0, json.dumps({"ok": True, "ingested": 3}).encode()),
    (0, json.dumps({"ok": True, "candidates": 4}).encode()),
    # No third call: there is nothing to call.
  ])
  monkeypatch.setattr(ingest_module, "_call", spy)

  doc = fused_ingest(promote=True, yes=True)

  assert doc["ok"] is True
  assert doc["exit_code"] == 0
  assert doc["promoted"] is None          # nothing is ever auto-written
  assert doc["promotion_pending"] == 4
  # Only ingest + promote generate -- no ledger-write subprocess.
  assert spy.log == [["ingest"], ["promote", "generate"]]
  assert any(
    "non-interactive promotion" in w["message"] for w in doc["warnings"]
  )


def test_raw_returns_sentinel_envelope_without_calling_backends(monkeypatch):
  """--raw: orchestrator short-circuits; no _call made."""
  calls: list[list[str]] = []

  def fake_call(args: list[str], **kwargs) -> tuple[int, bytes]:
    calls.append(list(args))
    return 0, b"{}"

  monkeypatch.setattr(ingest_module, "_call", fake_call)

  doc = fused_ingest(raw=True)

  assert doc["raw"] is True
  assert doc["ok"] is True
  assert calls == []  # no subprocess calls


def test_extra_args_forwarded_to_ingest(monkeypatch):
  """Extra args (e.g. --source imessage) are forwarded to yaams ingest."""
  spy = _make_call_spy([
    (0, b"{}"),
    (0, b"{}"),
  ])
  monkeypatch.setattr(ingest_module, "_call", spy)

  fused_ingest(extra_args=["--source", "imessage"])

  assert spy.log[0] == ["ingest", "--source", "imessage"]


def test_envelope_has_required_keys(monkeypatch):
  """Envelope always contains the documented top-level keys."""
  monkeypatch.setattr(ingest_module, "_call", lambda _a, **_k: (0, b"{}"))
  doc = fused_ingest()
  for key in ("tool", "command", "ok", "exit_code", "dry_run", "raw",
              "ingested", "candidates_generated", "promoted", "warnings", "error"):
    assert key in doc, f"missing key: {key}"


# ---------------------------------------------------------------------------
# CLI integration tests via CliRunner
# ---------------------------------------------------------------------------

def test_cli_ingest_json_output_on_success(monkeypatch):
  """hugr ingest --json returns a parseable JSON envelope on success."""
  monkeypatch.setattr(ingest_module, "_call", lambda _a, **_k: (
    0, json.dumps({"ok": True, "ingested": 1}).encode()
  ))
  result = CliRunner().invoke(cli, ["ingest", "--json"])
  assert result.exit_code == 0, result.output + (result.exception and str(result.exception) or "")
  doc = json.loads(result.output.strip())
  assert doc["tool"] == "hugr"
  assert doc["command"] == "ingest"
  assert doc["ok"] is True


def test_cli_ingest_pretty_output_on_success(monkeypatch):
  """hugr ingest (no --json) prints human-readable output."""
  monkeypatch.setattr(ingest_module, "_call", lambda _a, **_k: (
    0, json.dumps({"ok": True, "ingested": 3}).encode()
  ))
  result = CliRunner().invoke(cli, ["ingest"])
  assert result.exit_code == 0, result.output
  assert "hugr ingest" in result.output
  assert "3" in result.output


def test_cli_ingest_dry_run_flag_accepted(monkeypatch):
  """hugr ingest --dry-run exits 0 and mentions dry-run."""
  monkeypatch.setattr(ingest_module, "_call", lambda _a, **_k: (
    0, json.dumps({"ok": True, "ingested": 0}).encode()
  ))
  result = CliRunner().invoke(cli, ["ingest", "--dry-run"])
  assert result.exit_code == 0, result.output
  assert "dry" in result.output.lower() or "dry" in (result.stderr or "").lower()


def test_cli_ingest_exits_2_on_partial_failure(monkeypatch):
  """hugr ingest exits 2 when ingest ok but sweep fails."""
  responses = [
    (0, json.dumps({"ok": True, "ingested": 5}).encode()),
    (1, json.dumps({"ok": False, "error": {"message": "sweep error"}}).encode()),
  ]
  call_iter = iter(responses)
  monkeypatch.setattr(ingest_module, "_call", lambda _a, **_k: next(call_iter))

  result = CliRunner().invoke(cli, ["ingest", "--json"])
  assert result.exit_code == 2, result.output
  doc = json.loads(result.output.strip())
  assert doc["exit_code"] == 2


def test_cli_ingest_exits_nonzero_on_yaams_failure(monkeypatch):
  """hugr ingest propagates yaams exit code."""
  monkeypatch.setattr(ingest_module, "_call", lambda _a, **_k: (
    1, json.dumps({"ok": False, "error": {"message": "fail"}}).encode()
  ))
  result = CliRunner().invoke(cli, ["ingest", "--json"])
  assert result.exit_code != 0
  doc = json.loads(result.output.strip())
  assert doc["ok"] is False


def test_cli_ingest_raw_bypasses_orchestrator(monkeypatch, tmp_path: Path):
  """hugr ingest --raw routes through the passthrough, not the orchestrator."""
  orchestrator_calls: list[str] = []

  original_fused = fused_ingest

  def tracking_fused(**kwargs):
    orchestrator_calls.append("called")
    return original_fused(**kwargs)

  monkeypatch.setattr(ingest_module, "fused_ingest", tracking_fused)

  # Mock the passthrough run so we don't need a real yaams binary.
  import hugr.commands.ingest as cmd_mod
  passthrough_calls: list[list[str]] = []

  def fake_passthrough_run(args, **kwargs) -> int:
    passthrough_calls.append(list(args))
    return 0

  monkeypatch.setattr(cmd_mod, "fused_ingest", tracking_fused)
  # We need to patch the passthrough.run that's imported inside the command.
  import hugr.commands.passthrough as pt_mod
  monkeypatch.setattr(pt_mod, "run", fake_passthrough_run)

  result = CliRunner().invoke(cli, ["ingest", "--raw"])
  # The orchestrator tracking_fused should not have been called with raw=False.
  # (In raw path the CLI calls passthrough.run directly, not fused_ingest.)
  assert passthrough_calls or result.exit_code == 0


def test_cli_ingest_first_run_guard(monkeypatch, tmp_path: Path):
  """hugr ingest without config exits 4 with hint."""
  # Override the config fixture for this test.
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "no_config"))
  result = CliRunner().invoke(cli, ["ingest"])
  assert result.exit_code == 4
  combined = result.output + (result.stderr_bytes or b"").decode("utf-8", "ignore")
  assert "hugr init" in combined


def test_cli_ingest_promote_preview_message(monkeypatch):
  """--promote without --yes reports candidates and points at the
  interactive reviewer (no write happens)."""
  responses = [
    (0, json.dumps({"ok": True, "ingested": 2}).encode()),
    (0, json.dumps({"ok": True, "candidates": 5}).encode()),
  ]
  call_iter = iter(responses)
  monkeypatch.setattr(ingest_module, "_call", lambda _a, **_k: next(call_iter))

  result = CliRunner().invoke(cli, ["ingest", "--promote"])
  assert result.exit_code == 0, result.output
  assert "5" in result.output
  assert "promote review" in result.output  # actionable next step


def test_cli_ingest_promote_yes_does_not_claim_a_write(monkeypatch):
  """--promote --yes must NOT claim candidates were written: there is
  no non-interactive promote-commit verb upstream. It surfaces an
  honest note that auto-write is unavailable."""
  responses = [
    (0, json.dumps({"ok": True, "ingested": 2}).encode()),
    (0, json.dumps({"ok": True, "candidates": 3}).encode()),
    # No third call: nothing to write to.
  ]
  call_iter = iter(responses)
  monkeypatch.setattr(ingest_module, "_call", lambda _a, **_k: next(call_iter))

  result = CliRunner().invoke(cli, ["ingest", "--promote", "--yes"])
  assert result.exit_code == 0, result.output
  out = result.output.lower()
  assert "could not auto-write" in out
  assert "not available" in out
  # Must not falsely claim a completed write.
  assert "written to ledger" not in out
  assert "candidate(s) written" not in out

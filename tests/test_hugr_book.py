from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import sys

import hugr.api as api
from hugr.cli import cli

sched_mod = sys.modules["hugr.api.schedule"]


def _stub_config(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  cfg = tmp_path / "hugr" / "config.toml"
  cfg.parent.mkdir(parents=True)
  cfg.write_text("version: 1\n")


def test_api_schedule_builds_find_time_argv(monkeypatch):
  captured: dict[str, list[str]] = {}

  def fake_call(args):
    captured["args"] = list(args)
    return 0, json.dumps({"slots": [{"date": "2026-05-26", "start": "09:00", "end": "09:15"}]}).encode()

  monkeypatch.setattr(sched_mod, "_call", fake_call)
  doc = api.schedule("Standup", who=["a@x.com", "b@x.com"], duration_minutes=15, date="tomorrow")

  assert captured["args"] == [
    "schedule", "find-time",
    "--who", "a@x.com,b@x.com",
    "--duration", "15",
    "--date", "tomorrow",
  ]
  assert doc["ok"] is True
  assert doc["proposed_subject"] == "Standup"
  assert len(doc["slots"]) == 1
  assert doc["slots"][0]["start"] == "09:00"


def test_api_schedule_returns_empty_slots_on_failure(monkeypatch):
  monkeypatch.setattr(sched_mod, "_call", lambda args: (2, b'{"ok":false}'))
  doc = api.schedule("X", who=["a@x.com"])
  assert doc["ok"] is False
  assert doc["slots"] == []
  assert doc["error"]["code"] == "owa_sched_find_time_failed"


def test_api_schedule_commit_calls_send_invite(monkeypatch):
  captured: dict[str, dict] = {}

  def fake_send_invite(subject, **kwargs):
    captured["subject"] = subject
    captured["kwargs"] = kwargs
    return {"tool": "hugr", "command": "send invite", "ok": True, "exit_code": 0}

  monkeypatch.setattr(sched_mod, "send_invite", fake_send_invite)
  api.schedule_commit(
    "Standup",
    who=["a@x.com"],
    slot={"date": "2026-05-26", "start": "09:00", "end": "09:15"},
    location="A1",
  )
  assert captured["subject"] == "Standup"
  assert captured["kwargs"]["date"] == "2026-05-26"
  assert captured["kwargs"]["start"] == "09:00"
  assert captured["kwargs"]["end"] == "09:15"
  assert captured["kwargs"]["location"] == "A1"


def test_book_propose_cli_prints_proposal(monkeypatch, tmp_path: Path):
  _stub_config(tmp_path, monkeypatch)
  monkeypatch.setattr(
    api,
    "schedule",
    lambda intent, **kwargs: {
      "tool": "hugr",
      "command": "schedule",
      "ok": True,
      "exit_code": 0,
      "intent": intent,
      "proposed_subject": intent.strip(),
      "request": {"who": kwargs.get("who")},
      "slots": [{"date": "2026-05-26", "start": "09:00", "end": "09:15"}],
      "raw": None,
      "error": None,
    },
  )
  result = CliRunner().invoke(
    cli,
    ["book", "propose", "Standup", "--who", "a@x.com", "--duration", "15", "--date", "tomorrow", "--json"],
  )
  assert result.exit_code == 0
  payload = json.loads(result.output)
  assert payload["command"] == "schedule"
  assert payload["slots"][0]["start"] == "09:00"


def test_book_commit_requires_yes_in_json_mode(monkeypatch, tmp_path: Path):
  _stub_config(tmp_path, monkeypatch)
  result = CliRunner().invoke(
    cli,
    ["book", "commit", "Standup", "--who", "a@x.com", "--slot", "0", "--json"],
  )
  assert result.exit_code == 1
  payload = json.loads(result.output)
  assert payload["error"]["code"] == "confirmation_required"


def test_book_commit_emits_slot_unavailable_when_no_slots(monkeypatch, tmp_path: Path):
  _stub_config(tmp_path, monkeypatch)
  monkeypatch.setattr(
    api,
    "schedule",
    lambda intent, **kwargs: {
      "tool": "hugr",
      "command": "schedule",
      "ok": True,
      "exit_code": 0,
      "intent": intent,
      "proposed_subject": intent.strip(),
      "request": {},
      "slots": [],
      "raw": None,
      "error": None,
    },
  )
  result = CliRunner().invoke(
    cli,
    ["book", "commit", "Standup", "--who", "a@x.com", "--slot", "0", "--yes", "--json"],
  )
  assert result.exit_code == 4
  payload = json.loads(result.output)
  assert payload["error"]["code"] == "slot_unavailable"


def test_book_commit_creates_event_when_slot_present(monkeypatch, tmp_path: Path):
  _stub_config(tmp_path, monkeypatch)
  monkeypatch.setattr(
    api,
    "schedule",
    lambda intent, **kwargs: {
      "tool": "hugr",
      "command": "schedule",
      "ok": True,
      "exit_code": 0,
      "intent": intent,
      "proposed_subject": intent.strip(),
      "request": {},
      "slots": [{"date": "2026-05-26", "start": "09:00", "end": "09:15"}],
      "raw": None,
      "error": None,
    },
  )

  captured: dict[str, dict] = {}

  def fake_commit(intent, **kwargs):
    captured["intent"] = intent
    captured["kwargs"] = kwargs
    return {
      "tool": "hugr",
      "command": "send invite",
      "ok": True,
      "exit_code": 0,
      "request": {"subject": intent},
      "result": {"id": "evt-1"},
      "error": None,
    }

  monkeypatch.setattr(api, "schedule_commit", fake_commit)
  result = CliRunner().invoke(
    cli,
    [
      "book", "commit",
      "Standup",
      "--who", "a@x.com",
      "--slot", "0",
      "--yes",
      "--json",
    ],
  )
  assert result.exit_code == 0
  payload = json.loads(result.output)
  assert payload["ok"] is True
  assert captured["kwargs"]["slot"]["start"] == "09:00"

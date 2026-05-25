from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import hugr.api as api
from hugr.api import send as send_mod
from hugr.cli import cli


def _stub_config(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  cfg = tmp_path / "hugr" / "config.toml"
  cfg.parent.mkdir(parents=True)
  cfg.write_text("version: 1\n")


def test_api_send_mail_builds_argv_and_envelopes_result(monkeypatch):
  captured: dict[str, list[str]] = {}

  def fake_call(args):
    captured["args"] = list(args)
    return 0, b'{"ok":true,"id":"AAMkAG..."}'

  monkeypatch.setattr(send_mod, "_call", fake_call)
  doc = api.send_mail(
    ["a@example.com", "b@example.com"],
    "hi",
    "hello",
    cc=["c@example.com"],
    bcc=(),
    html=True,
  )

  assert captured["args"] == [
    "mail", "send",
    "--to", "a@example.com,b@example.com",
    "--subject", "hi",
    "--body", "hello",
    "--cc", "c@example.com",
    "--html",
  ]
  assert doc["tool"] == "hugr"
  assert doc["command"] == "send mail"
  assert doc["ok"] is True
  assert doc["exit_code"] == 0
  assert doc["request"]["to"] == ["a@example.com", "b@example.com"]
  assert doc["request"]["body_length"] == 5
  assert doc["error"] is None


def test_api_send_mail_failure_surfaces_error(monkeypatch):
  def fake_call(args):
    return 2, b'{"ok":false,"error":{"code":"auth"}}'

  monkeypatch.setattr(send_mod, "_call", fake_call)
  doc = api.send_mail(["a@example.com"], "hi", "x")

  assert doc["ok"] is False
  assert doc["exit_code"] == 2
  assert doc["error"]["code"] == "owa_mail_send_failed"


def test_api_send_invite_omits_unset_flags(monkeypatch):
  captured: dict[str, list[str]] = {}

  def fake_call(args):
    captured["args"] = list(args)
    return 0, b'{"id":"evt-1"}'

  monkeypatch.setattr(send_mod, "_call", fake_call)
  doc = api.send_invite("standup", date="tomorrow", start="09:00", end="09:15")

  assert captured["args"] == [
    "cal", "create",
    "--subject", "standup",
    "--date", "tomorrow",
    "--start", "09:00",
    "--end", "09:15",
  ]
  assert doc["command"] == "send invite"
  assert doc["ok"] is True
  assert doc["request"]["location"] is None
  assert doc["request"]["has_body"] is False


def test_send_mail_cli_requires_yes_in_json_mode(monkeypatch, tmp_path: Path):
  _stub_config(tmp_path, monkeypatch)
  monkeypatch.setattr(api, "send_mail", lambda *a, **k: pytest_fail_no_call(a, k))

  result = CliRunner().invoke(
    cli,
    ["send", "mail", "--to", "a@example.com", "--subject", "x", "--body", "y", "--json"],
  )
  assert result.exit_code == 1
  payload = json.loads(result.output)
  assert payload["ok"] is False
  assert payload["error"]["code"] == "confirmation_required"


def test_send_mail_cli_with_yes_calls_api_and_prints_envelope(monkeypatch, tmp_path: Path):
  _stub_config(tmp_path, monkeypatch)
  captured: dict[str, dict] = {}

  def fake_send_mail(to, subject, body, *, cc, bcc, html):
    captured["kwargs"] = {
      "to": list(to),
      "subject": subject,
      "body": body,
      "cc": list(cc),
      "bcc": list(bcc),
      "html": html,
    }
    return {
      "tool": "hugr",
      "command": "send mail",
      "ok": True,
      "exit_code": 0,
      "request": {"to": list(to)},
      "result": {"id": "AAMkAG..."},
      "error": None,
    }

  monkeypatch.setattr(api, "send_mail", fake_send_mail)

  result = CliRunner().invoke(
    cli,
    [
      "send", "mail",
      "--to", "a@example.com",
      "--cc", "c@example.com",
      "--subject", "subj",
      "--body", "hello",
      "--html",
      "--yes",
      "--json",
    ],
  )
  assert result.exit_code == 0
  payload = json.loads(result.output)
  assert payload["ok"] is True
  assert captured["kwargs"]["to"] == ["a@example.com"]
  assert captured["kwargs"]["cc"] == ["c@example.com"]
  assert captured["kwargs"]["html"] is True


def test_send_invite_cli_with_yes(monkeypatch, tmp_path: Path):
  _stub_config(tmp_path, monkeypatch)

  def fake_send_invite(subject, **kwargs):
    return {
      "tool": "hugr",
      "command": "send invite",
      "ok": True,
      "exit_code": 0,
      "request": {"subject": subject, **kwargs},
      "result": {"id": "evt-1"},
      "error": None,
    }

  monkeypatch.setattr(api, "send_invite", fake_send_invite)
  result = CliRunner().invoke(
    cli,
    [
      "send", "invite",
      "--subject", "Standup",
      "--date", "tomorrow",
      "--start", "09:00",
      "--end", "09:15",
      "--yes",
      "--json",
    ],
  )
  assert result.exit_code == 0
  payload = json.loads(result.output)
  assert payload["ok"] is True
  assert payload["command"] == "send invite"


def test_send_mail_cli_propagates_nonzero_exit(monkeypatch, tmp_path: Path):
  _stub_config(tmp_path, monkeypatch)

  monkeypatch.setattr(
    api,
    "send_mail",
    lambda *a, **k: {
      "tool": "hugr",
      "command": "send mail",
      "ok": False,
      "exit_code": 3,
      "request": {},
      "result": None,
      "error": {"code": "owa_mail_send_failed", "message": "auth", "hint": "hint"},
    },
  )
  result = CliRunner().invoke(
    cli,
    ["send", "mail", "--to", "a@example.com", "--subject", "x", "--body", "y", "--yes", "--json"],
  )
  assert result.exit_code == 3


def pytest_fail_no_call(args, kwargs):  # helper for the "must not call" assertion above
  raise AssertionError(f"api.send_mail should not be called; got args={args}, kwargs={kwargs}")

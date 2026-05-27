"""Tests for the shared hugr-conventions contract package."""
from __future__ import annotations

import io
import json

import pytest

from hugr_conventions import (
  DoctorFinding,
  DoctorPayload,
  EXIT_OK,
  EXIT_PARTIAL,
  EXIT_USER_ERROR,
  action_envelope,
  bind,
  data_error,
  emit_action,
  emit_data_error,
  emit_doctor,
  now_iso,
  redact,
  stream_progress,
  stream_result,
  stream_warning,
)


# --- redaction -------------------------------------------------------------

def test_redact_jwt_like():
  jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJjYW5hcnkifQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
  assert jwt not in redact(f"x={jwt}")


def test_redact_bearer():
  assert "abc123def456" not in redact("Authorization: Bearer abc123def456")


def test_redact_token_fields():
  out = redact('{"access_token":"xyz","refresh_token":"qrs"}')
  assert "xyz" not in out and "qrs" not in out


def test_redact_body_fields():
  out = redact('{"body":"private message text"}')
  assert "private message text" not in out


def test_redaction_sentinel_does_not_leak():
  jwt = "eyJfake." + "CANARY_SECRET_xxxx" + "." + "padding1234"
  assert "CANARY_SECRET_xxxx" not in redact(f"Authorization: Bearer {jwt}")


def test_redact_handles_non_string():
  assert redact(None) == ""
  assert redact(42) == "42"


# --- action envelope -------------------------------------------------------

def test_action_envelope_shape():
  env = action_envelope(
    tool="yaams", version="0.2.0", command="ingest", ok=True, stats={"sources": 3}
  )
  assert env["tool"] == "yaams"
  assert env["version"] == "0.2.0"
  assert env["command"] == "ingest"
  assert env["ok"] is True
  assert env["stats"]["sources"] == 3
  assert env["error"] is None


def test_action_envelope_failure():
  env = action_envelope(
    tool="yaams", version="0.2.0", command="ingest", ok=False,
    error={"code": "x", "message": "boom"},
  )
  assert env["ok"] is False
  assert env["error"]["code"] == "x"


def test_version_callable_resolved_lazily():
  calls = []

  def ver() -> str:
    calls.append(1)
    return "9.9.9"

  env = action_envelope(tool="t", version=ver, command="c", ok=True)
  assert env["version"] == "9.9.9"
  assert calls == [1]


def test_emit_action_one_line():
  buf = io.StringIO()
  emit_action(action_envelope(tool="t", version="1", command="x", ok=True), stream=buf)
  out = buf.getvalue()
  assert out.endswith("\n") and out.count("\n") == 1
  assert json.loads(out)["command"] == "x"


# --- data error ------------------------------------------------------------

def test_data_error_shape():
  err = data_error(tool="owa-cal", version="0.2.0", command="events", code="c", message="m", hint="h")
  assert err["tool"] == "owa-cal"
  assert err["ok"] is False
  assert err["error"]["hint"] == "h"


def test_data_error_omits_empty_hint():
  err = data_error(tool="t", version="1", command="x", code="c", message="m")
  assert "hint" not in err["error"]


def test_emit_data_error_one_line():
  buf = io.StringIO()
  emit_data_error(data_error(tool="t", version="1", command="x", code="c", message="m"), stream=buf)
  assert json.loads(buf.getvalue())["ok"] is False


# --- streaming -------------------------------------------------------------

def test_stream_progress_schema():
  buf = io.StringIO()
  stream_progress(source="yaams", stage="ingest", done=10, total=100, stream=buf)
  payload = json.loads(buf.getvalue())
  assert payload["type"] == "progress"
  assert payload["source"] == "yaams"
  assert payload["done"] == 10
  assert "ts" in payload


def test_stream_warning_redacts():
  buf = io.StringIO()
  stream_warning("Bearer secrettoken in stack trace", stream=buf)
  assert "secrettoken" not in json.loads(buf.getvalue())["message"]


def test_stream_result_carries_envelope():
  buf = io.StringIO()
  stream_result(action_envelope(tool="t", version="1", command="ingest", ok=True), stream=buf)
  payload = json.loads(buf.getvalue())
  assert payload["type"] == "result"
  assert payload["command"] == "ingest"


def test_now_iso_is_utc_zulu():
  assert now_iso().endswith("Z")


# --- doctor ----------------------------------------------------------------

def test_doctor_payload_minimal():
  d = DoctorPayload(tool="yaams").to_dict()
  assert d["tool"] == "yaams"
  assert d["version"] == "0.0.0"
  assert d["findings"] == []


def test_doctor_payload_full():
  d = DoctorPayload(
    tool="yaams",
    version="0.2.0",
    config_path="/etc/hugr/config.toml",
    models={"embedding": "bge-m3"},
    findings=[DoctorFinding(id="x", severity="error", message="m", hint="fix it")],
  ).to_dict()
  assert d["config_path"] == "/etc/hugr/config.toml"
  assert d["models"]["embedding"] == "bge-m3"
  assert d["findings"][0]["severity"] == "error"
  assert d["findings"][0]["hint"] == "fix it"


def test_doctor_exit_codes():
  assert DoctorPayload(tool="t").exit_code() == EXIT_OK
  d = DoctorPayload(tool="t", findings=[DoctorFinding(id="x", severity="error", message="m")])
  assert d.exit_code() == EXIT_USER_ERROR


def test_emit_doctor_json_returns_exit_code():
  buf = io.StringIO()
  rc = emit_doctor(DoctorPayload(tool="t", version="1"), as_json=True, stream=buf)
  assert rc == EXIT_OK
  assert json.loads(buf.getvalue())["tool"] == "t"


def test_emit_doctor_human_renders_findings():
  buf = io.StringIO()
  payload = DoctorPayload(
    tool="t", version="1",
    findings=[DoctorFinding(id="boom", severity="error", message="bad")],
  )
  rc = emit_doctor(payload, as_json=False, stream=buf)
  assert rc == EXIT_USER_ERROR
  assert "boom" in buf.getvalue()
  with pytest.raises(json.JSONDecodeError):
    json.loads(buf.getvalue())


# --- exit codes ------------------------------------------------------------

def test_exit_constants():
  assert (EXIT_OK, EXIT_USER_ERROR, EXIT_PARTIAL) == (0, 1, 5)


# --- bound API -------------------------------------------------------------

def test_bind_fills_tool_and_version():
  C = bind("owa-mail", "0.2.0")
  env = C.action_envelope(command="send", ok=True)
  assert env["tool"] == "owa-mail"
  assert env["version"] == "0.2.0"
  assert C.version == "0.2.0"


def test_bind_data_error():
  C = bind("owa-cal", lambda: "0.2.0")
  err = C.data_error(command="events", code="auth", message="expired")
  assert err["tool"] == "owa-cal" and err["ok"] is False


def test_bind_doctor_payload_defaults_and_override():
  C = bind("sheep", "0.4.1")
  assert C.doctor_payload().tool == "sheep"
  # explicit tool overrides the bound one
  assert C.doctor_payload(tool="other").tool == "other"


def test_bind_reexports_emitters():
  C = bind("t", "1")
  buf = io.StringIO()
  C.emit_action(C.action_envelope(command="x", ok=True), stream=buf)
  assert json.loads(buf.getvalue())["ok"] is True

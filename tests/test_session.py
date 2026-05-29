from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from click.testing import CliRunner

from hugr import session
from hugr.cli import cli


def _isolate(tmp_path: Path, monkeypatch) -> None:
  """Point HUGR_HOME + XDG_CONFIG_HOME at tmp_path so no real state leaks."""
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "hugr-home"))
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
  monkeypatch.delenv("HUGR_SESSION", raising=False)


def test_start_creates_meta_under_hugr_home(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  meta = session.start_session()
  assert meta.id
  meta_file = session.session_dir(meta.id) / "meta.json"
  assert meta_file.is_file()
  doc = json.loads(meta_file.read_text())
  assert doc["id"] == meta.id
  assert doc["ttl_seconds"] == session.SESSION_TTL_SECONDS


def test_end_removes_session_dir(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  meta = session.start_session()
  assert session.session_dir(meta.id).is_dir()
  assert session.end_session(meta.id) is True
  assert not session.session_dir(meta.id).exists()
  assert session.end_session(meta.id) is False  # idempotent


def test_gc_removes_stale_sessions(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  fresh = session.start_session()
  stale = session.start_session(ttl_seconds=1)

  # Backdate stale's last_used_at past its TTL
  stale.last_used_at = "2020-01-01T00:00:00Z"
  session.write_meta(stale)

  removed = session.gc_stale()
  assert stale.id in removed
  assert fresh.id not in removed


def test_is_stale_uses_ttl(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  meta = session.start_session(ttl_seconds=60)
  assert not session.is_stale(meta)
  later = datetime.now(timezone.utc) + timedelta(seconds=120)
  assert session.is_stale(meta, now=later)


def test_recall_writes_last_recall_when_session_active(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  meta = session.start_session()
  monkeypatch.setenv("HUGR_SESSION", meta.id)

  # Stub _call inside fused
  from hugr.api import fused
  monkeypatch.setattr(fused, "_call", lambda args, **k: (0, b'{"items":[]}'))

  doc = fused.recall("hello", live=False)
  assert doc["query"] == "hello"

  cached = session.read_last_recall(meta.id)
  assert cached is not None
  assert cached["query"] == "hello"


def test_inbox_writes_working_set_when_session_active(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  meta = session.start_session()
  monkeypatch.setenv("HUGR_SESSION", meta.id)

  from hugr.api import fused
  responses = iter([
    b'[{"id":"m1"},{"id":"m2"}]',  # mail list
    b'[{"id":"e1"}]',                # cal events
    b'{"loops":[{"id":"l1"}]}',      # ledger loops
    b'[]',                            # yaams promote list
  ])
  monkeypatch.setattr(fused, "_call", lambda args, **k: (0, next(responses)))

  fused.inbox()
  items = session.read_working_set(meta.id)
  ids = sorted(it["id"] for it in items if it.get("id"))
  assert ids == ["e1", "l1", "m1", "m2"]


def test_recall_skips_session_write_when_unset(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  # No HUGR_SESSION
  from hugr.api import fused
  monkeypatch.setattr(fused, "_call", lambda args, **k: (0, b"[]"))
  fused.recall("hi", live=False)
  # Nothing written
  assert not session.sessions_root().is_dir() or not any(session.sessions_root().iterdir())


def test_cli_session_start_emits_envelope(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  result = CliRunner().invoke(cli, ["session", "start", "--json"])
  assert result.exit_code == 0
  payload = json.loads(result.output)
  assert payload["ok"] is True
  assert payload["session"]["id"]
  assert payload["hint"].startswith("export HUGR_SESSION=")


def test_cli_session_status_lists_active(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  meta = session.start_session()
  monkeypatch.setenv("HUGR_SESSION", meta.id)
  result = CliRunner().invoke(cli, ["session", "status", "--json"])
  assert result.exit_code == 0
  payload = json.loads(result.output)
  assert payload["current_session_id"] == meta.id
  assert payload["active"]["id"] == meta.id


def test_cli_session_end_without_id_errors(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  result = CliRunner().invoke(cli, ["session", "end", "--json"])
  assert result.exit_code == 1
  payload = json.loads(result.output)
  assert payload["error"]["code"] == "no_active_session"


def test_cli_session_gc_removes_stale(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  stale = session.start_session(ttl_seconds=1)
  stale.last_used_at = "2020-01-01T00:00:00Z"
  session.write_meta(stale)
  result = CliRunner().invoke(cli, ["session", "gc", "--json"])
  assert result.exit_code == 0
  payload = json.loads(result.output)
  assert stale.id in payload["removed"]

"""Plan 03.4 web route tests: /session, /api/*, SSE."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="web extra not installed")

from fastapi.testclient import TestClient

import hugr.api as api
from hugr import session as session_mod
from hugr.web.app import create_app


def test_session_index_returns_session_status(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "hugr-home"))
  monkeypatch.delenv("HUGR_SESSION", raising=False)
  meta = session_mod.start_session()

  client = TestClient(create_app())
  response = client.get("/session", headers={"accept": "application/json"})
  assert response.status_code == 200
  payload = response.json()
  ids = [s["id"] for s in payload.get("sessions") or []]
  assert meta.id in ids


def test_session_detail_returns_meta_and_working_set(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "hugr-home"))
  monkeypatch.delenv("HUGR_SESSION", raising=False)
  meta = session_mod.start_session()
  session_mod.write_working_set(meta.id, [{"source": "owa-mail", "id": "m1"}])

  client = TestClient(create_app())
  response = client.get(f"/session/{meta.id}", headers={"accept": "application/json"})
  assert response.status_code == 200
  payload = response.json()
  assert payload["ok"] is True
  assert payload["meta"]["id"] == meta.id
  assert payload["working_set"][0]["id"] == "m1"


def test_session_detail_unknown_returns_404(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "hugr-home"))
  client = TestClient(create_app())
  response = client.get("/session/does-not-exist", headers={"accept": "application/json"})
  assert response.status_code == 404
  assert response.json()["ok"] is False


def test_api_recall_returns_json_without_accept_header(monkeypatch):
  monkeypatch.setattr(api, "recall", lambda q: {"tool": "hugr", "command": "recall", "query": q})
  client = TestClient(create_app())
  response = client.get("/api/recall?q=easter")
  assert response.status_code == 200
  assert response.json()["query"] == "easter"


def test_api_inbox_mirrors_html_route(monkeypatch):
  monkeypatch.setattr(api, "inbox", lambda: {"tool": "hugr", "command": "inbox", "sources": []})
  client = TestClient(create_app())

  html_resp = client.get("/inbox", headers={"accept": "application/json"})
  api_resp = client.get("/api/inbox")
  assert html_resp.json() == api_resp.json()


def test_api_find_mirrors_html_route(monkeypatch):
  monkeypatch.setattr(api, "find", lambda kind, q: {"tool": "hugr", "kind": kind, "query": q})
  client = TestClient(create_app())

  html_resp = client.get("/find?kind=person&q=nina", headers={"accept": "application/json"})
  api_resp = client.get("/api/find?kind=person&q=nina")
  assert html_resp.json() == api_resp.json()


def test_sse_ingest_streams_ndjson(monkeypatch):
  """Stub asyncio.create_subprocess_exec so the SSE handler is exercised end-to-end."""
  import asyncio

  class _StubProc:
    def __init__(self, lines):
      self._lines = list(lines)
      self.returncode = 0

    @property
    def stdout(self):
      return self

    @property
    def stderr(self):
      return self

    def __aiter__(self):
      return self

    async def __anext__(self):
      if not self._lines:
        raise StopAsyncIteration
      return self._lines.pop(0)

    async def wait(self):
      return 0

  async def fake_exec(*args, **kwargs):
    return _StubProc([
      b'{"type":"progress","done":1,"total":3}\n',
      b'{"type":"progress","done":2,"total":3}\n',
      b'{"type":"result","ok":true,"exit_code":0}\n',
    ])

  monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)

  client = TestClient(create_app())
  with client.stream("GET", "/api/stream/ingest") as response:
    assert response.status_code == 200
    body = b"".join(response.iter_bytes()).decode()
  assert 'data: {"type":"progress","done":1,"total":3}' in body
  assert 'event: done' in body
  assert '"exit_code": 0' in body

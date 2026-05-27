"""Regression tests for the web surface auth + CSRF hardening (review 2026-05-27)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="web extra not installed")

import asyncio

from fastapi.testclient import TestClient

import hugr.api as api
from hugr.web import app as web_app
from hugr.web.app import create_app


# --- bearer-token auth (HUGR_WEB_TOKEN) -----------------------------------


def test_no_token_means_open_app():
  client = TestClient(create_app())
  assert client.get("/inbox").status_code == 200


def test_token_app_rejects_unauthenticated():
  client = TestClient(create_app(token="s3cret"))
  resp = client.get("/inbox")
  assert resp.status_code == 401
  assert resp.json()["error"]["code"] == "unauthorized"


def test_token_app_allows_correct_bearer(monkeypatch):
  monkeypatch.setattr(api, "inbox", lambda: {"tool": "hugr", "ok": True})
  client = TestClient(create_app(token="s3cret"))
  resp = client.get("/inbox", headers={"authorization": "Bearer s3cret"})
  assert resp.status_code == 200


def test_token_app_rejects_wrong_bearer():
  client = TestClient(create_app(token="s3cret"))
  resp = client.get("/inbox", headers={"authorization": "Bearer nope"})
  assert resp.status_code == 401


def test_healthz_open_even_with_token():
  client = TestClient(create_app(token="s3cret"))
  assert client.get("/healthz").status_code == 200


def test_token_app_guards_mutations(monkeypatch):
  called: list[bool] = []
  monkeypatch.setattr(api, "send_mail", lambda *a, **k: called.append(True) or {})
  client = TestClient(create_app(token="s3cret"))
  resp = client.post(
    "/send/mail",
    data={"to": "a@x.com", "subject": "x", "body": "y", "confirm": "on"},
    headers={"accept": "application/json"},
  )
  assert resp.status_code == 401
  assert called == []


# --- CSRF origin checks on mutations --------------------------------------


def test_cross_origin_mutation_blocked(monkeypatch):
  called: list[bool] = []
  monkeypatch.setattr(api, "send_mail", lambda *a, **k: called.append(True) or {})
  client = TestClient(create_app())
  resp = client.post(
    "/send/mail",
    data={"to": "a@x.com", "subject": "x", "body": "y", "confirm": "on"},
    headers={"accept": "application/json", "origin": "http://evil.example"},
  )
  assert resp.status_code == 403
  assert resp.json()["error"]["code"] == "cross_origin_blocked"
  assert called == []


def test_same_origin_mutation_allowed(monkeypatch):
  captured: dict[str, object] = {}

  def fake_send_mail(to, subject, body, *, cc, bcc, html):
    captured["to"] = list(to)
    return {"tool": "hugr", "command": "send mail", "ok": True, "exit_code": 0}

  monkeypatch.setattr(api, "send_mail", fake_send_mail)
  client = TestClient(create_app())
  resp = client.post(
    "/send/mail",
    data={"to": "a@x.com", "subject": "x", "body": "y", "confirm": "on"},
    headers={"accept": "application/json", "origin": "http://testserver"},
  )
  assert resp.status_code == 200
  assert captured["to"] == ["a@x.com"]


def test_cross_origin_referer_blocked(monkeypatch):
  called: list[bool] = []
  monkeypatch.setattr(api, "remember", lambda *a, **k: called.append(True) or {})
  client = TestClient(create_app())
  resp = client.post(
    "/remember",
    data={"fact": "x", "confirm": "on"},
    headers={"accept": "application/json", "referer": "http://evil.example/page"},
  )
  assert resp.status_code == 403
  assert called == []


# --- SSE ingest must not deadlock on a noisy child's stderr ----------------


def test_sse_ingest_does_not_pipe_stderr(monkeypatch):
  """A PIPE'd-but-undrained stderr could block the child forever; the
  stream redirects it to DEVNULL instead."""
  captured: dict[str, object] = {}

  class _FakeStdout:
    def __init__(self, lines: list[bytes]) -> None:
      self._lines = list(lines)

    def __aiter__(self):
      return self

    async def __anext__(self) -> bytes:
      if not self._lines:
        raise StopAsyncIteration
      return self._lines.pop(0)

  class _FakeProc:
    def __init__(self) -> None:
      self.stdout = _FakeStdout([b'{"ok": true}\n'])
      self.returncode = 0

    async def wait(self) -> int:
      return 0

  async def _fake_exec(*args, **kwargs):
    captured["stderr"] = kwargs.get("stderr")
    return _FakeProc()

  monkeypatch.setattr(web_app.asyncio, "create_subprocess_exec", _fake_exec)

  async def _drive() -> list[str]:
    return [frame async for frame in web_app._stream_ingest([])]

  frames = asyncio.run(_drive())
  assert captured["stderr"] is asyncio.subprocess.DEVNULL
  assert any('"ok": true' in frame for frame in frames)

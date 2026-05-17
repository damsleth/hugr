from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="web extra not installed")

from fastapi.testclient import TestClient

import mnem.api as api
from mnem.web.app import create_app


def test_healthz_route():
  client = TestClient(create_app())
  response = client.get("/healthz")
  assert response.status_code == 200
  assert response.json()["ok"] is True


def test_ask_json_parity(monkeypatch):
  expected = {"tool": "mnem", "command": "ask", "query": "easter"}
  monkeypatch.setattr(api, "ask", lambda q: {**expected, "query": q})
  client = TestClient(create_app())

  response = client.get("/ask?q=easter", headers={"accept": "application/json"})
  assert response.status_code == 200
  assert response.json() == expected


def test_find_json_route(monkeypatch):
  monkeypatch.setattr(api, "find", lambda kind, q: {"tool": "mnem", "command": "find", "kind": kind, "query": q})
  client = TestClient(create_app())

  response = client.get("/find?kind=person&q=nina", headers={"accept": "application/json"})
  assert response.status_code == 200
  assert response.json()["kind"] == "person"


def test_inbox_json_route(monkeypatch):
  monkeypatch.setattr(api, "inbox", lambda: {"tool": "mnem", "command": "inbox", "sources": []})
  client = TestClient(create_app())

  response = client.get("/inbox", headers={"accept": "application/json"})
  assert response.status_code == 200
  assert response.json()["command"] == "inbox"

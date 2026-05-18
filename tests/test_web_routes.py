from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="web extra not installed")

from fastapi.testclient import TestClient

import hugr.api as api
from hugr.web.app import create_app


def test_healthz_route():
  client = TestClient(create_app())
  response = client.get("/healthz")
  assert response.status_code == 200
  assert response.json()["ok"] is True


def test_ask_json_parity(monkeypatch):
  expected = {"tool": "hugr", "command": "recall", "query": "easter"}
  monkeypatch.setattr(api, "recall", lambda q: {**expected, "query": q})
  client = TestClient(create_app())

  response = client.get("/recall?q=easter", headers={"accept": "application/json"})
  assert response.status_code == 200
  assert response.json() == expected


def test_find_json_route(monkeypatch):
  monkeypatch.setattr(api, "find", lambda kind, q: {"tool": "hugr", "command": "find", "kind": kind, "query": q})
  client = TestClient(create_app())

  response = client.get("/find?kind=person&q=nina", headers={"accept": "application/json"})
  assert response.status_code == 200
  assert response.json()["kind"] == "person"


def test_inbox_json_route(monkeypatch):
  monkeypatch.setattr(api, "inbox", lambda: {"tool": "hugr", "command": "inbox", "sources": []})
  client = TestClient(create_app())

  response = client.get("/inbox", headers={"accept": "application/json"})
  assert response.status_code == 200
  assert response.json()["command"] == "inbox"

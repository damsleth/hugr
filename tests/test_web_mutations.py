"""Plan 03.5 web mutation tests."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="web extra not installed")

from fastapi.testclient import TestClient

import hugr.api as api
from hugr.web.app import create_app


def test_send_mail_get_renders_form():
  client = TestClient(create_app())
  response = client.get("/send/mail")
  assert response.status_code == 200
  assert "I confirm" in response.text
  assert 'name="to"' in response.text


def test_send_mail_post_without_confirm_returns_412(monkeypatch):
  called: list[bool] = []
  monkeypatch.setattr(api, "send_mail", lambda *a, **k: called.append(True) or {})
  client = TestClient(create_app())
  response = client.post(
    "/send/mail",
    data={"to": "a@x.com", "subject": "x", "body": "y"},
    headers={"accept": "application/json"},
  )
  assert response.status_code == 412
  assert response.json()["error"]["code"] == "confirmation_required"
  assert called == []


def test_send_mail_post_with_confirm_calls_api(monkeypatch):
  captured: dict[str, object] = {}

  def fake_send_mail(to, subject, body, *, cc, bcc, html):
    captured.update(to=list(to), subject=subject, body=body, cc=list(cc), bcc=list(bcc), html=html)
    return {"tool": "hugr", "command": "send mail", "ok": True, "exit_code": 0}

  monkeypatch.setattr(api, "send_mail", fake_send_mail)
  client = TestClient(create_app())
  response = client.post(
    "/send/mail",
    data={
      "to": "a@x.com, b@x.com",
      "cc": "c@x.com",
      "subject": "subj",
      "body": "hello",
      "html": "on",
      "confirm": "on",
    },
    headers={"accept": "application/json"},
  )
  assert response.status_code == 200
  assert captured["to"] == ["a@x.com", "b@x.com"]
  assert captured["cc"] == ["c@x.com"]
  assert captured["html"] is True


def test_send_invite_post_with_confirm(monkeypatch):
  captured: dict[str, object] = {}

  def fake_send_invite(subject, **kwargs):
    captured["subject"] = subject
    captured.update(kwargs)
    return {"tool": "hugr", "command": "send invite", "ok": True, "exit_code": 0}

  monkeypatch.setattr(api, "send_invite", fake_send_invite)
  client = TestClient(create_app())
  response = client.post(
    "/send/invite",
    data={
      "subject": "Standup",
      "date": "tomorrow",
      "start": "09:00",
      "end": "09:15",
      "confirm": "on",
    },
    headers={"accept": "application/json"},
  )
  assert response.status_code == 200
  assert captured["subject"] == "Standup"
  assert captured["date"] == "tomorrow"
  assert captured["location"] is None


def test_remember_post_with_confirm(monkeypatch):
  captured: dict[str, object] = {}

  def fake_remember(fact, *, note_type, links, yes):
    captured.update(fact=fact, note_type=note_type, links=list(links), yes=yes)
    return {"tool": "hugr", "command": "remember", "ok": True, "exit_code": 0}

  monkeypatch.setattr(api, "remember", fake_remember)
  client = TestClient(create_app())
  response = client.post(
    "/remember",
    data={"fact": "Nina prefers early flights", "links": "person:nina, topic:travel", "confirm": "on"},
    headers={"accept": "application/json"},
  )
  assert response.status_code == 200
  assert captured["fact"].startswith("Nina")
  assert captured["links"] == ["person:nina", "topic:travel"]
  assert captured["yes"] is True


def test_send_mail_post_propagates_failure_status(monkeypatch):
  monkeypatch.setattr(
    api,
    "send_mail",
    lambda *a, **k: {"tool": "hugr", "command": "send mail", "ok": False, "exit_code": 3, "error": {"code": "x", "message": "y", "hint": "z"}},
  )
  client = TestClient(create_app())
  response = client.post(
    "/send/mail",
    data={"to": "a@x.com", "subject": "x", "body": "y", "confirm": "on"},
    headers={"accept": "application/json"},
  )
  assert response.status_code == 502
  assert response.json()["ok"] is False

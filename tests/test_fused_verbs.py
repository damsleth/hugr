from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

import hugr.api as api
from hugr.api import fused
from hugr.cli import cli


def test_api_ask_fuses_yaams_calendar_and_mail(monkeypatch):
  calls: list[list[str]] = []

  def fake_call(args, **kwargs):
    calls.append(list(args))
    return 0, json.dumps({"tool": args[0], "items": [{"id": "1"}]}).encode()

  monkeypatch.setattr(fused, "_call", fake_call)
  doc = api.recall("easter dinner")

  assert doc["command"] == "recall"
  assert [item["source"] for item in doc["sources"]] == ["yaams", "owa-cal", "owa-mail"]
  assert len(doc["citations"]) == 3
  assert calls == [
    ["query", "easter dinner"],
    ["cal", "events", "--search", "easter dinner"],
    ["mail", "search", "easter dinner"],
  ]


def test_api_find_routes_person_to_people_find(monkeypatch):
  captured: dict[str, list[str]] = {}

  def fake_call(args, **kwargs):
    captured["args"] = list(args)
    return 0, b'{"people":[]}'

  monkeypatch.setattr(fused, "_call", fake_call)
  doc = api.find("person", "nina")

  assert doc["source"]["source"] == "owa-people"
  # owa-people's real subcommand is `find`, not `lookup`.
  assert captured["args"] == ["people", "find", "nina"]


def test_api_inbox_queries_four_sources(monkeypatch):
  calls: list[list[str]] = []

  def fake_call(args, **kwargs):
    calls.append(list(args))
    return 0, b"[]"

  monkeypatch.setattr(fused, "_call", fake_call)
  doc = api.inbox()

  assert doc["command"] == "inbox"
  assert calls == [
    ["mail", "list", "--unread"],
    ["cal", "events", "--today"],
    ["ledger", "loops"],
    ["promote", "list"],
  ]


def test_api_remember_returns_action_envelope(monkeypatch):
  captured: dict[str, list[str]] = {}

  def fake_call(args, **kwargs):
    captured["args"] = list(args)
    return 0, b'{"ok":true}'

  monkeypatch.setattr(fused, "_call", fake_call)
  doc = api.remember("Nina prefers early flights", links=["person:nina"], yes=True)

  assert doc["ok"] is True
  assert doc["exit_code"] == 0
  assert captured["args"] == [
    "ledger",
    "notes",
    "add",
    "--type",
    "fact",
    "--link",
    "person:nina",
    "--yes",
    "Nina prefers early flights",
  ]


def test_ask_cli_prints_json(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  cfg = tmp_path / "hugr" / "config.yaml"
  cfg.parent.mkdir(parents=True)
  cfg.write_text("version: 1\n")

  monkeypatch.setattr(api, "recall", lambda question, **_: {"tool": "hugr", "command": "recall", "query": question})

  result = CliRunner().invoke(cli, ["recall", "what", "changed"])
  assert result.exit_code == 0
  assert json.loads(result.output)["query"] == "what changed"


def test_ask_cli_first_run_hint(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  result = CliRunner().invoke(cli, ["recall", "anything"])
  assert result.exit_code == 4
  combined = result.output + (result.stderr_bytes or b"").decode("utf-8", "ignore")
  assert "hugr init" in combined

"""F6 - M365 profiles stanza in hugr doctor.

Tests:
- When owa-piggy is not installed (FileNotFoundError), the stanza is
  present in JSON as ``m365_profiles: []`` and the human render says
  "not configured".
- When owa-piggy returns a valid JSON list, the stanza lists each
  profile with name, token_expires_at, and is_default.
- ``default_owa_profile`` from the master config drives the is_default
  flag on the matching profile.
- ``hugr doctor --json`` includes the ``m365_profiles`` key at the top
  level of the returned document.
"""
from __future__ import annotations

import json
import subprocess
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from hugr.cli import cli
from hugr.commands.doctor import build_report, run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(stdout: str, returncode: int = 0) -> MagicMock:
  """Return a mock subprocess.CompletedProcess."""
  m = MagicMock()
  m.returncode = returncode
  m.stdout = stdout
  return m


def _patch_fanout(monkeypatch):
  """Replace the binary fan-out with a single no-op stub so tests are fast."""
  from hugr.commands import doctor as doc_mod
  monkeypatch.setattr(doc_mod, "_FANOUT", [])


# ---------------------------------------------------------------------------
# Unit: _m365_profiles()
# ---------------------------------------------------------------------------

class TestM365ProfilesUnit:
  def test_returns_empty_when_owa_piggy_not_found(self, monkeypatch):
    from hugr.commands.doctor import _m365_profiles
    with patch("subprocess.run", side_effect=FileNotFoundError):
      result = _m365_profiles()
    assert result == []

  def test_returns_empty_when_subprocess_times_out(self, monkeypatch):
    from hugr.commands.doctor import _m365_profiles
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("owa-piggy", 10)):
      result = _m365_profiles()
    assert result == []

  def test_returns_empty_when_returncode_nonzero(self):
    from hugr.commands.doctor import _m365_profiles
    proc = _make_proc(stdout="", returncode=1)
    with patch("subprocess.run", return_value=proc):
      result = _m365_profiles()
    assert result == []

  def test_returns_empty_when_stdout_not_json(self):
    from hugr.commands.doctor import _m365_profiles
    proc = _make_proc(stdout="not json at all")
    with patch("subprocess.run", return_value=proc):
      result = _m365_profiles()
    assert result == []

  def test_parses_list_output(self, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from hugr.commands.doctor import _m365_profiles
    payload = json.dumps([
      {"name": "work", "token_expires_at": "2026-06-01T12:00:00Z"},
      {"name": "personal", "token_expires_at": None},
    ])
    proc = _make_proc(stdout=payload)
    with patch("subprocess.run", return_value=proc):
      result = _m365_profiles()
    assert len(result) == 2
    assert result[0]["name"] == "work"
    assert result[0]["token_expires_at"] == "2026-06-01T12:00:00Z"
    assert result[0]["is_default"] is False
    assert result[1]["name"] == "personal"
    assert result[1]["token_expires_at"] is None

  def test_parses_wrapper_dict_output(self, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from hugr.commands.doctor import _m365_profiles
    payload = json.dumps({
      "profiles": [{"name": "swon", "token_expires_at": "2026-06-01T00:00:00Z"}]
    })
    proc = _make_proc(stdout=payload)
    with patch("subprocess.run", return_value=proc):
      result = _m365_profiles()
    assert len(result) == 1
    assert result[0]["name"] == "swon"

  def test_is_default_flag_set_from_master_config(self, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # Write a master config that names "work" as default.
    master = tmp_path / "hugr" / "config.yaml"
    master.parent.mkdir(parents=True)
    master.write_text("version: 1\ndefault_owa_profile: work\n")

    from hugr.commands.doctor import _m365_profiles
    payload = json.dumps([
      {"name": "work"},
      {"name": "personal"},
    ])
    proc = _make_proc(stdout=payload)
    with patch("subprocess.run", return_value=proc):
      result = _m365_profiles()

    by_name = {p["name"]: p for p in result}
    assert by_name["work"]["is_default"] is True
    assert by_name["personal"]["is_default"] is False


# ---------------------------------------------------------------------------
# Integration: build_report() includes m365_profiles key
# ---------------------------------------------------------------------------

class TestBuildReportM365:
  def test_m365_profiles_key_present_when_owa_not_installed(self, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _patch_fanout(monkeypatch)
    with patch("subprocess.run", side_effect=FileNotFoundError):
      doc, _code = build_report()
    assert "m365_profiles" in doc
    assert doc["m365_profiles"] == []

  def test_m365_profiles_key_populated_when_owa_returns_profiles(self, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _patch_fanout(monkeypatch)
    payload = json.dumps([{"name": "work"}, {"name": "swon"}])
    proc = _make_proc(stdout=payload)
    with patch("subprocess.run", return_value=proc):
      doc, _code = build_report()
    assert len(doc["m365_profiles"]) == 2
    names = {p["name"] for p in doc["m365_profiles"]}
    assert names == {"work", "swon"}


# ---------------------------------------------------------------------------
# Integration: human render includes the stanza
# ---------------------------------------------------------------------------

class TestDoctorHumanRenderM365:
  def test_stanza_says_not_configured_when_no_profiles(self, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _patch_fanout(monkeypatch)
    with patch("subprocess.run", side_effect=FileNotFoundError):
      buf = StringIO()
      run(as_json=False, stream=buf)
    output = buf.getvalue()
    assert "M365 profiles" in output
    assert "not configured" in output

  def test_stanza_lists_profiles_when_present(self, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _patch_fanout(monkeypatch)
    payload = json.dumps([
      {"name": "work", "token_expires_at": "2026-06-01T12:00:00Z"},
      {"name": "personal"},
    ])
    proc = _make_proc(stdout=payload)
    with patch("subprocess.run", return_value=proc):
      buf = StringIO()
      run(as_json=False, stream=buf)
    output = buf.getvalue()
    assert "M365 profiles" in output
    assert "work" in output
    assert "personal" in output
    assert "2026-06-01T12:00:00Z" in output

  def test_default_tag_appears_next_to_default_profile(self, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    master = tmp_path / "hugr" / "config.yaml"
    master.parent.mkdir(parents=True)
    master.write_text("version: 1\ndefault_owa_profile: work\n")
    _patch_fanout(monkeypatch)
    payload = json.dumps([{"name": "work"}, {"name": "personal"}])
    proc = _make_proc(stdout=payload)
    with patch("subprocess.run", return_value=proc):
      buf = StringIO()
      run(as_json=False, stream=buf)
    output = buf.getvalue()
    assert "[default]" in output
    # The [default] tag should appear on the work line, not personal.
    for line in output.splitlines():
      if "personal" in line:
        assert "[default]" not in line
      if "work" in line and "M365" not in line:
        assert "[default]" in line


# ---------------------------------------------------------------------------
# CLI surface: hugr doctor --json includes m365_profiles
# ---------------------------------------------------------------------------

class TestDoctorJsonCLI:
  def test_json_output_contains_m365_profiles(self, monkeypatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _patch_fanout(monkeypatch)
    with patch("subprocess.run", side_effect=FileNotFoundError):
      result = CliRunner().invoke(cli, ["doctor", "--json"])
    assert result.exit_code in (0, 1), result.output
    doc = json.loads(result.output)
    assert "m365_profiles" in doc

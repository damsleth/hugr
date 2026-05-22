from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from hugr.cli import cli
from hugr.config import read_master
from hugr.sources import ProbeResult


def _stub_probes() -> list[ProbeResult]:
  return [
    ProbeResult("imessage", False, "not found"),
    ProbeResult("email", False, "not found"),
    ProbeResult("signal", False, "not found"),
    ProbeResult("github", False, "not found"),
    ProbeResult("owa_piggy", False, "not configured"),
    ProbeResult("notes", False, "not found"),
    ProbeResult("tier2_ledger", False, "not configured"),
  ]


def _patch_fanout(monkeypatch):
  from hugr.commands import doctor as doc_mod
  monkeypatch.setattr(doc_mod, "_FANOUT", [])


def test_doctor_fix_without_yes_reports_pending(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "data"))
  _patch_fanout(monkeypatch)
  with patch("subprocess.run", side_effect=FileNotFoundError):
    result = CliRunner().invoke(cli, ["doctor", "--fix", "--json"])

  assert result.exit_code == 0
  doc = json.loads(result.output)
  fix = doc["fixes_applied"][0]
  assert fix["id"] == "missing_hugr_config"
  assert fix["applied"] is False
  assert not (tmp_path / "hugr" / "config.toml").exists()


def test_doctor_fix_yes_runs_quick_bootstrap(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "data"))
  _patch_fanout(monkeypatch)

  from hugr.commands import init as init_mod
  monkeypatch.setattr(init_mod, "run_all_cached", lambda: _stub_probes())
  import shutil
  monkeypatch.setattr(shutil, "which", lambda _name: None)

  with patch("subprocess.run", side_effect=FileNotFoundError):
    result = CliRunner().invoke(cli, ["doctor", "--fix", "--yes", "--json"])

  assert result.exit_code == 0, result.output
  doc = json.loads(result.output)
  fix = doc["fixes_applied"][0]
  assert fix["applied"] is True

  master = tmp_path / "hugr" / "config.toml"
  yaams_cfg = tmp_path / "yaams" / "config.yaml"
  assert master.is_file()
  assert yaams_cfg.is_file()
  parsed = read_master(master)
  assert parsed["yaams_config"] == str(yaams_cfg)


def _component(tool: str, installed: bool, findings: list[dict]) -> dict:
  return {
    "tool": tool,
    "version": "0.0.0",
    "installed": installed,
    "findings": findings,
    "exit_code": 0,
  }


def test_doctor_fix_offers_owa_piggy_no_profiles_pointer(monkeypatch, tmp_path: Path):
  """owa-piggy with no profiles is state B; --fix surfaces it as a
  pending fix pointing at the interactive setup form. Even with
  --yes we don't auto-run setup since it needs alias + email."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "data"))

  from hugr.commands import doctor as doc_mod
  monkeypatch.setattr(doc_mod, "_FANOUT", [])
  monkeypatch.setattr(
    doc_mod,
    "_aggregate",
    lambda *, fix=False, yes=False: {
      "tool": "hugr",
      "version": "0.0.0",
      "components": [
        _component("owa-piggy", True, [
          {"id": "no_profiles", "severity": "warning", "message": "no profiles"},
        ]),
      ],
      "m365_profiles": [],
      "_exit_code": 1,
      **({"fixes_applied": doc_mod._apply_fixes(
        yes=yes,
        components=[_component("owa-piggy", True, [
          {"id": "no_profiles", "severity": "warning", "message": "no profiles"},
        ])],
      )} if fix else {}),
    },
  )

  result = CliRunner().invoke(cli, ["doctor", "--fix", "--yes", "--json"])
  assert result.exit_code in (0, 1), result.output
  doc = json.loads(result.output)
  ids = [f["id"] for f in doc.get("fixes_applied", [])]
  assert "owa_piggy_no_profiles" in ids
  fix = next(f for f in doc["fixes_applied"] if f["id"] == "owa_piggy_no_profiles")
  assert fix["applied"] is False
  assert "owa-piggy setup" in fix["hint"]


def test_doctor_fix_offers_yaams_config_missing_when_finding_present(monkeypatch, tmp_path: Path):
  """yaams reporting config_missing is state B; --fix --yes runs the
  quick bootstrap which writes the canonical yaams config."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "data"))

  # The master-config-missing fix triggers first (state: no master).
  # Then yaams_config_missing should also appear in the list.
  from hugr.commands import doctor as doc_mod
  monkeypatch.setattr(doc_mod, "_FANOUT", [])
  monkeypatch.setattr(
    doc_mod,
    "_aggregate",
    lambda *, fix=False, yes=False: {
      "tool": "hugr",
      "version": "0.0.0",
      "components": [
        _component("yaams", True, [
          {"id": "config_missing", "severity": "error", "message": "missing"},
        ]),
      ],
      "m365_profiles": [],
      "_exit_code": 1,
      **({"fixes_applied": doc_mod._apply_fixes(
        yes=yes,
        components=[_component("yaams", True, [
          {"id": "config_missing", "severity": "error", "message": "missing"},
        ])],
      )} if fix else {}),
    },
  )

  from hugr.commands import init as init_mod
  monkeypatch.setattr(init_mod, "run_all_cached", lambda: [])
  import shutil
  monkeypatch.setattr(shutil, "which", lambda _name: None)

  with patch("subprocess.run", side_effect=FileNotFoundError):
    result = CliRunner().invoke(cli, ["doctor", "--fix", "--yes", "--json"])
  doc = json.loads(result.output)
  ids = [f["id"] for f in doc.get("fixes_applied", [])]
  assert "yaams_config_missing" in ids

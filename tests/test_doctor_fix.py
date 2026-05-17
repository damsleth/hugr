from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from mnem.cli import cli
from mnem.config import read_master
from mnem.sources import ProbeResult


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
  from mnem.commands import doctor as doc_mod
  monkeypatch.setattr(doc_mod, "_FANOUT", [])


def test_doctor_fix_without_yes_reports_pending(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("MNEM_HOME", str(tmp_path / "data"))
  _patch_fanout(monkeypatch)
  with patch("subprocess.run", side_effect=FileNotFoundError):
    result = CliRunner().invoke(cli, ["doctor", "--fix", "--json"])

  assert result.exit_code == 0
  doc = json.loads(result.output)
  fix = doc["fixes_applied"][0]
  assert fix["id"] == "missing_mnem_config"
  assert fix["applied"] is False
  assert not (tmp_path / "mnem" / "config.yaml").exists()


def test_doctor_fix_yes_runs_quick_bootstrap(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("MNEM_HOME", str(tmp_path / "data"))
  _patch_fanout(monkeypatch)

  from mnem.commands import init as init_mod
  monkeypatch.setattr(init_mod, "run_all_cached", lambda: _stub_probes())
  import shutil
  monkeypatch.setattr(shutil, "which", lambda _name: None)

  with patch("subprocess.run", side_effect=FileNotFoundError):
    result = CliRunner().invoke(cli, ["doctor", "--fix", "--yes", "--json"])

  assert result.exit_code == 0, result.output
  doc = json.loads(result.output)
  fix = doc["fixes_applied"][0]
  assert fix["applied"] is True

  master = tmp_path / "mnem" / "config.yaml"
  yaams_cfg = tmp_path / "yaams" / "config.yaml"
  assert master.is_file()
  assert yaams_cfg.is_file()
  parsed = read_master(master)
  assert parsed["yaams_config"] == str(yaams_cfg)

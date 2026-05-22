"""State-A (binary missing) prompt and brew-install handling.

When a component's binary isn't on PATH, init prompts Y/n/skip:
- Y  -> shell out to `brew install damsleth/tap/<formula>`
- n  -> print install command, mark deferred, continue
- skip -> mark deferred silently, continue

Brew failure aborts the whole wizard (no partial master config).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from hugr.cli import cli
from hugr.commands import init as init_mod
from hugr.commands.init import BrewInstallFailed, _prompt_install
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


def test_prompt_install_returns_true_when_binary_present(monkeypatch):
  monkeypatch.setattr("shutil.which", lambda _n: "/usr/local/bin/yaams")
  assert _prompt_install("yaams", "yaams") is True


def test_prompt_install_runs_brew_on_yes(monkeypatch):
  """Y answer shells out to brew install, then re-probes."""
  states = iter([None, "/usr/local/bin/yaams"])
  monkeypatch.setattr("shutil.which", lambda _n: next(states))
  recorded: list[list[str]] = []

  def fake_run(argv, **_kw):
    recorded.append(argv)
    return subprocess.CompletedProcess(argv, 0)

  monkeypatch.setattr(subprocess, "run", fake_run)
  monkeypatch.setattr("click.prompt", lambda *_a, **_kw: "y")
  assert _prompt_install("yaams", "yaams") is True
  assert recorded == [["brew", "install", "damsleth/tap/yaams"]]


def test_prompt_install_returns_false_on_no(monkeypatch):
  monkeypatch.setattr("shutil.which", lambda _n: None)
  monkeypatch.setattr("click.prompt", lambda *_a, **_kw: "n")
  init_mod._reset_deferred()
  assert _prompt_install("yaams", "yaams") is False
  assert any("yaams" in d for d in init_mod._DEFERRED)


def test_prompt_install_returns_false_on_skip(monkeypatch):
  monkeypatch.setattr("shutil.which", lambda _n: None)
  monkeypatch.setattr("click.prompt", lambda *_a, **_kw: "skip")
  init_mod._reset_deferred()
  assert _prompt_install("yaams", "yaams") is False
  assert any("yaams" in d for d in init_mod._DEFERRED)


def test_prompt_install_raises_on_brew_failure(monkeypatch):
  """brew exit nonzero -> BrewInstallFailed, which the caller turns
  into a clean wizard abort (no partial master config written)."""
  monkeypatch.setattr("shutil.which", lambda _n: None)
  monkeypatch.setattr("click.prompt", lambda *_a, **_kw: "y")
  monkeypatch.setattr(
    subprocess,
    "run",
    lambda *_a, **_kw: subprocess.CompletedProcess([], 1),
  )
  with pytest.raises(BrewInstallFailed) as exc:
    _prompt_install("yaams", "yaams")
  assert exc.value.formula == "yaams"
  assert exc.value.returncode == 1


def test_prompt_install_raises_when_brew_missing(monkeypatch):
  """If `brew` itself isn't installed, that's a brew failure too."""
  monkeypatch.setattr("shutil.which", lambda _n: None)
  monkeypatch.setattr("click.prompt", lambda *_a, **_kw: "y")

  def fake_run(*_a, **_kw):
    raise FileNotFoundError("brew not found")

  monkeypatch.setattr(subprocess, "run", fake_run)
  with pytest.raises(BrewInstallFailed):
    _prompt_install("yaams", "yaams")


def test_init_aborts_when_brew_install_fails(monkeypatch, tmp_path: Path):
  """End-to-end: missing yaams + brew failure -> init exits 5 and
  does NOT write a master config."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "data"))
  monkeypatch.setattr(init_mod, "run_all", _stub_probes)
  monkeypatch.setattr(init_mod, "_which_or_warn", lambda _name: None)
  monkeypatch.setattr("shutil.which", lambda _n: None)
  monkeypatch.setattr(
    subprocess,
    "run",
    lambda *_a, **_kw: subprocess.CompletedProcess([], 1),
  )

  # continue?, install yaams? -> y (will fail)
  result = CliRunner().invoke(cli, ["init"], input="y\ny\n")
  assert result.exit_code == 5
  assert "brew install" in (result.output + (result.stderr_bytes or b"").decode())
  assert not (tmp_path / "hugr" / "config.toml").exists()


def test_init_continues_when_user_skips_install(monkeypatch, tmp_path: Path):
  """n on every state-A prompt -> wizard still completes; master
  config is written with empty pointers; deferred summary printed."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "data"))
  monkeypatch.setattr(init_mod, "run_all", _stub_probes)
  monkeypatch.setattr(init_mod, "_which_or_warn", lambda _name: None)
  monkeypatch.setattr("shutil.which", lambda _n: None)

  # continue?, install yaams?(n), install ledger?(n), install owa-piggy?(n), install owa-tools?(n)
  result = CliRunner().invoke(cli, ["init"], input="y\nn\nn\nn\nn\n")
  assert result.exit_code == 0, result.output
  assert (tmp_path / "hugr" / "config.toml").is_file()
  assert "Deferred:" in result.output
  assert "yaams" in result.output
  assert "owa-piggy" in result.output

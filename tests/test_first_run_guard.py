"""First-run guard on bare `hugr` invocation.

When no master config exists and the user runs just `hugr`, we
prompt to launch the wizard. With master config present, bare
`hugr` falls through to the verb listing (hello).
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from hugr.cli import _first_run_should_offer_init, cli


def test_should_offer_init_when_master_missing(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setattr("sys.stdin.isatty", lambda: True)
  monkeypatch.setattr("sys.stdout.isatty", lambda: True)
  assert _first_run_should_offer_init(as_json_top=False) is True


def test_should_not_offer_when_master_present(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setattr("sys.stdin.isatty", lambda: True)
  monkeypatch.setattr("sys.stdout.isatty", lambda: True)
  master = tmp_path / "hugr" / "config.toml"
  master.parent.mkdir(parents=True)
  master.write_text("version: 1\n")
  assert _first_run_should_offer_init(as_json_top=False) is False


def test_should_not_offer_when_json_mode(monkeypatch, tmp_path: Path):
  """JSON mode is machine context - prompting is wrong."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setattr("sys.stdin.isatty", lambda: True)
  monkeypatch.setattr("sys.stdout.isatty", lambda: True)
  assert _first_run_should_offer_init(as_json_top=True) is False


def test_should_not_offer_when_not_tty(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setattr("sys.stdin.isatty", lambda: False)
  monkeypatch.setattr("sys.stdout.isatty", lambda: True)
  assert _first_run_should_offer_init(as_json_top=False) is False


def test_bare_hugr_skips_guard_in_non_tty(monkeypatch, tmp_path: Path):
  """Under CliRunner (non-tty), bare hugr falls straight to hello.
  The guard's tty check is what makes this safe in CI/pipes."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  result = CliRunner().invoke(cli, [])
  # hello output starts with "hugr v..."
  assert result.exit_code == 0
  assert "hugr" in result.output


def test_bare_hugr_prompts_when_tty_and_no_config(monkeypatch, tmp_path: Path):
  """With the guard helper stubbed True, bare hugr reaches the
  prompt. Answering n falls through to hello (no init launched).

  CliRunner replaces sys.stdin/stdout with non-tty streams, so we
  bypass the real tty check by stubbing the helper directly."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  from hugr import cli as cli_mod
  monkeypatch.setattr(cli_mod, "_first_run_should_offer_init", lambda _j: True)
  result = CliRunner().invoke(cli, [], input="n\n")
  assert result.exit_code == 0
  assert "No hugr config" in result.output
  assert "Run `hugr init` now?" in result.output

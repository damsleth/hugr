"""State-B chaining: when a binary is installed but unconfigured,
the wizard offers to chain the tool's own setup verb.

- yaams       -> writes generated config (already covered in test_init)
- ledger      -> `ledger init`
- owa-piggy   -> prompts for alias + email, runs `owa-piggy setup --profile <a> --email <e>`
- owa-tools   -> no setup needed; just confirms presence
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from hugr.cli import cli
from hugr.commands import init as init_mod
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


def test_chain_ledger_init_runs_with_correct_argv(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "data"))
  monkeypatch.setattr(init_mod, "run_all", _stub_probes)
  monkeypatch.setattr(init_mod, "_which_or_warn", lambda _name: None)
  monkeypatch.setattr("shutil.which", lambda name: f"/usr/local/bin/{name}")

  recorded: list[list[str]] = []

  def fake_run(argv, **_kw):
    recorded.append(argv)
    return subprocess.CompletedProcess(argv, 0)

  monkeypatch.setattr(subprocess, "run", fake_run)

  # continue?, generate yaams?(y), run ledger init?(y), run owa-piggy setup?(n)
  result = CliRunner().invoke(cli, ["init"], input="y\ny\ny\nn\n")
  assert result.exit_code == 0, result.output
  ledger_calls = [a for a in recorded if a[:2] == ["/usr/local/bin/ledger", "init"]]
  assert ledger_calls, f"expected `ledger init` invocation; got {recorded}"


def test_chain_owa_piggy_setup_uses_alias_and_email(monkeypatch, tmp_path: Path):
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "data"))
  monkeypatch.setattr(init_mod, "run_all", _stub_probes)
  monkeypatch.setattr(init_mod, "_which_or_warn", lambda _name: None)
  monkeypatch.setattr("shutil.which", lambda name: f"/usr/local/bin/{name}")

  recorded: list[list[str]] = []

  def fake_run(argv, **_kw):
    recorded.append(argv)
    return subprocess.CompletedProcess(argv, 0)

  monkeypatch.setattr(subprocess, "run", fake_run)

  # continue?, generate yaams?(y), run ledger init?(n),
  # run owa-piggy setup?(y), alias=work, email=carl@crayon.no
  inputs = "y\ny\nn\ny\nwork\ncarl@crayon.no\n"
  result = CliRunner().invoke(cli, ["init"], input=inputs)
  assert result.exit_code == 0, result.output

  owa_calls = [
    a for a in recorded
    if len(a) >= 2 and a[0] == "/usr/local/bin/owa-piggy" and a[1] == "setup"
  ]
  assert owa_calls, f"expected owa-piggy setup invocation; got {recorded}"
  argv = owa_calls[0]
  assert "--profile" in argv and argv[argv.index("--profile") + 1] == "work"
  assert "--email" in argv and argv[argv.index("--email") + 1] == "carl@crayon.no"


def test_chain_owa_piggy_skipped_when_alias_or_email_blank(monkeypatch, tmp_path: Path):
  """Empty alias or email -> skip setup, defer it, do not crash."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "data"))
  monkeypatch.setattr(init_mod, "run_all", _stub_probes)
  monkeypatch.setattr(init_mod, "_which_or_warn", lambda _name: None)
  monkeypatch.setattr("shutil.which", lambda name: f"/usr/local/bin/{name}")

  recorded: list[list[str]] = []
  monkeypatch.setattr(
    subprocess,
    "run",
    lambda argv, **_kw: (recorded.append(argv), subprocess.CompletedProcess(argv, 0))[1],
  )

  # continue?, generate yaams?(y), run ledger init?(n),
  # run owa-piggy setup?(y), alias=<blank>, email=<blank>
  result = CliRunner().invoke(cli, ["init"], input="y\ny\nn\ny\n\n\n")
  assert result.exit_code == 0, result.output

  owa_setup_calls = [
    a for a in recorded
    if len(a) >= 2 and "owa-piggy" in a[0] and a[1] == "setup"
  ]
  assert not owa_setup_calls
  assert "required" in result.output.lower()


def test_owa_tools_presence_check_no_state_b_prompt(monkeypatch, tmp_path: Path):
  """owa-tools has no config of its own. State C is just `+ on PATH`
  - no Y/n prompts to consume."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "data"))
  monkeypatch.setattr(init_mod, "run_all", _stub_probes)
  monkeypatch.setattr(init_mod, "_which_or_warn", lambda _name: None)
  monkeypatch.setattr("shutil.which", lambda name: f"/usr/local/bin/{name}")

  # continue?, generate yaams?(y), ledger init?(n), owa-piggy setup?(n)
  # If owa-tools tried to prompt, it would consume from stdin and the
  # test would either crash or write to a wrong path. Confirm it
  # finishes cleanly with the four expected inputs.
  result = CliRunner().invoke(cli, ["init"], input="y\ny\nn\nn\n")
  assert result.exit_code == 0, result.output
  assert "owa-tools on PATH" in result.output

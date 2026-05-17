"""F5 - existing-config adoption invariant.

Rule: if a tool's config already exists at any of the canonical search
paths, ``mnem init`` MUST NOT mutate it. The master config records the
path it adopted; that is the only mnem write.

One test per tool (yaams / ledger / owa-piggy). Each fixture writes a
config file with a distinctive custom property, runs ``mnem init``,
and asserts:
  1. The file is unchanged byte-for-byte.
  2. The master config records the adopted path.
"""
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from mnem.cli import cli
from mnem.config import read_master
from mnem.sources import ProbeResult


def _stub_probes() -> list[ProbeResult]:
  return [
    ProbeResult("imessage", True, "chat.db found", extras={"chat_db_path": "/tmp/chat.db"}),
    ProbeResult("email", False, "no Apple Mail", hint="run Mail.app once"),
    ProbeResult("signal", False, "Signal not installed"),
    ProbeResult("github", True, "gh authenticated"),
    ProbeResult("owa_piggy", True, "2 profiles", extras={"profiles": ["work", "personal"]}),
    ProbeResult("notes", True, "vault at /tmp/vault", extras={"vault_path": "/tmp/vault"}),
    ProbeResult("tier2_ledger", False, "ledger not on PATH", hint="brew install ledger"),
  ]


def test_init_does_not_mutate_existing_yaams_config(monkeypatch, tmp_path: Path):
  """Byte-for-byte invariant: existing yaams config is untouched."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("MNEM_HOME", str(tmp_path / "data"))

  # Write a yaams config with a distinctive custom comment + key.
  yaams_cfg = tmp_path / "yaams" / "config.yaml"
  yaams_cfg.parent.mkdir(parents=True)
  original_content = (
    "# user-custom-line\n"
    "db_path: ~/custom/brain/yaams/data.db\n"
    "custom_key: unique-sentinel-value-yaams\n"
  )
  yaams_cfg.write_bytes(original_content.encode("utf-8"))
  original_bytes = yaams_cfg.read_bytes()

  from mnem.commands import init as init_mod
  monkeypatch.setattr(init_mod, "run_all", _stub_probes)
  monkeypatch.setattr(init_mod, "_which_or_warn", lambda _name: None)

  # One prompt: "Continue?" -> y (yaams config exists so no second prompt)
  result = CliRunner().invoke(cli, ["init"], input="y\n")
  assert result.exit_code == 0, result.output

  # File must be unchanged byte-for-byte.
  assert yaams_cfg.read_bytes() == original_bytes, (
    "mnem init mutated the existing yaams config"
  )

  # Master config must record the adopted path.
  master = read_master(tmp_path / "mnem" / "config.yaml")
  assert master.get("yaams_config") == str(yaams_cfg)


def test_init_does_not_mutate_existing_ledger_config(monkeypatch, tmp_path: Path):
  """Byte-for-byte invariant: existing ledger config is untouched."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("MNEM_HOME", str(tmp_path / "data"))

  ledger_cfg = tmp_path / "cognitive-ledger" / "config.yaml"
  ledger_cfg.parent.mkdir(parents=True)
  original_content = (
    "# user-custom-line\n"
    "ledger_root: ~/custom/notes/ledger\n"
    "custom_key: unique-sentinel-value-ledger\n"
  )
  ledger_cfg.write_bytes(original_content.encode("utf-8"))
  original_bytes = ledger_cfg.read_bytes()

  from mnem.commands import init as init_mod
  monkeypatch.setattr(init_mod, "run_all", _stub_probes)
  monkeypatch.setattr(init_mod, "_which_or_warn", lambda _name: None)

  result = CliRunner().invoke(cli, ["init"], input="y\ny\n")
  assert result.exit_code == 0, result.output

  assert ledger_cfg.read_bytes() == original_bytes, (
    "mnem init mutated the existing ledger config"
  )

  master = read_master(tmp_path / "mnem" / "config.yaml")
  assert master.get("ledger_config") == str(ledger_cfg)


def test_init_does_not_mutate_existing_owa_piggy_config(monkeypatch, tmp_path: Path):
  """Byte-for-byte invariant: existing owa-piggy config is untouched."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("MNEM_HOME", str(tmp_path / "data"))

  owa_cfg = tmp_path / "owa-piggy" / "profiles.conf"
  owa_cfg.parent.mkdir(parents=True)
  original_content = (
    "# user-custom-line\n"
    'OWA_DEFAULT_PROFILE="personal"\n'
    "# unique-sentinel-value-owa\n"
  )
  owa_cfg.write_bytes(original_content.encode("utf-8"))
  original_bytes = owa_cfg.read_bytes()

  from mnem.commands import init as init_mod
  monkeypatch.setattr(init_mod, "run_all", _stub_probes)
  monkeypatch.setattr(init_mod, "_which_or_warn", lambda _name: None)

  result = CliRunner().invoke(cli, ["init"], input="y\ny\n")
  assert result.exit_code == 0, result.output

  assert owa_cfg.read_bytes() == original_bytes, (
    "mnem init mutated the existing owa-piggy config"
  )

  master = read_master(tmp_path / "mnem" / "config.yaml")
  assert master.get("owa_piggy_config") == str(owa_cfg)


def test_init_does_not_mutate_any_config_when_all_three_exist(monkeypatch, tmp_path: Path):
  """When all three tool configs exist, none of them is touched."""
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
  monkeypatch.setenv("MNEM_HOME", str(tmp_path / "data"))

  configs: dict[str, tuple[Path, bytes]] = {}

  for tool, filename, sentinel in [
    ("yaams", "yaams/config.yaml", "sentinel-yaams"),
    ("ledger", "cognitive-ledger/config.yaml", "sentinel-ledger"),
    ("owa", "owa-piggy/profiles.conf", "sentinel-owa"),
  ]:
    cfg = tmp_path / filename
    cfg.parent.mkdir(parents=True, exist_ok=True)
    content = f"# user-custom-line\ncustom_key: {sentinel}\n".encode("utf-8")
    cfg.write_bytes(content)
    configs[tool] = (cfg, content)

  from mnem.commands import init as init_mod
  monkeypatch.setattr(init_mod, "run_all", _stub_probes)
  monkeypatch.setattr(init_mod, "_which_or_warn", lambda _name: None)

  result = CliRunner().invoke(cli, ["init"], input="y\n")
  assert result.exit_code == 0, result.output

  for tool, (path, original) in configs.items():
    assert path.read_bytes() == original, (
      f"mnem init mutated the existing {tool} config"
    )

"""`hugr list` enumerates all suite binaries (hugr + packages)."""
from __future__ import annotations

import json

from click.testing import CliRunner

from hugr import __version__
from hugr._minimums import PACKAGES
from hugr.cli import cli


def _all_binaries() -> list[str]:
  return ["hugr"] + [b for info in PACKAGES.values() for b in info["binaries"]]


def test_list_json_shape(monkeypatch):
  """JSON envelope: {tool, version, tools: [...]} with one row per
  binary (hugr first, then PACKAGES in declared order)."""
  monkeypatch.setattr("shutil.which", lambda name: f"/usr/local/bin/{name}")
  from hugr.commands import list as list_mod
  monkeypatch.setattr(list_mod, "_version_of", lambda _b: "9.9.9")

  result = CliRunner().invoke(cli, ["list", "--json"])
  assert result.exit_code == 0, result.output
  doc = json.loads(result.output)
  assert doc["tool"] == "hugr"
  assert doc["version"] == __version__

  tools = doc["tools"]
  names = [t["tool"] for t in tools]
  assert names == _all_binaries()

  # hugr row reports its own __version__, not the probed value.
  hugr_row = tools[0]
  assert hugr_row["tool"] == "hugr"
  assert hugr_row["version"] == __version__
  assert hugr_row["installed"] is True


def test_list_marks_missing_binary_not_installed(monkeypatch):
  """When shutil.which returns None, the row is installed=False with
  version=None - no spurious probe call."""
  monkeypatch.setattr("shutil.which", lambda name: None if name == "yaams" else f"/usr/local/bin/{name}")
  from hugr.commands import list as list_mod
  probed: list[str] = []

  def fake_version(binary: str):
    probed.append(binary)
    return "1.0.0"

  monkeypatch.setattr(list_mod, "_version_of", fake_version)

  result = CliRunner().invoke(cli, ["list", "--json"])
  assert result.exit_code == 0
  doc = json.loads(result.output)
  yaams_row = next(t for t in doc["tools"] if t["tool"] == "yaams")
  assert yaams_row["installed"] is False
  assert yaams_row["path"] is None
  assert yaams_row["version"] is None
  assert "yaams" not in probed


def test_list_pretty_groups_by_package(monkeypatch):
  """Default (non-JSON) rendering groups rows by package label and
  marks not-installed binaries explicitly."""
  monkeypatch.setattr(
    "shutil.which",
    lambda name: None if name == "owa-piggy" else f"/usr/local/bin/{name}",
  )
  from hugr.commands import list as list_mod
  monkeypatch.setattr(list_mod, "_version_of", lambda _b: "1.2.3")

  result = CliRunner().invoke(cli, ["list"])
  assert result.exit_code == 0, result.output
  out = result.output
  # Package headers and at least one entry under each.
  for pkg in ("hugr", "yaams", "cognitive-ledger", "owa-piggy", "owa-tools"):
    assert f"{pkg}:" in out, f"missing package header {pkg!r}"
  assert "(not installed)" in out
  assert "1.2.3" in out


def test_list_in_hello_verb_listing():
  """Hello/help output advertises the new `list` verb so users can
  discover it without already knowing the name."""
  result = CliRunner().invoke(cli, ["hello"])
  assert result.exit_code == 0
  assert "list" in result.output

"""Master config for mnem: ``$XDG_CONFIG_HOME/mnem/config.yaml``.

Schema (flat, two conceptual sections):

  # mnem-specific
  version: 1
  data_root: ~/.local/share/mnem

  # pointers to per-tool configs
  yaams_config: ~/.config/yaams/config.yaml
  ledger_config: ~/.config/cognitive-ledger/config.yaml
  owa_piggy_config: ~/.config/owa-piggy/profiles.conf

  # optional M365 hint (display-only; mnem never auto-selects a profile)
  # default_owa_profile: swon

mnem doesn't own those tool configs - it just records where they
live. ``yaams`` honors ``YAAMS_CONFIG``; mnem injects it for
yaams-backed routes from this file. ``ledger`` and ``owa-piggy``
read their canonical XDG locations directly and don't accept a
config redirect, so their paths here are informational (used by
``mnem doctor`` and to point the user at the right file to edit).

Parsing is intentionally hand-rolled (no PyYAML dependency in mnem
itself). The shape is flat ``key: value`` scalars, optional quotes,
optional trailing comments.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence


def config_dir() -> Path:
  xdg = os.environ.get("XDG_CONFIG_HOME")
  base = Path(xdg) if xdg else Path.home() / ".config"
  return base / "mnem"


def master_config_path() -> Path:
  return config_dir() / "config.yaml"


def data_root_default() -> Path:
  mnem_home = os.environ.get("MNEM_HOME")
  return Path(mnem_home) if mnem_home else Path.home() / ".local" / "share" / "mnem"


def canonical_yaams_config() -> Path:
  xdg = os.environ.get("XDG_CONFIG_HOME")
  base = Path(xdg) if xdg else Path.home() / ".config"
  return base / "yaams" / "config.yaml"


def canonical_ledger_config() -> Path:
  xdg = os.environ.get("XDG_CONFIG_HOME")
  base = Path(xdg) if xdg else Path.home() / ".config"
  return base / "cognitive-ledger" / "config.yaml"


def canonical_owa_piggy_config() -> Path:
  xdg = os.environ.get("XDG_CONFIG_HOME")
  base = Path(xdg) if xdg else Path.home() / ".config"
  return base / "owa-piggy" / "profiles.conf"


def read_master(path: Path | None = None) -> dict[str, str]:
  """Parse the master config into a flat str->str dict.

  Unknown keys are preserved so future fields don't trip the parser.
  Returns ``{}`` if the file is missing.
  """
  cfg = path or master_config_path()
  if not cfg.is_file():
    return {}
  out: dict[str, str] = {}
  for raw in cfg.read_text(encoding="utf-8").splitlines():
    line = raw.split("#", 1)[0].rstrip()
    if not line or line.startswith(" ") or line.startswith("\t"):
      continue
    if ":" not in line:
      continue
    key, _, value = line.partition(":")
    key = key.strip()
    value = value.strip().strip("'").strip('"')
    if not key:
      continue
    out[key] = value
  return out


def resolved_yaams_config() -> Path | None:
  """Path to the yaams config mnem should hand to yaams.

  Order:
  1. ``yaams_config:`` from the master config (if it exists and the
     file at that path exists).
  2. Canonical ``$XDG_CONFIG_HOME/yaams/config.yaml`` (if it exists).
  3. ``None`` if neither is resolvable.

  The first-run guard treats ``None`` as "user needs to run
  ``mnem init``".
  """
  master = read_master()
  pointer = master.get("yaams_config")
  if pointer:
    candidate = Path(pointer).expanduser()
    if candidate.is_file():
      return candidate
  canonical = canonical_yaams_config()
  if canonical.is_file():
    return canonical
  return None


def resolved_ledger_config() -> Path | None:
  master = read_master()
  pointer = master.get("ledger_config")
  if pointer:
    candidate = Path(pointer).expanduser()
    if candidate.is_file():
      return candidate
  canonical = canonical_ledger_config()
  return canonical if canonical.is_file() else None


def resolved_owa_piggy_config() -> Path | None:
  master = read_master()
  pointer = master.get("owa_piggy_config")
  if pointer:
    candidate = Path(pointer).expanduser()
    if candidate.is_file():
      return candidate
  canonical = canonical_owa_piggy_config()
  return canonical if canonical.is_file() else None


def resolved_default_owa_profile() -> str | None:
  """Return the optional ``default_owa_profile`` from the master config.

  This is informational only - mnem never auto-selects a profile. The
  value is surfaced in ``mnem doctor`` and can be set by the user
  directly in the master config file.  Returns ``None`` if unset.
  """
  return read_master().get("default_owa_profile") or None


def explicit_config_in_args(args: Sequence[str]) -> bool:
  """True iff the user passed --config / --config=... themselves."""
  return any(
    a == "--config" or a.startswith("--config=") for a in args
  )


def yaams_config_env_for_args(args: Sequence[str]) -> dict[str, str]:
  """Return a YAAMS_CONFIG env overlay for yaams-backed routes.

  This is shared by the CLI passthrough and the in-process API layer so
  mnem surfaces resolve yaams config the same way. It never overrides a
  user-set ``YAAMS_CONFIG`` or an explicit child ``--config`` argument.
  """
  from mnem.router import lookup

  full = tuple(args)
  resolved = lookup(list(full))
  if resolved is None:
    return {}
  mapping, _ = resolved
  if mapping.binary != "yaams":
    return {}
  if os.environ.get("YAAMS_CONFIG"):
    return {}
  if explicit_config_in_args(full):
    return {}
  cfg = resolved_yaams_config()
  if cfg is None:
    return {}
  return {"YAAMS_CONFIG": str(cfg)}


def render_master(
  *,
  version: str,
  data_root: Path,
  yaams_config: Path | None,
  ledger_config: Path | None,
  owa_piggy_config: Path | None,
  default_owa_profile: str | None = None,
) -> str:
  """Hand-roll the master config file body. Stays valid YAML."""
  def _line(key: str, value: Path | None, *, note: str | None = None) -> str:
    if value is None:
      hint = f"  # {note}" if note else "  # not detected"
      return f"# {key}:{hint}"
    return f"{key}: {value}"

  profile_line = (
    f"default_owa_profile: {default_owa_profile}"
    if default_owa_profile
    else "# default_owa_profile:  # optional: set to your preferred owa-piggy profile alias"
  )

  return f"""# mnem master config (generated by `mnem init` v{version}).
# Edit freely. Re-run `mnem init` any time to refresh detection;
# existing pointers are preserved unless you opt in to overwriting.

version: 1

# --- mnem-specific ---------------------------------------------------
data_root: {data_root}

# --- pointers to per-tool configs ------------------------------------
# yaams honors YAAMS_CONFIG, so mnem injects this path as an env var
# for yaams-backed routes (query, ingest, promote). ledger and
# owa-piggy read their canonical XDG locations directly and don't
# accept a config redirect; the paths below are informational - used
# by `mnem doctor` and to point you at the file to edit.

{_line("yaams_config", yaams_config, note="run `mnem init` once a yaams config exists")}
{_line("ledger_config", ledger_config, note="run `ledger init` to create one")}
{_line("owa_piggy_config", owa_piggy_config, note="run `owa-piggy setup` to create one")}

# --- M365 / owa-piggy -----------------------------------------------
# Set default_owa_profile to your preferred profile alias so `mnem doctor`
# can flag it. mnem never auto-selects a profile; this is display-only.
{profile_line}
"""

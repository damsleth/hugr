"""Master config for hugr: ``$XDG_CONFIG_HOME/hugr/config.yaml``.

Schema (flat YAML at root):

  version: 1
  data_root: ~/.local/share/hugr
  yaams_config: ~/.config/yaams/config.yaml
  ledger_config: ~/.config/cognitive-ledger/config.yaml
  owa_piggy_config: ~/.config/owa-piggy/profiles.conf
  # default_owa_profile: swon  # optional, display-only

hugr doesn't own the per-tool configs - it just records where they
live. ``yaams`` honors ``YAAMS_CONFIG``; hugr injects it for
yaams-backed routes from this file. ``ledger`` and ``owa-piggy``
read their canonical XDG locations directly and don't accept a
config redirect, so their paths here are informational (used by
``hugr doctor`` and to point the user at the right file to edit).

YAML matches the rest of the hugr suite (yaams, cognitive-ledger).
Parsing uses PyYAML's ``safe_load``. The shape is flat top-level
key/value scalars.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence


def config_dir() -> Path:
  xdg = os.environ.get("XDG_CONFIG_HOME")
  base = Path(xdg) if xdg else Path.home() / ".config"
  return base / "hugr"


def master_config_path() -> Path:
  return config_dir() / "config.yaml"


def data_root_default() -> Path:
  hugr_home = os.environ.get("HUGR_HOME")
  return Path(hugr_home) if hugr_home else Path.home() / ".local" / "share" / "hugr"


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
  """Parse the master config (flat YAML) into a str->str dict.

  Unknown top-level keys are preserved so future fields don't trip the
  parser. Non-scalar values (mappings, lists) are ignored. Returns
  ``{}`` if the file is missing or malformed.
  """
  cfg = path or master_config_path()
  if not cfg.is_file():
    return {}
  try:
    import yaml  # type: ignore[import-not-found]
  except ModuleNotFoundError:
    return {}
  try:
    data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
  except yaml.YAMLError:
    return {}
  if not isinstance(data, dict):
    return {}
  out: dict[str, str] = {}
  for key, value in data.items():
    if isinstance(value, bool):
      out[str(key)] = "true" if value else "false"
    elif isinstance(value, (str, int, float)):
      out[str(key)] = str(value)
  return out


def resolved_yaams_config() -> Path | None:
  """Path to the yaams config hugr should hand to yaams.

  Order:
  1. ``yaams_config`` from the master config (if it exists and the
     file at that path exists).
  2. Canonical ``$XDG_CONFIG_HOME/yaams/config.yaml`` (if it exists).
  3. ``None`` if neither is resolvable.

  The first-run guard treats ``None`` as "user needs to run
  ``hugr init``".
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

  Display-only - hugr never auto-selects a profile. Surfaced in
  ``hugr doctor``. Returns ``None`` if unset.
  """
  return read_master().get("default_owa_profile") or None


def explicit_config_in_args(args: Sequence[str]) -> bool:
  """True iff the user passed --config / --config=... themselves."""
  return any(
    a == "--config" or a.startswith("--config=") for a in args
  )


def yaams_config_env_for_args(args: Sequence[str]) -> dict[str, str]:
  """Return a YAAMS_CONFIG env overlay for yaams-backed routes.

  Shared by the CLI passthrough and the in-process API layer so hugr
  surfaces resolve yaams config the same way. Never overrides a
  user-set ``YAAMS_CONFIG`` or an explicit child ``--config`` argument.
  """
  from hugr.router import lookup

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
  """Hand-roll the master config file body as YAML."""
  def _line(key: str, value: Path | None, *, note: str | None = None) -> str:
    if value is None:
      hint = f"  # {note}" if note else "  # not detected"
      return f"# {key}:{hint}"
    return f"{key}: {value}"

  profile_line = (
    f"default_owa_profile: {default_owa_profile}"
    if default_owa_profile
    else "# default_owa_profile:  # optional: your preferred owa-piggy profile alias"
  )

  return f"""# hugr master config (generated by `hugr init` v{version}).
# Edit freely. Re-run `hugr init` any time to refresh detection;
# existing pointers are preserved unless you opt in to overwriting.

version: 1

# --- hugr-specific ---------------------------------------------------
data_root: {data_root}

# --- pointers to per-tool configs ------------------------------------
# yaams honors YAAMS_CONFIG, so hugr injects this path as an env var
# for yaams-backed routes (query, ingest, promote). ledger and
# owa-piggy read their canonical XDG locations directly and don't
# accept a config redirect; the paths below are informational - used
# by `hugr doctor` and to point you at the file to edit.

{_line("yaams_config", yaams_config, note="run `hugr init` once a yaams config exists")}
{_line("ledger_config", ledger_config, note="run `ledger init` to create one")}
{_line("owa_piggy_config", owa_piggy_config, note="run `owa-piggy setup` to create one")}

# --- M365 / owa-piggy -----------------------------------------------
# Set default_owa_profile to your preferred profile alias so `hugr doctor`
# can flag it. hugr never auto-selects a profile; this is display-only.
{profile_line}
"""

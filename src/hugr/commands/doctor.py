"""``hugr doctor`` - aggregate health check across the suite.

Output class: data. Fans out to each `<tool> --doctor --json` and
collects findings into one document.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TextIO

from hugr import __version__
from hugr.config import master_config_path, resolved_default_owa_profile
from hugr.failure import run_subprocess


# Order is the report order; hugr first, then tiers, then M365.
_FANOUT = [
  "yaams",
  "ledger",
  "sheep",
  "ledger-obsidian",
  "owa-piggy",
  "owa-cal",
  "owa-mail",
  "owa-graph",
  "owa-people",
  "owa-sched",
  "owa-drive",
  "owa",
]


def _probe(binary: str) -> dict:
  """Probe `<binary> --doctor --json` and return the parsed payload.

  On crash or non-JSON output, synthesises a stub payload that
  preserves the doctor-schema invariants (tool name, findings list).
  """
  result = run_subprocess([binary, "--doctor"], tool=binary, inject_json=True)
  if result.crashed:
    return {
      "tool": binary,
      "version": None,
      "installed": False,
      "findings": [
        {
          "id": "binary_missing",
          "severity": "error",
          "message": "binary not on PATH or crashed before emitting JSON",
          "hint": f"brew install damsleth/tap/{binary} (or check PATH)",
        }
      ],
    }
  env = result.stdout_envelope or {}
  env["installed"] = True
  # Each binary's doctor exit code influenced findings already.
  # Track the raw exit_code for the aggregator's severity rollup.
  env["exit_code"] = result.returncode
  return env


def _m365_profiles() -> list[dict]:
  """Query owa-piggy for profile names and token-expiry state.

  Returns a list of profile dicts suitable for the doctor JSON stanza.
  If owa-piggy is not installed or returns nonzero, returns an empty list
  so the caller can render a "not configured" note.

  Each dict has the shape:
    {
      "name": str,
      "token_expires_at": str | None,  # ISO-8601 or null
      "is_default": bool,              # matches master config default_owa_profile
    }
  """
  try:
    proc = subprocess.run(
      ["owa-piggy", "profiles", "list", "--json"],
      capture_output=True,
      text=True,
      timeout=10,
    )
  except (FileNotFoundError, subprocess.TimeoutExpired):
    return []

  if proc.returncode != 0 or not proc.stdout.strip():
    return []

  try:
    raw = json.loads(proc.stdout)
  except json.JSONDecodeError:
    return []

  # owa-piggy profiles list returns either a list of profile objects or a
  # wrapper dict. Normalise to a list.
  if isinstance(raw, dict):
    raw = raw.get("profiles") or raw.get("results") or []
  if not isinstance(raw, list):
    return []

  default_profile = resolved_default_owa_profile()

  profiles: list[dict] = []
  for entry in raw:
    if not isinstance(entry, dict):
      continue
    name = entry.get("name") or entry.get("alias") or entry.get("profile") or str(entry)
    expires = entry.get("token_expires_at") or entry.get("expires_at") or None
    profiles.append({
      "name": name,
      "token_expires_at": expires,
      "is_default": (name == default_profile) if default_profile else False,
    })
  return profiles


def _apply_fixes(*, yes: bool) -> list[dict]:
  fixes: list[dict] = []
  master = master_config_path()
  if not master.is_file():
    item = {
      "id": "missing_hugr_config",
      "description": f"Create {master} with `hugr init --quick`",
      "safe": True,
      "applied": False,
    }
    if yes:
      from hugr.commands.init import quick_bootstrap_doc
      result = quick_bootstrap_doc()
      item["applied"] = bool(result.get("ok"))
      item["result"] = result
    else:
      item["hint"] = "re-run with `hugr doctor --fix --yes` to apply"
    fixes.append(item)
  return fixes


def _aggregate(*, fix: bool = False, yes: bool = False) -> dict:
  components = []
  worst_exit = 0
  for binary in _FANOUT:
    payload = _probe(binary)
    components.append(payload)
    # Aggregate severity from two sources:
    # (1) the subprocess returncode (clamped to the standard set), and
    # (2) the findings list - an error-severity finding always bumps
    # exit to at least 1, even if the binary itself returned 0.
    sub_exit = int(payload.get("exit_code") or 0)
    if not payload.get("installed", False):
      # Missing binary -> user-fixable (install or PATH); not the raw
      # FileNotFoundError exit (127).
      sub_exit = 1
    severities = {f.get("severity") for f in (payload.get("findings") or [])}
    if "error" in severities:
      sub_exit = max(sub_exit, 1)
    worst_exit = max(worst_exit, sub_exit)

  m365 = _m365_profiles()
  doc = {
    "tool": "hugr",
    "version": __version__,
    "components": components,
    "m365_profiles": m365,
    "_exit_code": worst_exit,
  }
  if fix:
    doc["fixes_applied"] = _apply_fixes(yes=yes)
  return doc


def build_report(*, fix: bool = False, yes: bool = False) -> tuple[dict, int]:
  """Return (report_dict, exit_code) without writing to stdout.

  The dict is the same shape that ``run(as_json=True)`` serialises,
  minus the internal ``_exit_code`` sentinel key.  Callers that only
  want the dict can ignore the exit code; callers that drive process
  exit (the CLI, the API layer) use the int.
  """
  doc = _aggregate(fix=fix, yes=yes)
  exit_code = int(doc.pop("_exit_code", 0))
  return doc, exit_code


def run(as_json: bool, stream: TextIO | None = None, *, fix: bool = False, yes: bool = False) -> int:
  out: TextIO = stream if stream is not None else sys.stdout
  doc, exit_code = build_report(fix=fix, yes=yes)
  if as_json:
    out.write(json.dumps(doc, ensure_ascii=False) + "\n")
    out.flush()
    return exit_code

  out.write(f"hugr doctor (v{doc['version']})\n")
  for comp in doc["components"]:
    name = comp["tool"]
    if not comp.get("installed"):
      out.write(f"  {name:<18}  - not installed\n")
      continue
    findings = comp.get("findings") or []
    if not findings:
      out.write(f"  {name:<18}  ok\n")
      continue
    severities = {f["severity"] for f in findings}
    if "error" in severities:
      mark = "x"
    elif "warning" in severities:
      mark = "!"
    else:
      mark = "."
    out.write(f"  {name:<18}  {mark} {len(findings)} finding(s)\n")
    for f in findings:
      hint = f"  hint: {f['hint']}" if f.get("hint") else ""
      out.write(f"    - [{f['severity']}] {f['id']}: {f['message']}{hint}\n")

  # M365 profiles stanza - read-only, never picks a default.
  out.write("\nM365 profiles (owa-piggy):\n")
  profiles = doc.get("m365_profiles") or []
  if not profiles:
    out.write("  owa-piggy: not configured\n")
  else:
    for p in profiles:
      default_tag = " [default]" if p.get("is_default") else ""
      expires = p.get("token_expires_at") or "unknown"
      out.write(f"  {p['name']}{default_tag}  expires: {expires}\n")

  if fix:
    out.write("\nFixes:\n")
    fixes = doc.get("fixes_applied") or []
    if not fixes:
      out.write("  no applicable fixes\n")
    for item in fixes:
      mark = "+" if item.get("applied") else "."
      out.write(f"  {mark} {item['id']}: {item['description']}\n")
      if item.get("hint"):
        out.write(f"    hint: {item['hint']}\n")

  out.flush()
  return exit_code

"""``hugr list`` - enumerate all suite binaries with installed state.

Output class: data. Mirrors `owa list` (which surfaces M365 consumer
tools), scoped to the whole hugr suite: hugr itself plus every
binary in ``hugr._minimums.PACKAGES``.

Each row reports:
  - ``tool``: binary name
  - ``package``: brew package label that ships it
  - ``installed``: True iff on PATH
  - ``path``: resolved PATH location, or None
  - ``version``: from ``<tool> --doctor --json``, or None

The JSON shape is ``{"tool": "hugr", "version": "...", "tools": [...]}``
so callers can distinguish hugr's own version from the per-tool list.
"""

from __future__ import annotations

import json
import shutil
import sys
from typing import TextIO

from hugr import __version__
from hugr._minimums import PACKAGES
from hugr.failure import run_subprocess


def _version_of(binary: str) -> str | None:
  """Pull the version field from ``<binary> --doctor --json``.

  Returns None when the binary isn't on PATH, crashes, or doesn't
  emit a JSON envelope with a version. We deliberately don't try
  ``--version`` since most suite tools default it to Click's
  human-text format.
  """
  result = run_subprocess([binary, "--doctor"], tool=binary, inject_json=True)
  if result.crashed:
    return None
  env = result.stdout_envelope or {}
  return env.get("version")


def _data_doc() -> dict:
  tools: list[dict] = [
    {
      "tool": "hugr",
      "package": "hugr",
      "installed": True,
      "path": shutil.which("hugr"),
      "version": __version__,
    }
  ]
  for pkg, info in PACKAGES.items():
    for binary in info["binaries"]:
      path = shutil.which(binary)
      tools.append({
        "tool": binary,
        "package": pkg,
        "installed": path is not None,
        "path": path,
        "version": _version_of(binary) if path else None,
      })
  return {
    "tool": "hugr",
    "version": __version__,
    "tools": tools,
  }


def build_report() -> dict:
  """Return the data dict without writing to stdout.

  Shape matches ``run(as_json=True)`` so ``hugr.api.list`` (if added
  later) can reuse it without shelling out.
  """
  return _data_doc()


def run(as_json: bool, stream: TextIO | None = None) -> int:
  out: TextIO = stream if stream is not None else sys.stdout
  doc = build_report()
  if as_json:
    out.write(json.dumps(doc, ensure_ascii=False) + "\n")
    out.flush()
    return 0

  out.write(f"hugr suite v{doc['version']}\n\n")
  current_pkg: str | None = None
  for row in doc["tools"]:
    pkg = row["package"]
    if pkg != current_pkg:
      out.write(f"{pkg}:\n")
      current_pkg = pkg
    name = row["tool"]
    if not row["installed"]:
      out.write(f"  {name:<18} (not installed)\n")
      continue
    version = row.get("version") or "?"
    out.write(f"  {name:<18} {version}\n")
  out.flush()
  return 0

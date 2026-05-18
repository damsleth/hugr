"""``hugr hello`` - the one-screen elevator pitch.

Output class: data. Runs without any config; safe on a fresh
install before anything is wired up. Emits JSON on stdout under
--json, a human banner otherwise.
"""

from __future__ import annotations

import json
import sys
from typing import TextIO

from hugr import __version__
from hugr.router import verbs


# Static verbs that live in hugr itself (not the translation table).
_BUILTIN_VERBS = [
  ("hello", "hugr", "Show this elevator pitch"),
  ("version", "hugr", "Show hugr version and observed component versions"),
  ("doctor", "hugr", "Run health checks across the whole suite"),
  ("init", "hugr", "First-run wizard: detect sources and write config"),
]

_FUSED_VERBS = [
  ("recall", "hugr", "Recall across YAAMS, ledger, and live M365 buckets"),
  ("find", "hugr", "Typed search for people, events, messages, notes, or files"),
  ("inbox", "hugr", "One screen for unread mail, today's events, loops, and promotions"),
  ("remember", "hugr", "Capture a fact directly into the ledger layer"),
]


def _all_verbs() -> list[tuple[str, str, str]]:
  return _BUILTIN_VERBS + _FUSED_VERBS + verbs()


def _data_doc() -> dict:
  return {
    "tool": "hugr",
    "version": __version__,
    "tagline": "Local-first memory suite for AI agents.",
    "verbs": [
      {"verb": verb, "binary": binary, "description": desc}
      for (verb, binary, desc) in _all_verbs()
    ],
    "fused_verbs": [
      {"verb": verb, "binary": binary, "description": desc}
      for (verb, binary, desc) in _FUSED_VERBS
    ],
    "direct_tool_verbs": [
      {"verb": verb, "binary": binary, "description": desc}
      for (verb, binary, desc) in verbs()
    ],
    "next_steps": [
      "hugr doctor",
      "hugr recall \"<question>\"",
      "hugr ingest",
    ],
  }


def run(as_json: bool, stream: TextIO | None = None) -> int:
  if stream is None:
    stream = sys.stdout
  if as_json:
    stream.write(json.dumps(_data_doc(), ensure_ascii=False) + "\n")
    stream.flush()
    return 0

  doc = _data_doc()
  stream.write(f"hugr v{doc['version']} - {doc['tagline']}\n\n")
  stream.write("Verbs:\n\n")
  stream.write("Fused verbs:\n")
  fused_width = max(len(entry["verb"]) for entry in doc["fused_verbs"])
  for entry in doc["fused_verbs"]:
    verb = entry["verb"]
    desc = entry["description"]
    stream.write(f"  {verb:<{fused_width}}  {desc}\n")
  stream.write("\nDirect tool access:\n")
  direct = doc["direct_tool_verbs"]
  direct_width = max(len(entry["verb"]) for entry in direct) if direct else 0
  for entry in direct:
    verb = entry["verb"]
    desc = entry["description"]
    stream.write(f"  {verb:<{direct_width}}  {desc}\n")
  stream.write("\nNext steps:\n")
  for cmd in doc["next_steps"]:
    stream.write(f"  $ {cmd}\n")
  stream.flush()
  return 0

"""Guard test: every inject-policy row's underlying tool must accept --json.

Piece C of router-passthrough-hardening. This is a tripwire test for the
next contributor who adds a new TABLE row with json_policy="inject". If
that tool rejects --json as unknown, this test will turn red and force the
author to pick the correct policy (native or none) instead.

How it works:
  - Parametrised over every non-interactive inject-policy row in TABLE.
  - For each row, shells out to `<binary> <rewrite([])> --json --help`.
    The --help keeps it side-effect-free; we only care that --json is NOT
    flagged as unrecognized by argparse.
  - Skips cleanly if the binary is not installed (suite not available in
    the current environment).

Run skipping live calls:  pytest -m "not live_tools" tests/test_json_policy_sweep.py
Run with real binaries:   pytest -m live_tools      tests/test_json_policy_sweep.py

See .plans/router-passthrough-hardening.md §Piece C.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from hugr.router import TABLE


@pytest.mark.live_tools
@pytest.mark.parametrize(
  "verb,mapping",
  [
    (v, m)
    for v, m in TABLE.items()
    if m.json_policy == "inject" and not m.interactive
  ],
  ids=lambda x: " ".join(x) if isinstance(x, tuple) else x.binary,
)
def test_inject_policy_tools_accept_json(verb, mapping):
  """Every inject-policy tool must accept --json without raising
  'unrecognized arguments: --json'.

  If this test goes red after adding a new TABLE row, set json_policy
  to "native" or "none" for that row instead — do NOT teach the tool to
  swallow --json just to pass this test.
  """
  if shutil.which(mapping.binary) is None:
    pytest.skip(f"{mapping.binary} not installed")

  # rewrite([]) gives us the subverb head with no user args.
  rewritten = mapping.rewrite([])
  argv = [mapping.binary, *rewritten, "--json", "--help"]

  out = subprocess.run(argv, capture_output=True, text=True)
  combined = (out.stdout + out.stderr).lower()

  assert "unrecognized arguments: --json" not in combined, (
    f"{mapping.binary} {' '.join(rewritten)} rejected --json. "
    f"Set json_policy='native' or 'none' on the TABLE row for {verb!r}.\n"
    f"stderr: {out.stderr[:300]}"
  )

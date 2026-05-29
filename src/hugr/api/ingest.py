"""Fused ingest orchestrator for hugr.

Orchestrates the pipeline:
  1. ``yaams ingest``            (Tier 1 raw capture)
  2. ``yaams promote generate``  (candidate sweep, when not --dry-run)

There is intentionally NO stage 3 auto-write. ``yaams promote`` exposes
only ``generate | list | review``; ``review`` is interactive and there
is no non-interactive "commit all candidates" verb, so a headless
``hugr ingest`` cannot write promotions into the ledger. ``--promote``
reports the candidate count; ``--promote --yes`` additionally notes
that auto-write is not yet available and the candidates are queued for
``hugr promote review``. Wire a real stage 3 here once yaams grows a
non-interactive promote-commit verb (shell out to it; loose-coupling
axiom).

Returned envelope shape::

    {
        "tool": "hugr",
        "command": "ingest",
        "ok": bool,
        "exit_code": int,             # 0 ok, 1 fail, 2 partial
        "dry_run": bool,
        "ingested": int | None,       # rows ingested (parsed from yaams output)
        "candidates_generated": int | None,
        "promoted": None,             # reserved: always None until a
                                      # non-interactive promote-commit
                                      # verb exists upstream
        "promotion_pending": int | None,  # candidates queued for review
                                          # when --promote was requested
        "warnings": [...],
        "error": {...} | None,
    }

Exit codes per CONVENTIONS.md:
  0  -- full success
  1  -- yaams ingest failed (propagated from yaams exit code)
  2  -- partial success: ingest ok but sweep/promote step failed
  other -- propagated verbatim from the failing subprocess

Loose-coupling axiom: no direct Python imports from yaams or
cognitive-ledger. Every subprocess call goes through
``hugr.api._passthrough.call``.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from hugr.api._passthrough import call as _call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode(raw: bytes) -> Any:
    """Best-effort JSON decode of subprocess stdout bytes."""
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def _count_from(data: Any, *keys: str) -> int | None:
    """Pull a scalar count from an envelope dict trying several key names."""
    if not isinstance(data, dict):
        return None
    for key in keys:
        val = data.get(key)
        if isinstance(val, int):
            return val
    return None


def _warning(source: str, message: str, exit_code: int = 0) -> dict[str, Any]:
    return {"source": source, "message": message, "exit_code": exit_code}


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------

def fused_ingest(
    *,
    dry_run: bool = False,
    promote: bool = False,
    yes: bool = False,
    raw: bool = False,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    """Orchestrate the fused ingest pipeline.

    Parameters
    ----------
    dry_run:
        Preview mode -- no side effects. Reports what *would* happen.
        ``yaams ingest --dry-run`` is called if yaams supports it;
        the promote/sweep stages are skipped entirely.
    promote:
        Generate promotion candidates AND preview (or write) them.
        Without ``yes`` this is a preview-only: prints the candidate
        count and exits 0 without touching the ledger.
    yes:
        Required alongside ``promote`` to actually write candidates
        to the cognitive ledger (Tier 2). Mirrors ``hugr remember --yes``.
    raw:
        Short-circuit to a pure ``yaams ingest`` passthrough. The
        orchestrator is not invoked; the caller handles routing.
        When ``raw=True`` this function returns a minimal sentinel
        envelope -- the CLI layer is responsible for the real dispatch.
    extra_args:
        Additional argv forwarded verbatim to ``yaams ingest``.
    """
    extra_args = extra_args or []
    warnings: list[dict[str, Any]] = []

    # --raw sentinel: the CLI layer handles routing via the router table.
    # We return a marker envelope so callers have a consistent type.
    if raw:
        return {
            "tool": "hugr",
            "command": "ingest",
            "ok": True,
            "exit_code": 0,
            "dry_run": dry_run,
            "raw": True,
            "ingested": None,
            "candidates_generated": None,
            "promoted": None,
            "promotion_pending": None,
            "warnings": [],
            "error": None,
        }

    # ------------------------------------------------------------------
    # Stage 1: yaams ingest
    # ------------------------------------------------------------------
    ingest_argv = ["ingest", *extra_args]
    if dry_run:
        ingest_argv.append("--dry-run")

    rc_ingest, raw_ingest = _call(ingest_argv)
    ingest_data = _decode(raw_ingest)

    if rc_ingest != 0:
        # yaams ingest failed -- propagate its exit code; skip sweep.
        err_msg = "yaams ingest failed"
        if isinstance(ingest_data, dict) and ingest_data.get("error"):
            err_msg = str(ingest_data["error"].get("message") or err_msg)
        return {
            "tool": "hugr",
            "command": "ingest",
            "ok": False,
            "exit_code": rc_ingest,
            "dry_run": dry_run,
            "raw": False,
            "ingested": None,
            "candidates_generated": None,
            "promoted": None,
            "promotion_pending": None,
            "warnings": warnings,
            "error": {
                "code": "ingest_failed",
                "message": err_msg,
                "hint": "Run `hugr ingest --raw` to see the raw yaams output.",
            },
        }

    ingested = _count_from(ingest_data, "ingested", "count", "total")

    # In dry-run mode we stop here: no sweep, no write, no side effects.
    if dry_run:
        return {
            "tool": "hugr",
            "command": "ingest",
            "ok": True,
            "exit_code": 0,
            "dry_run": True,
            "raw": False,
            "ingested": ingested,
            "candidates_generated": None,
            "promoted": None,
            "promotion_pending": None,
            "warnings": warnings,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Stage 2: yaams promote generate (candidate sweep)
    # ------------------------------------------------------------------
    rc_gen, raw_gen = _call(["promote", "generate"])
    gen_data = _decode(raw_gen)
    candidates_generated: int | None = None
    partial = False

    if rc_gen != 0:
        # Ingest already committed to Tier 1 -- do NOT roll back.
        # Surface as a warning and exit 2 (partial success).
        err_msg = "promote generate failed"
        if isinstance(gen_data, dict) and gen_data.get("error"):
            err_msg = str(gen_data["error"].get("message") or err_msg)
        warnings.append(_warning("promote generate", err_msg, rc_gen))
        partial = True
    else:
        candidates_generated = _count_from(
            gen_data, "candidates", "generated", "count", "total"
        )

    # ------------------------------------------------------------------
    # Stage 3 (optional): promote candidates into the ledger.
    #
    # NOT IMPLEMENTED as an auto-write, by design. yaams exposes only
    # `promote generate | list | review`; `review` is interactive and
    # there is no non-interactive "commit all candidates" verb, so a
    # headless `hugr ingest` cannot write promotions into the ledger.
    # We never fake a write: `--promote` surfaces the candidate count,
    # and `--promote --yes` additionally records a note that auto-write
    # is unavailable and the candidates are queued for `hugr promote
    # review`. `promoted` therefore stays None. Wire a real write here
    # (shelling out to a future yaams verb) when one exists upstream.
    # ------------------------------------------------------------------
    promotion_pending: int | None = None

    if promote and not partial:
        promotion_pending = candidates_generated
        if yes:
            warnings.append(_warning(
                "promote",
                "non-interactive promotion is not available yet; candidates "
                "are queued — run `hugr promote review` to write them to the ledger",
            ))

    exit_code = 2 if partial else 0
    ok = not partial

    return {
        "tool": "hugr",
        "command": "ingest",
        "ok": ok,
        "exit_code": exit_code,
        "dry_run": dry_run,
        "raw": False,
        "ingested": ingested,
        "candidates_generated": candidates_generated,
        "promoted": None,
        "promotion_pending": promotion_pending,
        "warnings": warnings,
        "error": None if ok else {
            "code": "partial_success",
            "message": "; ".join(w["message"] for w in warnings),
            "hint": (
                "Ingest succeeded (Tier 1 is safe). "
                "Sweep step failed. Retry `hugr ingest` or check logs."
            ),
        },
    }

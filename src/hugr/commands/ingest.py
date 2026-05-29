"""hugr ingest command -- fused Tier-1 + Tier-2 orchestrator.

Replaces the old thin passthrough.  ``hugr ingest --raw`` is still a
pure ``yaams ingest`` bypass via the router table (escape hatch for
scripts that want byte-identical passthrough behavior).

Exit codes (per CONVENTIONS.md):
  0  all stages succeeded
  1  yaams ingest failed (exit code propagated from yaams)
  2  partial success: ingest ok, sweep/promote step failed
"""

from __future__ import annotations

import json
import sys

import click

from hugr.api.ingest import fused_ingest


@click.command(
  "ingest",
  context_settings={"ignore_unknown_options": True, "allow_extra_args": False},
)
@click.option(
  "--dry-run",
  is_flag=True,
  default=False,
  help=(
    "Preview mode: show what would be ingested and how many candidates "
    "would be generated. No data is written to either Tier 1 or Tier 2."
  ),
)
@click.option(
  "--promote",
  is_flag=True,
  default=False,
  help=(
    "After ingesting, sweep promotion candidates and preview them. "
    "Use --promote --yes to also write them to the cognitive ledger (Tier 2)."
  ),
)
@click.option(
  "--yes",
  is_flag=True,
  default=False,
  help=(
    "Confirm the Tier-2 ledger write when used with --promote. "
    "Mirrors `hugr remember --yes`."
  ),
)
@click.option(
  "--raw",
  is_flag=True,
  default=False,
  help=(
    "Bypass the orchestrator: forward all args directly to `yaams ingest` "
    "(pure passthrough, byte-identical to the old hugr ingest behavior)."
  ),
)
@click.option(
  "--json",
  "as_json",
  is_flag=True,
  default=False,
  help="Machine mode (JSON envelope on stdout).",
)
@click.option(
  "--pretty",
  is_flag=True,
  default=False,
  help="Human rendering (default when --json is not set).",
)
@click.argument("extra", nargs=-1, type=click.UNPROCESSED)
@click.pass_context
def ingest_cmd(
  ctx: click.Context,
  dry_run: bool,
  promote: bool,
  yes: bool,
  raw: bool,
  as_json: bool,
  pretty: bool,
  extra: tuple[str, ...],
) -> None:
  """Ingest all configured sources into the hugr suite.

  Runs `yaams ingest` (Tier 1) then sweeps promotion candidates
  (Tier 2 preview).  Use --promote --yes to also write to the ledger.

  Use --raw to bypass the orchestrator and get a pure yaams passthrough.
  """
  # Import here to avoid circular imports at module load time.
  from hugr.cli import _ensure_config, _split_verbose, _yaams_config_env

  hint = _ensure_config(("ingest",))
  if hint is not None:
    ctx.exit(hint)

  as_json_eff = as_json or ctx.obj.get("json", False)
  # `hugr ingest --verbose` lands the flag in `extra` (the top-level
  # group only sees it as `hugr -v ingest`). Strip it here and forward
  # the intent through the router's yaams `-v` strategy instead.
  extra, verbose_in_tail = _split_verbose(extra)
  verbose = ctx.obj.get("verbose", False) or verbose_in_tail

  if raw:
    # Bypass the orchestrator: forward straight to yaams ingest via
    # the router table passthrough.  This preserves byte-identical
    # behavior for any script that relied on the old thin passthrough.
    # --dry-run is a Click-consumed option here, so re-append it;
    # --json is added by the passthrough's inject policy. Without this
    # re-append `hugr ingest --raw --dry-run` would silently drop the
    # flag and run a real ingest.
    passthru = list(extra)
    if dry_run:
      passthru.append("--dry-run")
    full = ("ingest", *passthru)
    from hugr.commands.passthrough import run
    ctx.exit(run(
      list(full),
      verbose=verbose,
      top_level_json=as_json_eff,
      extra_env=_yaams_config_env(full) or None,
    ))

  doc = fused_ingest(
    dry_run=dry_run,
    promote=promote,
    yes=yes,
    raw=False,
    verbose=verbose,
    extra_args=list(extra),
  )

  if as_json_eff:
    click.echo(json.dumps(doc, ensure_ascii=False))
  else:
    _emit_ingest_pretty(doc, promote=promote, yes=yes)

  ctx.exit(doc.get("exit_code") or (0 if doc.get("ok") else 1))


def _emit_ingest_pretty(doc: dict, *, promote: bool, yes: bool) -> None:
  """Human-readable rendering of the ingest envelope."""
  dry = doc.get("dry_run", False)
  prefix = "[dry-run] " if dry else ""

  ingested = doc.get("ingested")
  candidates = doc.get("candidates_generated")

  if not doc.get("ok") and doc.get("error"):
    err = doc["error"]
    click.echo(
      f"x hugr ingest: {err.get('message', 'failed')}",
      err=True,
    )
    hint = err.get("hint")
    if hint:
      click.echo(f"  hint: {hint}", err=True)
    return

  # Success path
  ingest_str = f"{ingested} source(s)" if ingested is not None else "sources"
  click.echo(f"{prefix}hugr ingest: ingested {ingest_str}")

  if candidates is not None:
    if dry:
      click.echo(f"  would generate ~{candidates} promotion candidate(s)")
    else:
      click.echo(f"  {candidates} promotion candidate(s) generated")

  if promote and not dry:
    # No non-interactive promote-commit verb exists upstream (yaams
    # promote only has generate/list/review, and review is
    # interactive), so hugr never auto-writes. Point the user at the
    # interactive reviewer instead of claiming a write happened.
    click.echo(
      "  run `hugr promote review` to write candidates to the ledger (Tier 2)"
    )
    if yes:
      click.echo(
        "  note: --yes could not auto-write — non-interactive promotion "
        "is not available yet; candidates are queued for review"
      )

  warnings = doc.get("warnings") or []
  if warnings:
    click.echo("")
    for w in warnings:
      click.echo(
        f"  warning [{w.get('source', '?')}]: {w.get('message', '')}",
        err=True,
      )

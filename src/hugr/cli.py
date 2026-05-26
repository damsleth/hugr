"""hugr Click root.

Subcommands:
- hello   - one-screen elevator pitch
- version - hugr version + observed component versions
- doctor  - aggregate health check across the suite
- init    - first-run wizard (interactive; rejects --json)
- query   - passthrough to `yaams query` (with --tier aliasing)
- ingest  - passthrough to `yaams ingest`
- promote - passthrough to `yaams promote <sub>`
- ledger  - passthrough to `ledger <sub>`
- auth    - passthrough to `owa-piggy <sub>`
- mail    - passthrough to `owa-mail`
- cal - passthrough to `owa-cal`
- graph   - passthrough to `owa-graph`
- people  - passthrough to `owa-people`
- schedule - passthrough to `owa-sched`
- drive   - passthrough to `owa-drive`

Top-level flags: --version (Click default), --doctor, --json,
--verbose. The doctor flag is wired so `hugr --doctor` works for
parity with other binaries in the suite.

First-run hint middleware: subcommands that depend on the yaams DB
(query, ingest, promote review) exit 4 with a clean
``Run: hugr init`` pointer when the user has no hugr config yet.
"""

from __future__ import annotations

import os
import sys
import json
from pathlib import Path

import click

from hugr import __version__
from hugr.config import (
  explicit_config_in_args,
  master_config_path,
  yaams_config_env_for_args,
)


# --- First-run hint helpers -------------------------------------------------

def _yaams_config_path() -> Path:
  """Path to the master hugr config (the gate for the first-run guard).

  Named ``_yaams_config_path`` for historical continuity; the file it
  points at is now ``$XDG_CONFIG_HOME/hugr/config.toml``, the suite
  master config. The actual yaams config it references lives wherever
  ``yaams_config:`` inside the master points - see
  ``hugr.config.resolved_yaams_config``.
  """
  return master_config_path()


_VERBS_NEEDING_CONFIG = {
  ("recall",),
  ("find",),
  ("inbox",),
  ("remember",),
  ("query",),
  ("ingest",),
  ("promote", "review"),
  ("promote", "generate"),
}


def _explicit_config_in_args(args: tuple[str, ...]) -> bool:
  """True iff the user passed --config / --config=... themselves."""
  return explicit_config_in_args(args)


# Env vars that bypass the first-run guard, scoped to the verb that
# actually reads them. Per CONVENTIONS.md the direct-CLI / hugr parity
# invariant requires `YAAMS_CONFIG` (and friends) to resolve the same
# config in both invocation paths; hugr must defer to them when set.
# But every verb in _VERBS_NEEDING_CONFIG today is YAAMS-backed, so
# only YAAMS_CONFIG (or the suite-wide HUGR_CONFIG override) should
# count - having LEDGER_CONFIG or OWA_CONFIG set is unrelated and
# previously caused users to skip past the helpful "Run: hugr init"
# hint and crash on the missing yaams config one layer down.
_BYPASS_ENV_BY_VERB: dict[tuple[str, ...], tuple[str, ...]] = {
  ("recall",): ("YAAMS_CONFIG", "HUGR_CONFIG"),
  ("find",): ("YAAMS_CONFIG", "HUGR_CONFIG"),
  ("inbox",): ("YAAMS_CONFIG", "HUGR_CONFIG"),
  ("remember",): ("YAAMS_CONFIG", "HUGR_CONFIG"),
  ("query",): ("YAAMS_CONFIG", "HUGR_CONFIG"),
  ("ingest",): ("YAAMS_CONFIG", "HUGR_CONFIG"),
  ("promote", "review"): ("YAAMS_CONFIG", "HUGR_CONFIG"),
  ("promote", "generate"): ("YAAMS_CONFIG", "HUGR_CONFIG"),
}


def _ensure_config(verb_args: tuple[str, ...]) -> int | None:
  """Return None if it's OK to proceed; an exit code if hugr should
  bail with a first-run hint."""
  if not verb_args:
    return None
  matched_prefix: tuple[str, ...] | None = None
  for prefix in _VERBS_NEEDING_CONFIG:
    if tuple(verb_args[: len(prefix)]) == prefix:
      matched_prefix = prefix
      break
  if matched_prefix is None:
    return None
  if _explicit_config_in_args(verb_args):
    return None
  bypass_vars = _BYPASS_ENV_BY_VERB.get(matched_prefix, ())
  if any(os.environ.get(name) for name in bypass_vars):
    return None
  cfg = _yaams_config_path()
  if cfg.is_file():
    return None
  click.echo(
    f"x hugr: no hugr config at {cfg}.\n"
    f"    Fix:  hugr init",
    err=True,
  )
  return 4  # EXIT_NOT_FOUND per CONVENTIONS.md


@click.group(
  invoke_without_command=True,
  context_settings={"help_option_names": ["-h", "--help"]},
)
@click.version_option(__version__, prog_name="hugr")
@click.option(
  "--doctor",
  is_flag=True,
  default=False,
  help="Run health check across the suite and exit.",
)
@click.option(
  "--json",
  "as_json_top",
  is_flag=True,
  default=False,
  help="Machine mode (JSON output) for top-level commands.",
)
@click.option(
  "-v",
  "--verbose",
  is_flag=True,
  default=False,
  help="Verbose mode: dump captured stderr from subprocess failures.",
)
@click.pass_context
def cli(ctx: click.Context, doctor: bool, as_json_top: bool, verbose: bool) -> None:
  ctx.ensure_object(dict)
  ctx.obj["json"] = as_json_top
  ctx.obj["verbose"] = verbose
  if doctor:
    from hugr.commands.doctor import run as doctor_run
    ctx.exit(doctor_run(as_json_top))
  if ctx.invoked_subcommand is None:
    if _first_run_should_offer_init(as_json_top):
      master = master_config_path()
      click.echo(f"No hugr config found at {master}.")
      if click.confirm("Run `hugr init` now?", default=True):
        from hugr.commands.init import run as init_run
        ctx.exit(init_run(as_json=False))
    from hugr.commands.hello import run as hello_run
    ctx.exit(hello_run(as_json_top))


def _first_run_should_offer_init(as_json_top: bool) -> bool:
  """Return True iff bare `hugr` should offer to launch the wizard.

  Conditions: not in JSON mode, stdin+stdout are a TTY (so we can
  actually prompt), and the master config doesn't exist yet.
  """
  if as_json_top:
    return False
  if not sys.stdin.isatty() or not sys.stdout.isatty():
    return False
  return not master_config_path().is_file()


@cli.command("hello")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering (default).")
@click.pass_context
def hello_cmd(ctx: click.Context, as_json: bool, pretty: bool) -> None:
  # --pretty is accepted per the CONVENTIONS per-command table for
  # data-class commands. The default already is human-pretty, so the
  # flag is effectively a confirmation rather than a mode flip - but
  # --json wins if both are passed.
  del pretty  # noqa: F841 - acknowledged for contract conformance
  from hugr.commands.hello import run
  ctx.exit(run(as_json or ctx.obj.get("json", False)))


@cli.command("version")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering (default).")
@click.pass_context
def version_cmd(ctx: click.Context, as_json: bool, pretty: bool) -> None:
  del pretty
  from hugr.commands.version import run
  ctx.exit(run(as_json or ctx.obj.get("json", False)))


@cli.command("list")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering (default).")
@click.pass_context
def list_cmd(ctx: click.Context, as_json: bool, pretty: bool) -> None:
  del pretty
  from hugr.commands.list import run
  ctx.exit(run(as_json or ctx.obj.get("json", False)))


@cli.command("doctor")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering (default).")
@click.option("--fix", is_flag=True, default=False, help="Apply bounded self-healing fixes.")
@click.option("--yes", is_flag=True, default=False, help="Apply doctor fixes without per-item prompts.")
@click.pass_context
def doctor_cmd(ctx: click.Context, as_json: bool, pretty: bool, fix: bool, yes: bool) -> None:
  del pretty
  from hugr.commands.doctor import run
  ctx.exit(run(as_json or ctx.obj.get("json", False), fix=fix, yes=yes))


def _emit_json_doc(doc: dict) -> None:
  click.echo(json.dumps(doc, ensure_ascii=False))


def _emit_fused_pretty(doc: dict) -> None:
  command = doc.get("command", "hugr")
  click.echo(f"hugr {command}")
  if doc.get("query"):
    click.echo(f"query: {doc['query']}")
  if doc.get("kind"):
    click.echo(f"kind: {doc['kind']}")

  source_items = doc.get("sources") or []
  if doc.get("source"):
    source_items = [doc["source"]]
  if source_items:
    click.echo("\nsources:")
    for item in source_items:
      mark = "+" if item.get("ok") else "x"
      label = item.get("source", "?")
      cmd = item.get("command", "")
      click.echo(f"  {mark} {label} {cmd}".rstrip())

  citations = doc.get("citations") or []
  if citations:
    click.echo("\ncitations:")
    for cite in citations:
      click.echo(f"  - {cite.get('source')}: {cite.get('ref')}")

  warnings = doc.get("warnings") or []
  if warnings:
    click.echo("\nwarnings:")
    for warning in warnings:
      click.echo(f"  - {warning.get('source')}: {warning.get('message')}")


def _question_from_parts(parts: tuple[str, ...]) -> str:
  return " ".join(parts).strip()


@cli.command("recall")
@click.argument("question", nargs=-1, required=True)
@click.option("-k", "--limit", default=10, show_default=True, type=int)
@click.option("--no-live", is_flag=True, default=False, help="Skip live M365 buckets.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def recall_cmd(ctx: click.Context, question: tuple[str, ...], limit: int, no_live: bool, as_json: bool, pretty: bool) -> None:
  hint = _ensure_config(("recall",))
  if hint is not None:
    ctx.exit(hint)
  from hugr import api
  doc = api.recall(_question_from_parts(question), k=limit, live=not no_live)
  if pretty and not (as_json or ctx.obj.get("json", False)):
    _emit_fused_pretty(doc)
  else:
    _emit_json_doc(doc)
  ctx.exit(0)


@cli.command("find")
@click.argument("kind")
@click.argument("query", nargs=-1, required=True)
@click.option("-k", "--limit", default=10, show_default=True, type=int)
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def find_cmd(ctx: click.Context, kind: str, query: tuple[str, ...], limit: int, as_json: bool, pretty: bool) -> None:
  hint = _ensure_config(("find",))
  if hint is not None:
    ctx.exit(hint)
  from hugr import api
  doc = api.find(kind, _question_from_parts(query), k=limit)
  if pretty and not (as_json or ctx.obj.get("json", False)):
    _emit_fused_pretty(doc)
  else:
    _emit_json_doc(doc)
  ctx.exit(0)


@cli.command("inbox")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def inbox_cmd(ctx: click.Context, as_json: bool, pretty: bool) -> None:
  hint = _ensure_config(("inbox",))
  if hint is not None:
    ctx.exit(hint)
  from hugr import api
  doc = api.inbox()
  if pretty and not (as_json or ctx.obj.get("json", False)):
    _emit_fused_pretty(doc)
  else:
    _emit_json_doc(doc)
  ctx.exit(0)


@cli.command("remember")
@click.argument("fact", nargs=-1, required=True)
@click.option("--type", "note_type", default="fact", show_default=True)
@click.option("--link", "links", multiple=True)
@click.option("--yes", is_flag=True, default=False, help="Confirm ledger-side action when supported.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON envelope on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def remember_cmd(
  ctx: click.Context,
  fact: tuple[str, ...],
  note_type: str,
  links: tuple[str, ...],
  yes: bool,
  as_json: bool,
  pretty: bool,
) -> None:
  hint = _ensure_config(("remember",))
  if hint is not None:
    ctx.exit(hint)
  from hugr import api
  doc = api.remember(_question_from_parts(fact), note_type=note_type, links=links, yes=yes)
  if pretty and not (as_json or ctx.obj.get("json", False)):
    if doc.get("ok"):
      click.echo("remembered")
    else:
      click.echo(f"remember failed: {doc.get('error', {}).get('message', 'unknown error')}", err=True)
  else:
    _emit_json_doc(doc)
  ctx.exit(int(doc.get("exit_code") or (0 if doc.get("ok") else 1)))


@cli.group("send", invoke_without_command=False)
def send_group() -> None:
  """Send mail or create calendar events through the fused API."""


@cli.group("book", invoke_without_command=False)
def book_group() -> None:
  """Fused scheduling: propose slots with owa-sched, commit via owa-cal.

  Named ``hugr book`` to coexist with the ``hugr schedule`` passthrough
  to owa-sched. Same intent: find slots, confirm one, create the event.
  """


def _emit_action_pretty(doc: dict) -> None:
  if doc.get("ok"):
    click.echo(f"hugr {doc.get('command', 'send')}: ok")
    return
  err = doc.get("error") or {}
  click.echo(
    f"hugr {doc.get('command', 'send')} failed: {err.get('message', 'unknown error')}",
    err=True,
  )
  if err.get("hint"):
    click.echo(f"hint: {err['hint']}", err=True)


def _confirm_mutation(label: str, *, as_json: bool, yes: bool) -> int | None:
  """Block destructive mutations on a non-TTY without --yes.

  Returns None when the caller may proceed, or an exit code if the
  caller should bail. In JSON mode, never prompts - require --yes.
  """
  if yes:
    return None
  if as_json:
    click.echo(
      json.dumps({
        "tool": "hugr",
        "command": label,
        "ok": False,
        "exit_code": 1,
        "error": {
          "code": "confirmation_required",
          "message": f"hugr {label} mutates state; pass --yes for non-interactive use.",
          "hint": f"hugr {label} --yes ...",
        },
      }),
    )
    return 1
  if not sys.stdin.isatty() or not sys.stdout.isatty():
    click.echo(
      f"hugr {label} requires --yes when stdin is not a TTY.",
      err=True,
    )
    return 1
  if not click.confirm(f"Proceed with `hugr {label}`?", default=False):
    click.echo("aborted.", err=True)
    return 1
  return None


@send_group.command("mail")
@click.option("--to", "to", multiple=True, required=True, help="Recipient (repeatable).")
@click.option("--cc", "cc", multiple=True, help="CC recipient (repeatable).")
@click.option("--bcc", "bcc", multiple=True, help="BCC recipient (repeatable).")
@click.option("--subject", required=True)
@click.option("--body", required=True)
@click.option("--html", is_flag=True, default=False)
@click.option("--yes", is_flag=True, default=False, help="Skip the interactive confirmation prompt.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON envelope on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def send_mail_cmd(
  ctx: click.Context,
  to: tuple[str, ...],
  cc: tuple[str, ...],
  bcc: tuple[str, ...],
  subject: str,
  body: str,
  html: bool,
  yes: bool,
  as_json: bool,
  pretty: bool,
) -> None:
  as_json_eff = as_json or ctx.obj.get("json", False)
  blocked = _confirm_mutation("send mail", as_json=as_json_eff, yes=yes)
  if blocked is not None:
    ctx.exit(blocked)
  from hugr import api
  doc = api.send_mail(list(to), subject, body, cc=list(cc), bcc=list(bcc), html=html)
  if pretty and not as_json_eff:
    _emit_action_pretty(doc)
  else:
    _emit_json_doc(doc)
  ctx.exit(int(doc.get("exit_code") or (0 if doc.get("ok") else 1)))


@send_group.command("invite")
@click.option("--subject", required=True)
@click.option("--date", default=None)
@click.option("--start", default=None)
@click.option("--end", default=None)
@click.option("--location", default=None)
@click.option("--body", default=None)
@click.option("--category", default=None)
@click.option("--showas", default=None)
@click.option("--yes", is_flag=True, default=False, help="Skip the interactive confirmation prompt.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON envelope on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def send_invite_cmd(
  ctx: click.Context,
  subject: str,
  date: str | None,
  start: str | None,
  end: str | None,
  location: str | None,
  body: str | None,
  category: str | None,
  showas: str | None,
  yes: bool,
  as_json: bool,
  pretty: bool,
) -> None:
  as_json_eff = as_json or ctx.obj.get("json", False)
  blocked = _confirm_mutation("send invite", as_json=as_json_eff, yes=yes)
  if blocked is not None:
    ctx.exit(blocked)
  from hugr import api
  doc = api.send_invite(
    subject,
    date=date,
    start=start,
    end=end,
    location=location,
    body=body,
    category=category,
    showas=showas,
  )
  if pretty and not as_json_eff:
    _emit_action_pretty(doc)
  else:
    _emit_json_doc(doc)
  ctx.exit(int(doc.get("exit_code") or (0 if doc.get("ok") else 1)))


@book_group.command("propose")
@click.argument("intent", nargs=-1, required=True)
@click.option("--who", multiple=True, required=True, help="Attendee (repeatable).")
@click.option("--duration", "duration_minutes", default=30, show_default=True, type=int)
@click.option("--date", default=None)
@click.option("--week", default=None)
@click.option("--year", default=None)
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def book_propose_cmd(
  ctx: click.Context,
  intent: tuple[str, ...],
  who: tuple[str, ...],
  duration_minutes: int,
  date: str | None,
  week: str | None,
  year: str | None,
  as_json: bool,
  pretty: bool,
) -> None:
  as_json_eff = as_json or ctx.obj.get("json", False)
  from hugr import api
  doc = api.schedule(
    _question_from_parts(intent),
    who=list(who),
    duration_minutes=duration_minutes,
    date=date,
    week=week,
    year=year,
  )
  if pretty and not as_json_eff:
    click.echo(f"hugr book propose: {doc.get('proposed_subject') or ''}")
    slots = doc.get("slots") or []
    if not slots:
      click.echo("(no slots found)")
    for idx, slot in enumerate(slots):
      label = " - ".join(
        str(slot.get(k))
        for k in ("date", "day", "start", "from", "end", "to")
        if slot.get(k)
      )
      click.echo(f"  [{idx}] {label}".rstrip())
    warn = doc.get("error")
    if warn:
      click.echo(f"warning: {warn.get('message')}", err=True)
  else:
    _emit_json_doc(doc)
  ctx.exit(0 if doc.get("ok") else int(doc.get("exit_code") or 1))


@book_group.command("commit")
@click.argument("intent", nargs=-1, required=True)
@click.option("--who", multiple=True, required=True, help="Attendee (repeatable).")
@click.option("--duration", "duration_minutes", default=30, show_default=True, type=int)
@click.option("--date", default=None)
@click.option("--week", default=None)
@click.option("--year", default=None)
@click.option("--slot", "slot_idx", default=0, show_default=True, type=int, help="Index into the proposal slot list.")
@click.option("--location", default=None)
@click.option("--body", default=None)
@click.option("--category", default=None)
@click.option("--yes", is_flag=True, default=False, help="Skip the interactive confirmation prompt.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON envelope on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def book_commit_cmd(
  ctx: click.Context,
  intent: tuple[str, ...],
  who: tuple[str, ...],
  duration_minutes: int,
  date: str | None,
  week: str | None,
  year: str | None,
  slot_idx: int,
  location: str | None,
  body: str | None,
  category: str | None,
  yes: bool,
  as_json: bool,
  pretty: bool,
) -> None:
  as_json_eff = as_json or ctx.obj.get("json", False)
  blocked = _confirm_mutation("book commit", as_json=as_json_eff, yes=yes)
  if blocked is not None:
    ctx.exit(blocked)
  from hugr import api
  intent_text = _question_from_parts(intent)
  proposal = api.schedule(
    intent_text,
    who=list(who),
    duration_minutes=duration_minutes,
    date=date,
    week=week,
    year=year,
  )
  slots = proposal.get("slots") or []
  if not slots or slot_idx < 0 or slot_idx >= len(slots):
    doc = {
      "tool": "hugr",
      "command": "book commit",
      "ok": False,
      "exit_code": 4,
      "request": {"intent": intent_text, "slot": slot_idx},
      "error": {
        "code": "slot_unavailable",
        "message": f"no proposal slot at index {slot_idx} (found {len(slots)})",
        "hint": "Run `hugr book propose` first to see available slots.",
      },
      "proposal": proposal,
    }
    if pretty and not as_json_eff:
      _emit_action_pretty(doc)
    else:
      _emit_json_doc(doc)
    ctx.exit(4)
  doc = api.schedule_commit(
    intent_text,
    who=list(who),
    slot=slots[slot_idx],
    location=location,
    body=body,
    category=category,
  )
  if pretty and not as_json_eff:
    _emit_action_pretty(doc)
  else:
    _emit_json_doc(doc)
  ctx.exit(int(doc.get("exit_code") or (0 if doc.get("ok") else 1)))


@cli.group("session", invoke_without_command=False)
def session_group() -> None:
  """Manage hugr sessions.

  A session is an optional workspace at ``$HUGR_HOME/sessions/<id>/``
  that hugr verbs share. Select one via ``HUGR_SESSION=<id>`` before
  running other verbs.
  """


@session_group.command("start")
@click.option("--ttl", "ttl_seconds", type=int, default=None, help="Session TTL in seconds (default 1800).")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON envelope on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def session_start_cmd(ctx: click.Context, ttl_seconds: int | None, as_json: bool, pretty: bool) -> None:
  from hugr import session as session_mod
  as_json_eff = as_json or ctx.obj.get("json", False)
  ttl = ttl_seconds or session_mod.SESSION_TTL_SECONDS
  meta = session_mod.start_session(ttl_seconds=ttl)
  doc = {
    "tool": "hugr",
    "command": "session start",
    "ok": True,
    "exit_code": 0,
    "session": meta.as_dict(),
    "hint": f"export HUGR_SESSION={meta.id}",
  }
  if pretty and not as_json_eff:
    click.echo(f"started session {meta.id}")
    click.echo(f"  export HUGR_SESSION={meta.id}")
  else:
    _emit_json_doc(doc)
  ctx.exit(0)


@session_group.command("end")
@click.argument("sid", required=False)
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON envelope on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def session_end_cmd(ctx: click.Context, sid: str | None, as_json: bool, pretty: bool) -> None:
  from hugr import session as session_mod
  target = sid or session_mod.current_session_id()
  as_json_eff = as_json or ctx.obj.get("json", False)
  if not target:
    doc = {
      "tool": "hugr",
      "command": "session end",
      "ok": False,
      "exit_code": 1,
      "error": {
        "code": "no_active_session",
        "message": "no session id provided and HUGR_SESSION is unset.",
        "hint": "hugr session end <id> or set HUGR_SESSION first.",
      },
    }
    if pretty and not as_json_eff:
      _emit_action_pretty(doc)
    else:
      _emit_json_doc(doc)
    ctx.exit(1)
  removed = session_mod.end_session(target)
  doc = {
    "tool": "hugr",
    "command": "session end",
    "ok": removed,
    "exit_code": 0 if removed else 4,
    "session_id": target,
  }
  if not removed:
    doc["error"] = {
      "code": "session_not_found",
      "message": f"no session {target}",
      "hint": "hugr session list",
    }
  if pretty and not as_json_eff:
    if removed:
      click.echo(f"ended session {target}")
    else:
      click.echo(f"no session {target}", err=True)
  else:
    _emit_json_doc(doc)
  ctx.exit(doc["exit_code"])


@session_group.command("status")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def session_status_cmd(ctx: click.Context, as_json: bool, pretty: bool) -> None:
  from hugr import session as session_mod
  as_json_eff = as_json or ctx.obj.get("json", False)
  doc = session_mod.status()
  if pretty and not as_json_eff:
    cur = doc.get("current_session_id")
    click.echo(f"current: {cur or '(none)'}")
    for s in doc.get("sessions") or []:
      mark = "*" if s.get("id") == cur else "-"
      click.echo(f"  {mark} {s.get('id')}  last_used={s.get('last_used_at')}  ttl={s.get('ttl_seconds')}s")
  else:
    _emit_json_doc(doc)
  ctx.exit(0)


@session_group.command("list")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def session_list_cmd(ctx: click.Context, as_json: bool, pretty: bool) -> None:
  from hugr import session as session_mod
  as_json_eff = as_json or ctx.obj.get("json", False)
  metas = [m.as_dict() for m in session_mod.list_sessions()]
  doc = {
    "tool": "hugr",
    "command": "session list",
    "ok": True,
    "exit_code": 0,
    "sessions": metas,
  }
  if pretty and not as_json_eff:
    for s in metas:
      click.echo(f"{s.get('id')}  last_used={s.get('last_used_at')}  ttl={s.get('ttl_seconds')}s")
  else:
    _emit_json_doc(doc)
  ctx.exit(0)


@session_group.command("gc")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON envelope on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def session_gc_cmd(ctx: click.Context, as_json: bool, pretty: bool) -> None:
  from hugr import session as session_mod
  as_json_eff = as_json or ctx.obj.get("json", False)
  removed = session_mod.gc_stale()
  doc = {
    "tool": "hugr",
    "command": "session gc",
    "ok": True,
    "exit_code": 0,
    "removed": removed,
    "count": len(removed),
  }
  if pretty and not as_json_eff:
    if not removed:
      click.echo("no stale sessions")
    else:
      click.echo(f"removed {len(removed)} stale session(s):")
      for sid in removed:
        click.echo(f"  - {sid}")
  else:
    _emit_json_doc(doc)
  ctx.exit(0)


@cli.command("init")
@click.option(
  "--json",
  "as_json",
  is_flag=True,
  default=False,
  help="Machine mode for `hugr init --quick`; rejected for interactive init.",
)
@click.option(
  "--force",
  is_flag=True,
  default=False,
  help="Overwrite an existing yaams config without prompting.",
)
@click.option(
  "--quick",
  is_flag=True,
  default=False,
  help="Run the non-interactive bootstrap path.",
)
@click.option(
  "--with-models",
  is_flag=True,
  default=False,
  help="Allow optional heavyweight model setup in quick mode.",
)
@click.pass_context
def init_cmd(ctx: click.Context, as_json: bool, force: bool, quick: bool, with_models: bool) -> None:
  from hugr.commands.init import run
  ctx.exit(run(
    as_json or ctx.obj.get("json", False),
    force=force,
    quick=quick,
    with_models=with_models,
  ))


def _yaams_config_env(full: tuple[str, ...]) -> dict[str, str]:
  """Return ``{"YAAMS_CONFIG": <yaams config path>}`` when hugr
  should hand a yaams config to the child via env, else ``{}``.

  The path is resolved from the master hugr config
  (``$XDG_CONFIG_HOME/hugr/config.toml``), falling back to the
  canonical ``$XDG_CONFIG_HOME/yaams/config.yaml``. yaams honors
  ``YAAMS_CONFIG`` natively, so forwarding the path through env keeps
  ``yaams <verb>`` and ``hugr <verb>`` resolving to the same config
  even on older yaams builds whose search path doesn't include
  ours.

  Conditions for injection (all must hold):

  - the head verb routes to yaams, AND
  - the user did not set ``YAAMS_CONFIG`` themselves, AND
  - the user did not pass ``--config`` explicitly, AND
  - a yaams config is resolvable on disk.

  Never overrides a user-set ``YAAMS_CONFIG``.
  """
  return yaams_config_env_for_args(full)


def _make_passthrough(name: str, head: tuple[str, ...]):
  """Generate a Click subcommand that forwards to the passthrough
  module after the first-run hint check."""

  @cli.command(
    name,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
  )
  @click.argument("args", nargs=-1, type=click.UNPROCESSED)
  @click.pass_context
  def _cmd(ctx: click.Context, args: tuple[str, ...]) -> None:
    full = (*head, *args)
    hint = _ensure_config(full)
    if hint is not None:
      ctx.exit(hint)
    from hugr.commands.passthrough import run
    ctx.exit(run(
      list(full),
      verbose=ctx.obj.get("verbose", False),
      top_level_json=ctx.obj.get("json", False),
      extra_env=_yaams_config_env(full) or None,
    ))

  _cmd.__doc__ = f"Run `hugr {name}` against the suite."
  return _cmd


# Translation-table-driven Click commands.
query_cmd = _make_passthrough("query", ("query",))
ingest_cmd = _make_passthrough("ingest", ("ingest",))
promote_cmd = _make_passthrough("promote", ("promote",))
ledger_cmd = _make_passthrough("ledger", ("ledger",))
auth_cmd = _make_passthrough("auth", ("auth",))
mail_cmd = _make_passthrough("mail", ("mail",))
cal_cmd = _make_passthrough("cal", ("cal",))
graph_cmd = _make_passthrough("graph", ("graph",))
people_cmd = _make_passthrough("people", ("people",))
schedule_cmd = _make_passthrough("schedule", ("schedule",))
drive_cmd = _make_passthrough("drive", ("drive",))


@cli.command("tui")
def tui_cmd() -> None:
  """Launch the interactive Textual TUI (requires [tui] extra)."""
  import sys
  try:
    from hugr.tui.app import run
  except ImportError:
    import click as _click
    _click.echo('tui extra not installed; pipx install "hugr-cli[tui]"', err=True)
    sys.exit(4)
  run()


@cli.command("web")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=7777, show_default=True, type=int)
@click.option("--public", "public", is_flag=True, default=False, help="Allow non-loopback bind with HUGR_WEB_TOKEN.")
def web_cmd(host: str, port: int, public: bool) -> None:
  """Launch the FastAPI web surface (requires [web] extra)."""
  from hugr.commands.web import launch
  launch(host=host, port=port, public=public)


@cli.command("server")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=7777, show_default=True, type=int)
@click.option("--insecure", is_flag=True, default=False, help="Allow non-loopback bind without an auth proxy.")
def server_cmd(host: str, port: int, insecure: bool) -> None:
  """Run hugr web/server runtime (requires [server] extra)."""
  from hugr.server.app import launch
  launch(host=host, port=port, insecure=insecure)


@cli.group("sync", invoke_without_command=False)
def sync_group() -> None:
  """Cross-device state sync over git + age."""


@sync_group.command("init")
@click.argument("repo_url")
@click.option("--clone-into", default=None, type=click.Path(), help="Target dir; defaults to $HUGR_HOME/state.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON envelope on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def sync_init_cmd(ctx: click.Context, repo_url: str, clone_into: str | None, as_json: bool, pretty: bool) -> None:
  from hugr import sync as sync_mod
  as_json_eff = as_json or ctx.obj.get("json", False)
  target = Path(clone_into) if clone_into else None
  envelope = sync_mod.init(repo_url, clone_into=target)
  doc = envelope.as_dict()
  if pretty and not as_json_eff:
    if envelope.ok:
      click.echo(f"hugr sync init: device={doc['device_id']}  public_key={doc['public_key']}")
      click.echo(f"  state repo at {doc['clone_into']}")
    else:
      _emit_action_pretty(doc)
  else:
    _emit_json_doc(doc)
  ctx.exit(envelope.exit_code)


@sync_group.command("status")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON document on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def sync_status_cmd(ctx: click.Context, as_json: bool, pretty: bool) -> None:
  from hugr import sync as sync_mod
  as_json_eff = as_json or ctx.obj.get("json", False)
  envelope = sync_mod.status()
  doc = envelope.as_dict()
  if pretty and not as_json_eff:
    if not envelope.ok:
      _emit_action_pretty(doc)
    else:
      click.echo(f"device:   {doc.get('device_id')}")
      click.echo(f"repo:     {doc.get('clone_into')}")
      click.echo(f"identity: {doc.get('public_key') or '(none)'}")
      recipients = doc.get("recipients") or []
      click.echo(f"recipients ({len(recipients)}):")
      for r in recipients:
        click.echo(f"  - {r.get('device')}: {r.get('public_key')}")
      last = doc.get("last_commit") or {}
      if last:
        click.echo(f"last commit: {last.get('sha', '')[:8]} {last.get('date', '')} {last.get('subject', '')}")
  else:
    _emit_json_doc(doc)
  ctx.exit(envelope.exit_code)


@sync_group.command("push")
@click.option("-m", "--message", default=None)
@click.option("--yes", is_flag=True, default=False, help="Skip the interactive confirmation prompt.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON envelope on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def sync_push_cmd(ctx: click.Context, message: str | None, yes: bool, as_json: bool, pretty: bool) -> None:
  from hugr import sync as sync_mod
  as_json_eff = as_json or ctx.obj.get("json", False)
  blocked = _confirm_mutation("sync push", as_json=as_json_eff, yes=yes)
  if blocked is not None:
    ctx.exit(blocked)
  envelope = sync_mod.push(message=message)
  doc = envelope.as_dict()
  if pretty and not as_json_eff:
    _emit_action_pretty(doc)
    for snap in doc.get("snapshots") or []:
      click.echo(f"  pushed: {snap}")
  else:
    _emit_json_doc(doc)
  ctx.exit(envelope.exit_code)


@sync_group.command("pull")
@click.option("--json", "as_json", is_flag=True, default=False, help="Machine mode (JSON envelope on stdout).")
@click.option("--pretty", is_flag=True, default=False, help="Human rendering.")
@click.pass_context
def sync_pull_cmd(ctx: click.Context, as_json: bool, pretty: bool) -> None:
  from hugr import sync as sync_mod
  as_json_eff = as_json or ctx.obj.get("json", False)
  envelope = sync_mod.pull()
  doc = envelope.as_dict()
  if pretty and not as_json_eff:
    _emit_action_pretty(doc)
    if envelope.ok:
      last = doc.get("last_commit") or {}
      click.echo(f"  last commit: {last.get('sha', '')[:8]} {last.get('subject', '')}")
      conflicts = doc.get("conflicts") or []
      for c in conflicts:
        saved = c.get("saved_theirs_to")
        tail = f" (incoming saved to {saved})" if saved else ""
        click.echo(f"  conflict: kept ours for {c.get('path', '')}{tail}")
      if conflicts:
        click.echo(f"  {len(conflicts)} conflict(s) need manual reconciliation")
  else:
    _emit_json_doc(doc)
  ctx.exit(envelope.exit_code)


def main() -> int:
  """Top-level entry. Catches Click usage errors so users get a clean
  one-line message instead of a Python traceback.

  Free-text diagnostics (per CONVENTIONS.md stream routing) go to
  stderr. Exit codes follow Click's defaults: 2 for usage errors, 1
  for everything else.
  """
  try:
    return cli(standalone_mode=False) or 0
  except click.exceptions.UsageError as exc:
    # `hugr --bad-flag`, `hugr hello --does-not-exist`, etc.
    # Click already builds a helpful message; just route it cleanly.
    exc.show(file=sys.stderr)
    return exc.exit_code
  except click.exceptions.Abort:
    # User hit Ctrl-C in an interactive prompt.
    sys.stderr.write("\nAborted.\n")
    return 1
  except click.exceptions.ClickException as exc:
    exc.show(file=sys.stderr)
    return exc.exit_code


if __name__ == "__main__":
  sys.exit(main())

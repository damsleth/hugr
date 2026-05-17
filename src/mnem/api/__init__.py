"""mnem.api - internal Python API for the mnem suite.

Internal API; subject to change until v2 stabilizes.

Every function here returns data - never writes to stdout or stderr.
Callers (CLI, TUI, web, MCP) own serialization.

Action-class wrappers return ``(exit_code: int, stdout_bytes: bytes)``.
The bytes contain the JSON envelope from the underlying tool; the
exit_code follows CONVENTIONS.md (0 ok, nonzero on failure) and agrees
with the ``ok`` field inside the envelope per the CONVENTIONS invariant.

Data-class wrappers return ``(exit_code: int, stdout_bytes: bytes)``
with the same semantics - bytes are the raw result document on success
or an error envelope on failure.

doctor() and version() return structured Python dicts directly (no
subprocess round-trip needed; they already build their data in-process).

Passthrough wrappers map one-to-one to rows in ``mnem.router.TABLE``
that have ``interactive=False``.  Interactive verbs (promote review,
auth setup) are not exposed here - they require a real TTY.

Plan-01 fused verbs return structured Python dictionaries directly.
"""

from __future__ import annotations

# Re-export the two in-process functions ---------------------------------

from mnem.api.doctor import doctor as doctor
from mnem.api.fused import ask as ask
from mnem.api.fused import find as find
from mnem.api.fused import inbox as inbox
from mnem.api.fused import remember as remember
from mnem.api.version import version as version

# Passthrough wrappers ---------------------------------------------------
# Each returns (exit_code: int, stdout_bytes: bytes).
# The exit_code is 0 on success; nonzero on failure.
# stdout_bytes is the raw JSON from the underlying tool (envelope or
# data document).  Callers parse or forward as needed.

from mnem.api._passthrough import call as _call


def yaams_query(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem query <args>`` (passthrough to ``yaams query``).

    Data-class.  Returns (exit_code, stdout_bytes).
    """
    return _call(["query", *args])


def yaams_ingest(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem ingest <args>`` (passthrough to ``yaams ingest``).

    Action-class.  stdout_bytes contains the JSON action envelope (or
    NDJSON stream for long runs; the final line is the result envelope).
    """
    return _call(["ingest", *args])


def yaams_promote_generate(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem promote generate <args>`` (passthrough to ``yaams promote generate``).

    Action-class.
    """
    return _call(["promote", "generate", *args])


def yaams_promote_list(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem promote list <args>`` (passthrough to ``yaams promote list``).

    Data-class.
    """
    return _call(["promote", "list", *args])


def ledger_init(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem ledger init <args>`` (passthrough to ``ledger init``).

    Action-class.
    """
    return _call(["ledger", "init", *args])


def ledger_paths(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem ledger paths <args>`` (passthrough to ``ledger paths``).

    Data-class.
    """
    return _call(["ledger", "paths", *args])


def ledger_query(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem ledger query <args>`` (passthrough to ``ledger query``).

    Data-class.
    """
    return _call(["ledger", "query", *args])


def ledger_loops(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem ledger loops <args>`` (passthrough to ``ledger loops``).

    Data-class.
    """
    return _call(["ledger", "loops", *args])


def ledger_notes(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem ledger notes <args>`` (passthrough to ``ledger notes``).

    Data-class.
    """
    return _call(["ledger", "notes", *args])


def ledger_context(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem ledger context <args>`` (passthrough to ``ledger context --format json``).

    Data-class.
    """
    return _call(["ledger", "context", *args])


def ledger_context_build(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem ledger context build <args>`` (passthrough to ``ledger context build``).

    Action-class.
    """
    return _call(["ledger", "context", "build", *args])


def ledger_context_profiles(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem ledger context profiles <args>`` (passthrough to ``ledger context profiles``).

    Data-class.
    """
    return _call(["ledger", "context", "profiles", *args])


def owa_piggy(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem auth <args>`` (passthrough to ``owa-piggy``).

    Routes via the ``auth`` verb prefix; ``args`` should start with the
    owa-piggy subcommand (e.g. ``["status"]``, ``["reseed"]``).
    Note: ``auth setup`` is interactive and raises ``ValueError``.
    """
    return _call(["auth", *args])


def owa_cal(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem calendar <args>`` (passthrough to ``owa-cal``).

    Data- or action-class depending on the subcommand.
    """
    return _call(["calendar", *args])


def owa_mail(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem mail <args>`` (passthrough to ``owa-mail``).

    Data- or action-class depending on the subcommand.
    """
    return _call(["mail", *args])


def owa_graph(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem graph <args>`` (passthrough to ``owa-graph``).

    Data- or action-class depending on the subcommand.
    """
    return _call(["graph", *args])


def owa_people(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem people <args>`` (passthrough to ``owa-people``).

    Data-class.
    """
    return _call(["people", *args])


def owa_sched(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem schedule <args>`` (passthrough to ``owa-sched``).

    Data- or action-class depending on the subcommand.
    """
    return _call(["schedule", *args])


def owa_drive(args: list[str]) -> tuple[int, bytes]:
    """Run ``mnem drive <args>`` (passthrough to ``owa-drive``).

    Data- or action-class depending on the subcommand.
    """
    return _call(["drive", *args])


__all__ = [
    "doctor",
    "version",
    "ask",
    "find",
    "inbox",
    "remember",
    "yaams_query",
    "yaams_ingest",
    "yaams_promote_generate",
    "yaams_promote_list",
    "ledger_init",
    "ledger_paths",
    "ledger_query",
    "ledger_loops",
    "ledger_notes",
    "ledger_context",
    "ledger_context_build",
    "ledger_context_profiles",
    "owa_piggy",
    "owa_cal",
    "owa_mail",
    "owa_graph",
    "owa_people",
    "owa_sched",
    "owa_drive",
]

"""``hugr.api.doctor`` - pure-function doctor report.

Delegates to ``hugr.commands.doctor.build_report()`` which fans out to
each component's ``--doctor --json`` endpoint.  Returns a plain dict;
never writes to stdout.
"""

from __future__ import annotations


def doctor() -> tuple[dict, int]:
    """Return ``(report_dict, exit_code)`` for the full suite health check.

    The dict shape is identical to what ``hugr doctor --json`` writes to
    stdout.  The exit_code follows CONVENTIONS.md (0 ok, 1 user-fixable,
    2 transient, 3 auth).

    No stdout/stderr is written.
    """
    from hugr.commands.doctor import build_report
    return build_report()

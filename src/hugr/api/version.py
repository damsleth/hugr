"""``hugr.api.version`` - pure-function version report.

Delegates to ``hugr.commands.version.build_report()`` which probes each
component binary.  Returns a plain dict; never writes to stdout.
"""

from __future__ import annotations


def version() -> dict:
    """Return the version data dict for hugr and all suite components.

    The dict shape is identical to what ``hugr version --json`` writes to
    stdout: ``{tool, version, components, packages}``.

    No stdout/stderr is written.
    """
    from hugr.commands.version import build_report
    return build_report()

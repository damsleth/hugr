"""``mnem.api.version`` - pure-function version report.

Delegates to ``mnem.commands.version.build_report()`` which probes each
component binary.  Returns a plain dict; never writes to stdout.
"""

from __future__ import annotations


def version() -> dict:
    """Return the version data dict for mnem and all suite components.

    The dict shape is identical to what ``mnem version --json`` writes to
    stdout: ``{tool, version, components, packages}``.

    No stdout/stderr is written.
    """
    from mnem.commands.version import build_report
    return build_report()

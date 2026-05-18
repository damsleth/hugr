"""Shared helper: call ``hugr.commands.passthrough.run()`` and return bytes.

API functions that wrap router-table verbs delegate here.  The helper
captures what the passthrough module *would* write to stdout, returns
it as raw bytes, and converts the exit code into a minimal envelope dict
for action-class callers.

Design constraint: this module does NOT write to stdout or stderr.
Callers receive data and decide how to serialize it.
"""

from __future__ import annotations

import os
import subprocess
from typing import Sequence

from hugr.config import yaams_config_env_for_args
from hugr.failure import parse_stdout, write_error_log
from hugr.router import lookup


def _capture_subprocess(
    argv: Sequence[str],
    *,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, bytes, str]:
    """Run a subprocess and capture stdout as bytes + stderr as str.

    Returns (returncode, stdout_bytes, stderr_text).
    Unlike the streaming passthrough in commands/passthrough.py, this
    version buffers everything - it is only for non-interactive verbs
    where the caller wants the result, not a live stream.
    """
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    try:
        proc = subprocess.run(
            list(argv),
            capture_output=True,
            env=env,
            check=False,
        )
    except FileNotFoundError as exc:
        return 127, b"", f"binary not on PATH: {exc}"
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", errors="replace")


def call(
    verb_args: Sequence[str],
    *,
    extra_env: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    """Resolve *verb_args* via the router and run the underlying tool.

    Returns ``(exit_code, stdout_bytes)``.

    - For action-class verbs the bytes contain the JSON envelope.
    - For data-class verbs the bytes contain the raw result document.
    - For interactive verbs this raises ``ValueError`` - callers must
      not route interactive commands through the API layer.
    - If the verb is unknown, returns ``(1, b"")``.

    No stdout/stderr is written.  The caller owns serialization.
    """
    resolved = lookup(list(verb_args))
    if resolved is None:
        return 1, b""

    mapping, rewritten = resolved
    if mapping.interactive:
        raise ValueError(
            f"interactive verb cannot be called via hugr.api: "
            f"{' '.join(verb_args)}"
        )

    argv = [mapping.binary, *rewritten]
    if mapping.json_policy == "inject" and "--json" not in argv:
        argv.append("--json")

    env_overlay = yaams_config_env_for_args(tuple(verb_args))
    if extra_env:
        env_overlay.update(extra_env)
    rc, stdout_bytes, stderr_text = _capture_subprocess(
        argv,
        extra_env=env_overlay or None,
    )

    stdout_str = stdout_bytes.decode("utf-8", errors="replace")
    envelope = parse_stdout(stdout_str)
    crashed = envelope is None and rc != 0
    failed = crashed or rc != 0 or (envelope is not None and envelope.get("ok") is False)

    if failed:
        write_error_log(
            tool=mapping.binary,
            argv=argv,
            exit_code=rc,
            stderr_text=stderr_text,
        )

    return rc, stdout_bytes

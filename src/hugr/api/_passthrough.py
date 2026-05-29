"""Shared helper: call ``hugr.commands.passthrough.run()`` and return bytes.

API functions that wrap router-table verbs delegate here.  The helper
captures what the passthrough module *would* write to stdout, returns
it as raw bytes, and converts the exit code into a minimal envelope dict
for action-class callers.

Design constraint: this module does NOT write to stdout, and the
stdout bytes it returns are owned by the caller (which may embed them
in a JSON envelope). The one exception is verbose mode: when the user
asks for -v/--verbose/--debug, the child's diagnostic *stderr* is
echoed (redacted) to hugr's stderr so they can see what is happening
under the hood. Per CONVENTIONS.md diagnostics belong on stderr, so
this never touches the stdout contract.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Sequence

from hugr.conventions import redact
from hugr.config import yaams_config_env_for_args
from hugr.failure import parse_stdout, write_error_log
from hugr.router import lookup, verbose_overlay


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
    verbose: bool = False,
) -> tuple[int, bytes]:
    """Resolve *verb_args* via the router and run the underlying tool.

    Returns ``(exit_code, stdout_bytes)``.

    - For action-class verbs the bytes contain the JSON envelope.
    - For data-class verbs the bytes contain the raw result document.
    - For interactive verbs this raises ``ValueError`` - callers must
      not route interactive commands through the API layer.
    - If the verb is unknown, returns ``(1, b"")``.

    ``verbose`` forwards the user's -v/--verbose/--debug intent to the
    child via the per-row strategy in the router. Rows with no verbose
    mechanism (e.g. owa-piggy) are a no-op.

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

    verbose_env: dict[str, str] = {}
    if verbose:
        verbose_env, verbose_argv = verbose_overlay(mapping)
        for flag in verbose_argv:
            if flag not in argv:
                argv.append(flag)

    if mapping.json_policy == "inject" and "--json" not in argv:
        argv.append("--json")

    env_overlay = yaams_config_env_for_args(tuple(verb_args))
    if verbose_env:
        env_overlay.update(verbose_env)
    if extra_env:
        env_overlay.update(extra_env)
    rc, stdout_bytes, stderr_text = _capture_subprocess(
        argv,
        extra_env=env_overlay or None,
    )

    # Verbose mode: surface the child's diagnostics (redacted) so the
    # forwarded -v/--debug actually shows under-the-hood output. Goes to
    # stderr only; the returned stdout bytes are untouched.
    if verbose and stderr_text:
        sys.stderr.write(redact(stderr_text))
        if not stderr_text.endswith("\n"):
            sys.stderr.write("\n")
        sys.stderr.flush()

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

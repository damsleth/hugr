"""hugr's binding to the shared CLI contract.

The contract itself lives in the ``hugr-conventions`` package (the
executable form of CONVENTIONS.md), which every binary in the suite
depends on. This module binds it to hugr's tool name and version and
re-exports the names hugr's own code and tests use, so call sites
read ``from hugr.conventions import action_envelope`` without
threading ``tool=`` / ``version=`` through every call.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import hugr_conventions as _hc
from hugr_conventions import (
  EXIT_AUTH,
  EXIT_NOT_FOUND,
  EXIT_OK,
  EXIT_PARTIAL,
  EXIT_TRANSIENT,
  EXIT_USER_ERROR,
  DoctorFinding,
  emit_action,
  emit_data_error,
  now_iso,
  redact,
  stream_progress,
  stream_result,
  stream_warning,
)

__all__ = [
  "EXIT_OK",
  "EXIT_USER_ERROR",
  "EXIT_TRANSIENT",
  "EXIT_AUTH",
  "EXIT_NOT_FOUND",
  "EXIT_PARTIAL",
  "TOOL_NAME",
  "redact",
  "now_iso",
  "action_envelope",
  "emit_action",
  "data_error",
  "emit_data_error",
  "stream_progress",
  "stream_warning",
  "stream_result",
  "DoctorFinding",
  "DoctorPayload",
]

TOOL_NAME = "hugr"


def _version() -> str:
  from hugr import __version__
  return __version__


_C = _hc.bind(TOOL_NAME, _version)


def action_envelope(
  *,
  command: str,
  ok: bool,
  stats: Mapping[str, Any] | None = None,
  warnings: Iterable[str] | None = None,
  error: Mapping[str, Any] | None = None,
  duration_ms: float | None = None,
) -> dict[str, Any]:
  return _C.action_envelope(
    command=command,
    ok=ok,
    stats=stats,
    warnings=warnings,
    error=error,
    duration_ms=duration_ms,
  )


def data_error(
  *,
  command: str,
  code: str,
  message: str,
  hint: str | None = None,
) -> dict[str, Any]:
  return _C.data_error(command=command, code=code, message=message, hint=hint)


def DoctorPayload(**kwargs: Any) -> _hc.DoctorPayload:  # noqa: N802 - preserves call site
  """hugr-bound :class:`hugr_conventions.DoctorPayload`.

  Defaults ``tool`` to ``"hugr"`` and ``version`` to the live package
  version so existing call sites construct it with no arguments.
  """
  kwargs.setdefault("tool", TOOL_NAME)
  kwargs.setdefault("version", _version)
  return _hc.DoctorPayload(**kwargs)

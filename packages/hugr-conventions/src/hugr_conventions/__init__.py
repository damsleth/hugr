"""Shared CLI-contract primitives for the hugr memory suite.

Every JSON-capable binary in the suite (``yaams``, ``ledger``,
``sheep``, ``owa-piggy``, the eight ``owa-*`` tools, and ``hugr``
itself) implements the same wire contract: action envelopes, a
data-class error envelope, NDJSON streaming, a ``--doctor`` payload,
the 0-5 exit-code taxonomy, and a stderr redactor. Until now each
repo carried a near-identical hand-copied ``conventions.py``; this
package is the single source of truth they depend on instead.

The contract itself is specified in ``CONVENTIONS.md`` in the hugr
repo. This module is the executable form of that spec.

Two ways to use it:

* **Bound** (recommended) - call :func:`bind` once with your tool
  name and version, then use the returned object's methods, which
  fill ``tool`` and ``version`` for you::

      from hugr_conventions import bind
      C = bind("owa-mail", lambda: __version__)
      C.emit_action(C.action_envelope(command="send", ok=True))

* **Explicit** - call the module-level functions with ``tool`` and
  ``version`` passed every time. Useful when one process emits
  envelopes on behalf of several tools (e.g. an aggregator).

``version`` may be a plain string or a zero-argument callable; the
callable form lets a tool defer importing its own ``__version__``
until an envelope is actually emitted, avoiding import cycles.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, TextIO

__all__ = [
  "EXIT_OK",
  "EXIT_USER_ERROR",
  "EXIT_TRANSIENT",
  "EXIT_AUTH",
  "EXIT_NOT_FOUND",
  "EXIT_PARTIAL",
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
  "emit_doctor",
  "bind",
  "Conventions",
]

__version__ = "0.1.0"


# --- Exit codes (CONVENTIONS.md "Exit codes") ------------------------------

EXIT_OK = 0
EXIT_USER_ERROR = 1
EXIT_TRANSIENT = 2
EXIT_AUTH = 3
EXIT_NOT_FOUND = 4
EXIT_PARTIAL = 5


# --- Redaction (CONVENTIONS.md "Redaction") --------------------------------

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._\-+/=]+")
_TOKEN_FIELD_RE = re.compile(
  r'(?i)"(access_token|refresh_token|id_token|client_secret|api_key|secret)"\s*:\s*"[^"]*"'
)
_BODY_FIELD_RE = re.compile(
  r'(?i)"(body|content|text|html_body|plain_body)"\s*:\s*"[^"]*"'
)


def redact(text: Any) -> str:
  """Redact secret-shaped substrings from text bound for stderr/logs.

  Catches JWT-like triples, ``Bearer`` headers, token/secret JSON
  field values, and mail/message body fields. Tools layer their own
  domain redaction (attachment paths, etc.) on top; this is the
  suite-wide floor every binary shares so a sentinel can never leak
  through the common path.
  """
  if text is None:
    return ""
  if not isinstance(text, str):
    text = str(text)
  text = _JWT_RE.sub("<redacted-jwt>", text)
  text = _BEARER_RE.sub("Bearer <redacted>", text)
  text = _TOKEN_FIELD_RE.sub(lambda m: f'"{m.group(1)}":"<redacted>"', text)
  text = _BODY_FIELD_RE.sub(lambda m: f'"{m.group(1)}":"<redacted>"', text)
  return text


def now_iso() -> str:
  """UTC timestamp in the ``ts`` shape the streaming contract uses."""
  return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# --- internals -------------------------------------------------------------

VersionLike = "str | Callable[[], str]"


def _resolve_version(version: "str | Callable[[], str]") -> str:
  if callable(version):
    return str(version())
  return str(version)


def _writeln(obj: Mapping[str, Any], stream: TextIO | None) -> None:
  stream = stream if stream is not None else sys.stdout
  stream.write(json.dumps(obj, ensure_ascii=False) + "\n")
  stream.flush()


# --- Action envelope (CONVENTIONS.md "Action envelope schema") -------------

def action_envelope(
  *,
  tool: str,
  version: "str | Callable[[], str]",
  command: str,
  ok: bool,
  stats: Mapping[str, Any] | None = None,
  warnings: Iterable[str] | None = None,
  error: Mapping[str, Any] | None = None,
  duration_ms: float | None = None,
) -> dict[str, Any]:
  """Build an action-class result envelope.

  Invariant per the spec: callers MUST keep ``ok`` in agreement with
  the process exit code (``ok: false`` iff exit code nonzero).
  """
  return {
    "tool": tool,
    "version": _resolve_version(version),
    "command": command,
    "ok": bool(ok),
    "duration_ms": float(duration_ms) if duration_ms is not None else 0.0,
    "stats": dict(stats or {}),
    "warnings": list(warnings or []),
    "error": dict(error) if error else None,
  }


def emit_action(envelope: Mapping[str, Any], stream: TextIO | None = None) -> None:
  """Write a single-line action envelope on stdout (or ``stream``)."""
  _writeln(envelope, stream)


# --- Data-class failure envelope (CONVENTIONS.md "Data-class failure ...") -

def data_error(
  *,
  tool: str,
  version: "str | Callable[[], str]",
  command: str,
  code: str,
  message: str,
  hint: str | None = None,
) -> dict[str, Any]:
  """Build the minimal error envelope a data command emits on failure.

  Data commands emit raw documents on success and switch to this
  envelope on failure so JSON-aware callers always get parseable
  JSON keyed on the reserved ``ok`` discriminator.
  """
  err: dict[str, Any] = {"code": code, "message": message}
  if hint:
    err["hint"] = hint
  return {
    "tool": tool,
    "version": _resolve_version(version),
    "command": command,
    "ok": False,
    "error": err,
  }


def emit_data_error(envelope: Mapping[str, Any], stream: TextIO | None = None) -> None:
  """Write a data-class error envelope on stdout (or ``stream``).

  Per the spec's stream-routing rule, structured failure envelopes
  travel on stdout alongside success output so a single parser on a
  single stream handles both paths. Free-text errors still go to
  stderr; this governs only the structured envelope.
  """
  _writeln(envelope, stream)


# --- NDJSON streaming (CONVENTIONS.md "Streaming schema") ------------------

def stream_progress(
  *,
  source: str | None = None,
  stage: str | None = None,
  done: int | None = None,
  total: int | None = None,
  stream: TextIO | None = None,
) -> None:
  """Emit a ``{"type":"progress", ...}`` NDJSON line."""
  payload: dict[str, Any] = {"type": "progress", "ts": now_iso()}
  if source is not None:
    payload["source"] = source
  if stage is not None:
    payload["stage"] = stage
  if done is not None:
    payload["done"] = done
  if total is not None:
    payload["total"] = total
  _writeln(payload, stream)


def stream_warning(
  message: str, *, source: str | None = None, stream: TextIO | None = None
) -> None:
  """Emit a ``{"type":"warning", ...}`` NDJSON line, redacting the message."""
  payload: dict[str, Any] = {"type": "warning", "message": redact(message), "ts": now_iso()}
  if source is not None:
    payload["source"] = source
  _writeln(payload, stream)


def stream_result(envelope: Mapping[str, Any], stream: TextIO | None = None) -> None:
  """Emit the terminal ``{"type":"result", ...full envelope...}`` line."""
  _writeln({"type": "result", **dict(envelope)}, stream)


# --- Doctor payload (CONVENTIONS.md "Doctor JSON schema") ------------------

@dataclass
class DoctorFinding:
  id: str
  severity: str  # "info" | "warning" | "error"
  message: str
  hint: str | None = None

  def to_dict(self) -> dict[str, Any]:
    out: dict[str, Any] = {
      "id": self.id,
      "severity": self.severity,
      "message": self.message,
    }
    if self.hint:
      out["hint"] = self.hint
    return out


@dataclass
class DoctorPayload:
  tool: str
  version: "str | Callable[[], str]" = "0.0.0"
  config_path: str | None = None
  data_path: str | None = None
  auth: dict[str, Any] | None = None
  models: dict[str, Any] | None = None
  findings: list[DoctorFinding] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    out: dict[str, Any] = {
      "tool": self.tool,
      "version": _resolve_version(self.version),
    }
    if self.config_path is not None:
      out["config_path"] = self.config_path
    if self.data_path is not None:
      out["data_path"] = self.data_path
    if self.auth is not None:
      out["auth"] = self.auth
    if self.models is not None:
      out["models"] = self.models
    out["findings"] = [f.to_dict() for f in self.findings]
    return out

  def exit_code(self) -> int:
    """Exit code from the highest-severity finding.

    ``error`` maps to user-error by default; a tool whose error is
    auth- or transient-shaped should set the exit code itself rather
    than rely on this floor.
    """
    severities = {f.severity for f in self.findings}
    if "error" in severities:
      return EXIT_USER_ERROR
    return EXIT_OK


def emit_doctor(
  payload: DoctorPayload, *, as_json: bool, stream: TextIO | None = None
) -> int:
  """Emit a doctor payload (JSON or human) and return its exit code."""
  if as_json:
    _writeln(payload.to_dict(), stream)
  else:
    _print_doctor_human(payload, stream if stream is not None else sys.stdout)
  return payload.exit_code()


def _print_doctor_human(payload: DoctorPayload, stream: TextIO) -> None:
  data = payload.to_dict()
  print(f"{payload.tool} doctor (v{data['version']})", file=stream)
  if payload.config_path:
    print(f"  config: {payload.config_path}", file=stream)
  if payload.data_path:
    print(f"  data:   {payload.data_path}", file=stream)
  if payload.auth:
    print(f"  auth:   {payload.auth}", file=stream)
  if not payload.findings:
    print("  status: ok", file=stream)
    return
  print(f"  findings: {len(payload.findings)}", file=stream)
  for f in payload.findings:
    marker = {"error": "x", "warning": "!", "info": "."}.get(f.severity, ".")
    print(f"    {marker} [{f.severity}] {f.id}: {f.message}", file=stream)
    if f.hint:
      print(f"        hint: {f.hint}", file=stream)


# --- Bound convenience wrapper ---------------------------------------------

class Conventions:
  """Tool-bound view over the contract.

  Holds a tool name and version (string or callable) so call sites
  don't repeat them. Returned by :func:`bind`.
  """

  __slots__ = ("tool", "_version")

  def __init__(self, tool: str, version: "str | Callable[[], str]") -> None:
    self.tool = tool
    self._version = version

  @property
  def version(self) -> str:
    return _resolve_version(self._version)

  def action_envelope(
    self,
    *,
    command: str,
    ok: bool,
    stats: Mapping[str, Any] | None = None,
    warnings: Iterable[str] | None = None,
    error: Mapping[str, Any] | None = None,
    duration_ms: float | None = None,
  ) -> dict[str, Any]:
    return action_envelope(
      tool=self.tool,
      version=self._version,
      command=command,
      ok=ok,
      stats=stats,
      warnings=warnings,
      error=error,
      duration_ms=duration_ms,
    )

  def data_error(
    self, *, command: str, code: str, message: str, hint: str | None = None
  ) -> dict[str, Any]:
    return data_error(
      tool=self.tool,
      version=self._version,
      command=command,
      code=code,
      message=message,
      hint=hint,
    )

  def doctor_payload(self, **kwargs: Any) -> DoctorPayload:
    kwargs.setdefault("tool", self.tool)
    kwargs.setdefault("version", self._version)
    return DoctorPayload(**kwargs)

  # Emitters are stateless; re-exported as methods for one-stop access.
  emit_action = staticmethod(emit_action)
  emit_data_error = staticmethod(emit_data_error)
  emit_doctor = staticmethod(emit_doctor)
  stream_progress = staticmethod(stream_progress)
  stream_warning = staticmethod(stream_warning)
  stream_result = staticmethod(stream_result)
  redact = staticmethod(redact)


def bind(tool: str, version: "str | Callable[[], str]") -> Conventions:
  """Bind the contract to a tool name and version.

  ``version`` may be a string or a zero-arg callable (e.g.
  ``lambda: mypkg.__version__``) resolved lazily at emit time.
  """
  return Conventions(tool, version)

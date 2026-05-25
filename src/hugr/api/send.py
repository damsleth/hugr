"""Send wrappers: fused mutating verbs over owa-mail / owa-cal.

`send_mail()` wraps ``owa-mail send``; `send_invite()` wraps
``owa-cal create``. Both return an action envelope:

    {
        "tool": "hugr",
        "command": "send mail" | "send invite",
        "ok": bool,
        "exit_code": int,
        "request": {...echoed input...},
        "result": <decoded child output>,
        "error": None | {code, message, hint},
    }

These functions never write to stdout/stderr and never prompt - the
CLI layer owns interactive confirmation per plan 01.4.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from hugr.api._passthrough import call as _call


def _decode(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return raw.decode("utf-8", errors="replace")


def _ok_from(rc: int, decoded: Any) -> bool:
    if rc != 0:
        return False
    if isinstance(decoded, dict) and decoded.get("ok") is False:
        return False
    return True


def _envelope(
    command: str,
    *,
    request: dict[str, Any],
    rc: int,
    raw: bytes,
    error_code: str,
    error_message: str,
    error_hint: str,
) -> dict[str, Any]:
    decoded = _decode(raw)
    ok = _ok_from(rc, decoded)
    return {
        "tool": "hugr",
        "command": command,
        "ok": ok,
        "exit_code": rc,
        "request": request,
        "result": decoded,
        "error": None if ok else {
            "code": error_code,
            "message": error_message,
            "hint": error_hint,
        },
    }


def _join_addrs(addrs: Sequence[str]) -> str:
    return ",".join(a.strip() for a in addrs if a and a.strip())


def send_mail(
    to: Sequence[str],
    subject: str,
    body: str,
    *,
    cc: Sequence[str] = (),
    bcc: Sequence[str] = (),
    html: bool = False,
) -> dict[str, Any]:
    """Send mail via ``owa-mail send``.

    Recipients are joined with commas to match the owa-mail CLI shape.
    """
    args = [
        "mail", "send",
        "--to", _join_addrs(to),
        "--subject", subject,
        "--body", body,
    ]
    cc_joined = _join_addrs(cc)
    if cc_joined:
        args.extend(["--cc", cc_joined])
    bcc_joined = _join_addrs(bcc)
    if bcc_joined:
        args.extend(["--bcc", bcc_joined])
    if html:
        args.append("--html")
    rc, raw = _call(args)
    return _envelope(
        "send mail",
        request={
            "to": list(to),
            "subject": subject,
            "cc": list(cc),
            "bcc": list(bcc),
            "html": html,
            "body_length": len(body),
        },
        rc=rc,
        raw=raw,
        error_code="owa_mail_send_failed",
        error_message="owa-mail send failed",
        error_hint="Run `hugr mail send --help` to inspect the underlying flags.",
    )


def send_invite(
    subject: str,
    *,
    date: str | None = None,
    start: str | None = None,
    end: str | None = None,
    location: str | None = None,
    body: str | None = None,
    category: str | None = None,
    showas: str | None = None,
) -> dict[str, Any]:
    """Create a calendar event via ``owa-cal create``.

    Note: ``owa-cal create`` does not yet accept attendees - this is a
    flagged upstream gap in owa-tools. For solo events this is a
    one-call wrapper; for attendee-bearing meetings the user still has
    to follow up with a manual invite until owa-tools v0.2 lands.
    """
    args = ["cal", "create", "--subject", subject]
    if date is not None:
        args.extend(["--date", date])
    if start is not None:
        args.extend(["--start", start])
    if end is not None:
        args.extend(["--end", end])
    if location is not None:
        args.extend(["--location", location])
    if body is not None:
        args.extend(["--body", body])
    if category is not None:
        args.extend(["--category", category])
    if showas is not None:
        args.extend(["--showas", showas])
    rc, raw = _call(args)
    return _envelope(
        "send invite",
        request={
            "subject": subject,
            "date": date,
            "start": start,
            "end": end,
            "location": location,
            "category": category,
            "showas": showas,
            "has_body": body is not None,
        },
        rc=rc,
        raw=raw,
        error_code="owa_cal_create_failed",
        error_message="owa-cal create failed",
        error_hint="Run `hugr cal create --help` to inspect the underlying flags.",
    )

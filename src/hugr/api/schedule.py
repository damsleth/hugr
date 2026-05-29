"""Schedule wrapper: owa-sched find-time + owa-cal create.

The default ``schedule()`` is a data-class verb that returns a slot
proposal without mutating anything. ``schedule_commit()`` takes a
proposal slot and creates the calendar event via ``send_invite()``.

The CLI ``hugr schedule`` exposes both modes:

    hugr schedule "intent" --who a@b.com --duration 30 --date tomorrow
        # returns slot proposal
    hugr schedule "intent" --who ... --commit --slot 0 --yes
        # creates the event from slot 0
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from hugr.api._passthrough import call as _call
from hugr.api.send import send_invite


def _decode(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return raw.decode("utf-8", errors="replace")


def _slots_from(decoded: Any) -> list[dict[str, Any]]:
    """Pull a normalized slot list out of owa-sched output.

    owa-sched find-time emits a few possible shapes depending on flags;
    accept anything that looks like {"slots":[...]} or a bare list.
    """
    if isinstance(decoded, list):
        return [s for s in decoded if isinstance(s, dict)]
    if isinstance(decoded, dict):
        for key in ("slots", "results", "data"):
            value = decoded.get(key)
            if isinstance(value, list):
                return [s for s in value if isinstance(s, dict)]
    return []


def schedule(
    intent: str,
    *,
    who: Sequence[str],
    duration_minutes: int = 30,
    date: str | None = None,
    week: str | None = None,
    year: str | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Find candidate slots for *intent* using ``owa-sched find-time``.

    Returns a proposal document with ``slots`` populated. Does not
    mutate anything; the user reviews and commits separately.
    """
    args = [
        "schedule", "find-time",
        "--who", ",".join(a.strip() for a in who if a and a.strip()),
        "--duration", str(duration_minutes),
    ]
    if date is not None:
        args.extend(["--date", date])
    if week is not None:
        args.extend(["--week", week])
    if year is not None:
        args.extend(["--year", year])

    rc, raw = _call(args, verbose=verbose)
    decoded = _decode(raw)
    ok = rc == 0 and not (isinstance(decoded, dict) and decoded.get("ok") is False)
    slots = _slots_from(decoded) if ok else []

    return {
        "tool": "hugr",
        "command": "schedule",
        "ok": ok,
        "exit_code": rc,
        "intent": intent,
        "proposed_subject": intent.strip(),
        "request": {
            "who": list(who),
            "duration_minutes": duration_minutes,
            "date": date,
            "week": week,
            "year": year,
        },
        "slots": slots,
        "raw": decoded,
        "error": None if ok else {
            "code": "owa_sched_find_time_failed",
            "message": "owa-sched find-time failed",
            "hint": "Run `hugr schedule find-time --help` (the underlying owa-sched verb) for flag details.",
        },
    }


def schedule_commit(
    intent: str,
    *,
    who: Sequence[str],
    slot: dict[str, Any],
    location: str | None = None,
    body: str | None = None,
    category: str | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    """Create the calendar event from a proposal *slot*.

    *slot* is expected to carry keys like ``date``, ``start``, ``end``
    (matching owa-sched output). Missing fields are forwarded as None
    so owa-cal applies its own defaults.
    """
    return send_invite(
        intent.strip(),
        date=slot.get("date") or slot.get("day"),
        start=slot.get("start") or slot.get("from"),
        end=slot.get("end") or slot.get("to"),
        location=location,
        body=body,
        category=category,
        verbose=verbose,
    )

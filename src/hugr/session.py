"""Hugr session storage (Plan 01.5).

A session is an optional, per-process workspace at
``$HUGR_HOME/sessions/<id>/`` that subsequent verbs share. It holds
``meta.json``, ``last_recall.json``, ``working_set.json``, and a
free-form ``scratch.md`` the user (or surface) may edit.

The session id is selected via the ``HUGR_SESSION`` env var; absent
that, sessions are off and every verb runs stateless.

This module is in-process file I/O only - no subprocess, no stdout.
The CLI / TUI / web surfaces own user-facing serialization.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hugr.config import data_root_default


SESSION_TTL_SECONDS = 30 * 60
SESSION_ENV = "HUGR_SESSION"


def sessions_root() -> Path:
    return data_root_default() / "sessions"


def session_dir(sid: str) -> Path:
    return sessions_root() / sid


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def current_session_id() -> str | None:
    sid = os.environ.get(SESSION_ENV)
    return sid.strip() if sid and sid.strip() else None


def _new_session_id() -> str:
    return secrets.token_hex(4)


@dataclass
class SessionMeta:
    id: str
    created_at: str
    last_used_at: str
    ttl_seconds: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, doc: dict[str, Any]) -> "SessionMeta":
        return cls(
            id=str(doc.get("id", "")),
            created_at=str(doc.get("created_at", "")),
            last_used_at=str(doc.get("last_used_at", "")),
            ttl_seconds=int(doc.get("ttl_seconds", SESSION_TTL_SECONDS)),
        )


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


def read_meta(sid: str) -> SessionMeta | None:
    doc = _read_json(session_dir(sid) / "meta.json")
    return SessionMeta.from_dict(doc) if isinstance(doc, dict) else None


def write_meta(meta: SessionMeta) -> None:
    _write_json(session_dir(meta.id) / "meta.json", meta.as_dict())


def touch(sid: str) -> SessionMeta | None:
    """Update last_used_at on the active session. Returns the new meta."""
    meta = read_meta(sid)
    if meta is None:
        return None
    meta.last_used_at = _iso(_now())
    write_meta(meta)
    return meta


def start_session(*, ttl_seconds: int = SESSION_TTL_SECONDS) -> SessionMeta:
    sid = _new_session_id()
    now = _iso(_now())
    meta = SessionMeta(
        id=sid,
        created_at=now,
        last_used_at=now,
        ttl_seconds=ttl_seconds,
    )
    write_meta(meta)
    return meta


def end_session(sid: str) -> bool:
    """Remove the session directory. Returns True if it existed."""
    target = session_dir(sid)
    if not target.exists():
        return False
    shutil.rmtree(target, ignore_errors=True)
    return True


def list_sessions() -> list[SessionMeta]:
    root = sessions_root()
    if not root.is_dir():
        return []
    metas: list[SessionMeta] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        meta = read_meta(child.name)
        if meta is not None:
            metas.append(meta)
    return metas


def is_stale(meta: SessionMeta, *, now: datetime | None = None) -> bool:
    try:
        used = datetime.fromisoformat(meta.last_used_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    cutoff = (now or _now()).timestamp() - meta.ttl_seconds
    return used.timestamp() < cutoff


def gc_stale(*, now: datetime | None = None) -> list[str]:
    """Remove stale session dirs. Returns the list of removed ids."""
    removed: list[str] = []
    for meta in list_sessions():
        if is_stale(meta, now=now):
            if end_session(meta.id):
                removed.append(meta.id)
    return removed


def read_last_recall(sid: str) -> dict[str, Any] | None:
    doc = _read_json(session_dir(sid) / "last_recall.json")
    return doc if isinstance(doc, dict) else None


def write_last_recall(sid: str, recall_doc: dict[str, Any]) -> None:
    _write_json(session_dir(sid) / "last_recall.json", recall_doc)


def read_working_set(sid: str) -> list[Any]:
    doc = _read_json(session_dir(sid) / "working_set.json")
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict) and isinstance(doc.get("items"), list):
        return doc["items"]
    return []


def write_working_set(sid: str, items: list[Any]) -> None:
    _write_json(
        session_dir(sid) / "working_set.json",
        {"items": items, "updated_at": _iso(_now())},
    )


def status() -> dict[str, Any]:
    """Snapshot for ``hugr session status``."""
    sid = current_session_id()
    active = read_meta(sid) if sid else None
    if active is not None:
        active = active.as_dict()
    sessions = [m.as_dict() for m in list_sessions()]
    return {
        "tool": "hugr",
        "command": "session status",
        "ok": True,
        "exit_code": 0,
        "current_session_id": sid,
        "active": active,
        "sessions": sessions,
    }

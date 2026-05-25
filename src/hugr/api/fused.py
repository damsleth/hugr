"""Fused high-level verbs for the hugr suite.

These functions orchestrate existing tool-backed API wrappers and return
plain Python data. They do not write to stdout/stderr.
"""

from __future__ import annotations

import json
from typing import Any, Sequence

from hugr.api._passthrough import call as _call
from hugr import session as _session


def _decode_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return raw.decode("utf-8", errors="replace")


def _source_result(source: str, command: str, rc: int, raw: bytes) -> dict[str, Any]:
    decoded = _decode_json(raw)
    ok = rc == 0
    if isinstance(decoded, dict) and decoded.get("ok") is False:
        ok = False
    return {
        "source": source,
        "command": command,
        "ok": ok,
        "exit_code": rc,
        "data": decoded,
    }


def _append_source(
    out: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    *,
    source: str,
    command: str,
    verb_args: Sequence[str],
) -> None:
    rc, raw = _call(list(verb_args))
    item = _source_result(source, command, rc, raw)
    out.append(item)
    if not item["ok"]:
        warnings.append({
            "source": source,
            "command": command,
            "exit_code": rc,
            "message": "source query failed",
        })


def _citation_for(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data")
    label = item["source"]
    ref = item["command"]
    if isinstance(data, dict):
        label = str(data.get("tool") or data.get("source") or label)
        ref = str(data.get("id") or data.get("command") or ref)
    return {
        "source": item["source"],
        "label": label,
        "ref": ref,
        "ok": item["ok"],
    }


def recall(question: str, *, k: int = 10, live: bool = True) -> dict[str, Any]:
    """Ask across YAAMS/Tier 2 plus opportunistic live M365 buckets."""
    sources: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    _append_source(
        sources,
        warnings,
        source="yaams",
        command="query",
        verb_args=["query", question],
    )
    if live:
        _append_source(
            sources,
            warnings,
            source="owa-cal",
            command="events",
            verb_args=["cal", "events", "--search", question],
        )
        _append_source(
            sources,
            warnings,
            source="owa-mail",
            command="search",
            verb_args=["mail", "search", question],
        )

    doc = {
        "tool": "hugr",
        "command": "recall",
        "query": question,
        "limit": k,
        "sources": sources,
        "citations": [_citation_for(item) for item in sources if item["ok"]],
        "warnings": warnings,
    }
    sid = _session.current_session_id()
    if sid is not None and _session.read_meta(sid) is not None:
        _session.write_last_recall(sid, doc)
        _session.touch(sid)
    return doc


def find(kind: str, query: str, *, k: int = 10) -> dict[str, Any]:
    """Typed search over the relevant underlying tool."""
    kind = kind.lower()
    routes: dict[str, tuple[str, str, list[str]]] = {
        "person": ("owa-people", "lookup", ["people", "lookup", query]),
        "people": ("owa-people", "lookup", ["people", "lookup", query]),
        "event": ("owa-cal", "events", ["cal", "events", "--search", query]),
        "message": ("owa-mail", "search", ["mail", "search", query]),
        "mail": ("owa-mail", "search", ["mail", "search", query]),
        "note": ("ledger", "query", ["ledger", "query", query]),
        "file": ("yaams", "query", ["query", query]),
    }
    source, command, verb_args = routes.get(kind, ("yaams", "query", ["query", query]))
    rc, raw = _call(verb_args)
    result = _source_result(source, command, rc, raw)
    return {
        "tool": "hugr",
        "command": "find",
        "kind": kind,
        "query": query,
        "limit": k,
        "source": result,
        "warnings": [] if result["ok"] else [{
            "source": source,
            "command": command,
            "exit_code": rc,
            "message": "source query failed",
        }],
    }


def inbox() -> dict[str, Any]:
    """Build the cross-tool inbox view."""
    sources: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for source, command, verb_args in (
        ("owa-mail", "list", ["mail", "list", "--unread"]),
        ("owa-cal", "events", ["cal", "events", "--today"]),
        ("ledger", "loops", ["ledger", "loops"]),
        ("yaams", "promote list", ["promote", "list"]),
    ):
        _append_source(
            sources,
            warnings,
            source=source,
            command=command,
            verb_args=verb_args,
        )
    doc = {
        "tool": "hugr",
        "command": "inbox",
        "sources": sources,
        "warnings": warnings,
    }
    sid = _session.current_session_id()
    if sid is not None and _session.read_meta(sid) is not None:
        ids = _collect_ids(sources)
        _session.write_working_set(sid, ids)
        _session.touch(sid)
    return doc


def _collect_ids(sources: list[dict[str, Any]]) -> list[Any]:
    """Pull ids/labels out of source payloads for the working set."""
    ids: list[Any] = []
    for src in sources:
        data = src.get("data")
        candidates: list[Any] = []
        if isinstance(data, list):
            candidates = data
        elif isinstance(data, dict):
            for key in ("items", "results", "loops", "events", "messages"):
                value = data.get(key)
                if isinstance(value, list):
                    candidates = value
                    break
        for item in candidates:
            if isinstance(item, dict):
                ids.append({
                    "source": src.get("source"),
                    "id": item.get("id") or item.get("uuid") or item.get("name"),
                })
            else:
                ids.append({"source": src.get("source"), "id": item})
    return ids


def remember(
    fact_text: str,
    *,
    note_type: str = "fact",
    links: Sequence[str] = (),
    yes: bool = False,
) -> dict[str, Any]:
    """Promote a one-off fact directly into the ledger layer."""
    args = ["ledger", "notes", "add", "--type", note_type]
    for link in links:
        args.extend(["--link", link])
    if yes:
        args.append("--yes")
    args.append(fact_text)
    rc, raw = _call(args)
    decoded = _decode_json(raw)
    ok = rc == 0
    if isinstance(decoded, dict) and decoded.get("ok") is False:
        ok = False
    return {
        "tool": "hugr",
        "command": "remember",
        "ok": ok,
        "exit_code": rc,
        "fact": fact_text,
        "note_type": note_type,
        "links": list(links),
        "result": decoded,
        "error": None if ok else {
            "code": "ledger_remember_failed",
            "message": "ledger note creation failed",
            "hint": "Run `hugr ledger notes --help` to inspect the ledger note commands.",
        },
    }

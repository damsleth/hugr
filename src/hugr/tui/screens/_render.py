"""Shared TUI render helpers - turn hugr.api docs into compact text."""

from __future__ import annotations

import json
from typing import Any


def render_recall_doc(doc: dict[str, Any]) -> str:
    lines: list[str] = []
    if q := doc.get("query"):
        lines.append(f"query: {q}")
    sources = doc.get("sources") or []
    for src in sources:
        mark = "+" if src.get("ok") else "x"
        label = src.get("source") or "?"
        cmd = src.get("command") or ""
        lines.append(f"  {mark} {label} {cmd}".rstrip())
    citations = doc.get("citations") or []
    if citations:
        lines.append("")
        lines.append("citations:")
        for cite in citations:
            lines.append(f"  - {cite.get('source')}: {cite.get('ref')}")
    warnings = doc.get("warnings") or []
    if warnings:
        lines.append("")
        lines.append("warnings:")
        for warn in warnings:
            lines.append(f"  - {warn.get('source')}: {warn.get('message')}")
    return "\n".join(lines) if lines else "(no result)"


def render_find_doc(doc: dict[str, Any]) -> str:
    lines: list[str] = []
    if k := doc.get("kind"):
        lines.append(f"kind: {k}")
    if q := doc.get("query"):
        lines.append(f"query: {q}")
    source = doc.get("source") or {}
    mark = "+" if source.get("ok") else "x"
    lines.append(f"  {mark} {source.get('source')} {source.get('command')}".rstrip())
    data = source.get("data")
    if isinstance(data, list):
        lines.append("")
        for idx, item in enumerate(data[:10]):
            label = _label_for(item)
            lines.append(f"  [{idx}] {label}")
    elif isinstance(data, dict):
        for key in ("items", "results", "data"):
            value = data.get(key)
            if isinstance(value, list):
                lines.append("")
                for idx, item in enumerate(value[:10]):
                    lines.append(f"  [{idx}] {_label_for(item)}")
                break
    return "\n".join(lines) if lines else "(no result)"


def render_inbox_doc(doc: dict[str, Any]) -> str:
    lines: list[str] = ["inbox"]
    for src in doc.get("sources") or []:
        mark = "+" if src.get("ok") else "x"
        label = src.get("source") or "?"
        cmd = src.get("command") or ""
        data = src.get("data")
        count = _count(data)
        lines.append(f"  {mark} {label} {cmd}  ({count} items)".rstrip())
    return "\n".join(lines)


def render_doctor_doc(doc: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"hugr doctor: {doc.get('summary', 'unknown')}")
    for finding in doc.get("findings") or []:
        sev = finding.get("severity", "info")
        msg = finding.get("message") or finding.get("id") or "?"
        lines.append(f"  [{sev}] {finding.get('tool', '?')}: {msg}")
    components = doc.get("components") or []
    if components:
        lines.append("")
        lines.append("components:")
        for c in components:
            state = c.get("state") or c.get("status") or "?"
            lines.append(f"  - {c.get('tool', '?')}: {state}")
    return "\n".join(lines) if lines else "(empty doctor report)"


def render_session_doc(doc: dict[str, Any]) -> str:
    lines: list[str] = []
    cur = doc.get("current_session_id")
    lines.append(f"current: {cur or '(none)'}")
    sessions = doc.get("sessions") or []
    if not sessions:
        lines.append("(no sessions)")
    for s in sessions:
        mark = "*" if s.get("id") == cur else "-"
        lines.append(
            f"  {mark} {s.get('id')}  last_used={s.get('last_used_at')}  ttl={s.get('ttl_seconds')}s"
        )
    return "\n".join(lines)


def render_json(doc: Any) -> str:
    try:
        return json.dumps(doc, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(doc)


def _label_for(item: Any) -> str:
    if isinstance(item, dict):
        for key in ("subject", "title", "name", "id"):
            value = item.get(key)
            if value:
                return str(value)
    return str(item)


def _count(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ("items", "results", "loops", "events", "messages"):
            value = data.get(key)
            if isinstance(value, list):
                return len(value)
    return 0

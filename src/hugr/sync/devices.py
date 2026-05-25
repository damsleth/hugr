"""Device id + recipient registry helpers."""

from __future__ import annotations

import os
import platform
import re
from pathlib import Path


_RECIPIENT_LINE_RE = re.compile(r"^(?P<key>age1[a-z0-9]+)\s*#\s*(?P<device>\S+)\s*$")


def device_id() -> str:
    """Stable per-machine identifier.

    Uses ``HUGR_DEVICE_ID`` env var when set, else ``$USER@$HOSTNAME``
    sanitised to lowercase alphanumerics + dashes.
    """
    override = os.environ.get("HUGR_DEVICE_ID")
    if override and override.strip():
        return override.strip()
    user = os.environ.get("USER") or os.environ.get("USERNAME") or "anon"
    host = platform.node() or "host"
    raw = f"{user}@{host}".lower()
    return re.sub(r"[^a-z0-9-]+", "-", raw).strip("-") or "device"


def read_recipients(path: Path) -> list[dict[str, str]]:
    """Return the list of {device, public_key} entries from a recipients file."""
    if not path.is_file():
        return []
    out: list[dict[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _RECIPIENT_LINE_RE.match(line)
        if m:
            out.append({"device": m["device"], "public_key": m["key"]})
            continue
        if line.startswith("age1"):
            out.append({"device": "?", "public_key": line.split()[0]})
    return out


def register_recipient(path: Path, device: str, public_key: str) -> None:
    """Ensure (device, public_key) is present in the recipients file.

    If an entry for the same device already exists, rewrite it with the
    new key. If the same key is registered for another device, keep
    both lines (the user can prune manually).
    """
    if not public_key:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if path.is_file():
        existing = path.read_text(encoding="utf-8").splitlines()

    new_lines: list[str] = []
    replaced = False
    for line in existing:
        m = _RECIPIENT_LINE_RE.match(line.strip())
        if m and m["device"] == device:
            new_lines.append(f"{public_key} # {device}")
            replaced = True
        else:
            new_lines.append(line.rstrip())
    if not replaced:
        new_lines.append(f"{public_key} # {device}")

    body = "\n".join(new_lines).rstrip() + "\n"
    path.write_text(body, encoding="utf-8")

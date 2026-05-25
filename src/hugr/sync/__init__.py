"""hugr.sync - cross-device state sync via age-encrypted git repo.

Plan 04.3 scope:

- ``hugr sync init <repo>`` clones the state repo, generates a per-
  device age identity, and registers the device's public key in the
  repo's recipients file.
- ``hugr sync status`` reports the device id, repo path, recipients,
  and the last commit on the repo branch.
- ``hugr sync push`` snapshots the master hugr config, encrypts it
  to all recipients, commits + pushes.
- ``hugr sync pull`` fast-forwards the local clone. Decrypting the
  pulled bundle and writing it onto the local config / DB is deferred
  to plan 04.4.

Everything is thin glue around the system ``git`` and ``age`` binaries.
If either is missing, the high-level functions return an envelope with
a clear error code; ``hugr doctor`` surfaces the missing-binary case.
"""

from __future__ import annotations

import datetime as _dt
import gzip
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hugr.config import data_root_default, master_config_path
from hugr.sync import age as age_mod
from hugr.sync import devices as devices_mod
from hugr.sync import git as git_mod


def state_repo_dir() -> Path:
    """Where the local clone of damsleth/hugr-state lives."""
    override = os.environ.get("HUGR_STATE_DIR")
    if override:
        return Path(override)
    return data_root_default() / "state"


def _now_iso() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass
class SyncEnvelope:
    """Return-shape for hugr.sync top-level functions."""

    ok: bool
    command: str
    exit_code: int
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool": "hugr",
            "command": self.command,
            "ok": self.ok,
            "exit_code": self.exit_code,
            "error": self.error,
            **self.data,
        }


def _missing_binary_envelope(command: str, missing: list[str]) -> SyncEnvelope:
    return SyncEnvelope(
        ok=False,
        command=command,
        exit_code=4,
        error={
            "code": "missing_binary",
            "message": f"missing binary on PATH: {', '.join(missing)}",
            "hint": (
                "Install with `brew install age git` (macOS) or your "
                "package manager."
            ),
        },
    )


def _prerequisites_envelope(command: str) -> SyncEnvelope | None:
    missing: list[str] = []
    if not git_mod.is_available():
        missing.append("git")
    if not age_mod.is_available():
        missing.append("age")
    if missing:
        return _missing_binary_envelope(command, missing)
    return None


def init(
    repo_url: str,
    *,
    clone_into: Path | None = None,
    identity_path: Path | None = None,
) -> SyncEnvelope:
    """Clone the state repo and register this device.

    Idempotent: if the repo is already cloned, just refreshes the
    recipient entry. If the age identity already exists, reuses it.
    """
    check = _prerequisites_envelope("sync init")
    if check is not None:
        return check

    target = clone_into or state_repo_dir()
    identity = identity_path or (target / ".age" / "identity.key")

    if not target.exists():
        rc, _ = git_mod.clone(repo_url, target)
        if rc != 0:
            return SyncEnvelope(
                ok=False,
                command="sync init",
                exit_code=2,
                error={
                    "code": "git_clone_failed",
                    "message": f"git clone {repo_url} failed (exit {rc})",
                    "hint": "Verify the repo URL and that ssh keys / tokens are set up.",
                },
                data={"repo_url": repo_url, "clone_into": str(target)},
            )

    if not identity.is_file():
        identity.parent.mkdir(parents=True, exist_ok=True)
        age_mod.generate_identity(identity)

    public_key = age_mod.public_key_from_identity(identity)
    device_id = devices_mod.device_id()
    recipients_path = target / ".age-recipients.txt"
    devices_mod.register_recipient(recipients_path, device_id, public_key)

    return SyncEnvelope(
        ok=True,
        command="sync init",
        exit_code=0,
        data={
            "repo_url": repo_url,
            "clone_into": str(target),
            "identity_path": str(identity),
            "device_id": device_id,
            "public_key": public_key,
        },
    )


def status() -> SyncEnvelope:
    """Report device, repo, recipients, last commit."""
    target = state_repo_dir()
    if not (target / ".git").is_dir():
        return SyncEnvelope(
            ok=False,
            command="sync status",
            exit_code=4,
            error={
                "code": "not_initialized",
                "message": f"no state repo at {target}",
                "hint": "Run `hugr sync init <repo-url>` first.",
            },
            data={"clone_into": str(target)},
        )

    identity = target / ".age" / "identity.key"
    public_key = (
        age_mod.public_key_from_identity(identity) if identity.is_file() else None
    )
    recipients = devices_mod.read_recipients(target / ".age-recipients.txt")
    last_commit = git_mod.last_commit(target)

    return SyncEnvelope(
        ok=True,
        command="sync status",
        exit_code=0,
        data={
            "clone_into": str(target),
            "device_id": devices_mod.device_id(),
            "public_key": public_key,
            "recipients": recipients,
            "last_commit": last_commit,
        },
    )


def _snapshot_targets() -> list[tuple[str, Path]]:
    """List of (label, source-path) pairs that ``push`` should snapshot.

    Plan 04.3a includes the master hugr config only. Tool configs and
    yaams DB snapshots land in 04.4.
    """
    targets: list[tuple[str, Path]] = []
    master = master_config_path()
    if master.is_file():
        targets.append(("master-config", master))
    return targets


def push(*, message: str | None = None) -> SyncEnvelope:
    """Snapshot opt-in state, encrypt, commit, push."""
    check = _prerequisites_envelope("sync push")
    if check is not None:
        return check

    repo = state_repo_dir()
    if not (repo / ".git").is_dir():
        return SyncEnvelope(
            ok=False,
            command="sync push",
            exit_code=4,
            error={
                "code": "not_initialized",
                "message": f"no state repo at {repo}",
                "hint": "Run `hugr sync init <repo-url>` first.",
            },
        )

    recipients = devices_mod.read_recipients(repo / ".age-recipients.txt")
    if not recipients:
        return SyncEnvelope(
            ok=False,
            command="sync push",
            exit_code=1,
            error={
                "code": "no_recipients",
                "message": "no recipients in .age-recipients.txt",
                "hint": "Run `hugr sync init` to register this device.",
            },
        )
    public_keys = [r["public_key"] for r in recipients if r.get("public_key")]

    device_dir = repo / "devices" / devices_mod.device_id()
    shared_dir = repo / "shared" / "hugr"
    device_dir.mkdir(parents=True, exist_ok=True)
    shared_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for label, source in _snapshot_targets():
        payload = gzip.compress(source.read_bytes())
        encrypted = age_mod.encrypt(payload, public_keys)
        dest = shared_dir / f"{label}.yaml.gz.age"
        dest.write_bytes(encrypted)
        written.append(str(dest.relative_to(repo)))

    meta = {
        "device_id": devices_mod.device_id(),
        "pushed_at": _now_iso(),
        "snapshots": written,
    }
    (device_dir / "last-push.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    commit_msg = message or f"sync push from {devices_mod.device_id()} @ {_now_iso()}"
    rc, stderr = git_mod.commit_all(repo, commit_msg)
    if rc != 0 and "nothing to commit" not in stderr:
        return SyncEnvelope(
            ok=False,
            command="sync push",
            exit_code=2,
            error={
                "code": "git_commit_failed",
                "message": f"git commit failed (exit {rc})",
                "hint": stderr.strip()[:200] or "see git status in the state repo",
            },
            data={"snapshots": written},
        )
    rc, stderr = git_mod.push(repo)
    if rc != 0:
        return SyncEnvelope(
            ok=False,
            command="sync push",
            exit_code=2,
            error={
                "code": "git_push_failed",
                "message": f"git push failed (exit {rc})",
                "hint": stderr.strip()[:200] or "check ssh / token access to the state repo",
            },
            data={"snapshots": written},
        )

    return SyncEnvelope(
        ok=True,
        command="sync push",
        exit_code=0,
        data={
            "snapshots": written,
            "pushed_at": meta["pushed_at"],
        },
    )


def pull() -> SyncEnvelope:
    """Fast-forward the state repo. Decryption + writeback lands in 04.4."""
    check = _prerequisites_envelope("sync pull")
    if check is not None:
        return check

    repo = state_repo_dir()
    if not (repo / ".git").is_dir():
        return SyncEnvelope(
            ok=False,
            command="sync pull",
            exit_code=4,
            error={
                "code": "not_initialized",
                "message": f"no state repo at {repo}",
                "hint": "Run `hugr sync init <repo-url>` first.",
            },
        )
    rc, stderr = git_mod.pull(repo)
    if rc != 0:
        return SyncEnvelope(
            ok=False,
            command="sync pull",
            exit_code=2,
            error={
                "code": "git_pull_failed",
                "message": f"git pull failed (exit {rc})",
                "hint": stderr.strip()[:200] or "resolve conflicts in the state repo",
            },
        )
    return SyncEnvelope(
        ok=True,
        command="sync pull",
        exit_code=0,
        data={
            "pulled_at": _now_iso(),
            "last_commit": git_mod.last_commit(repo),
            "note": "snapshot writeback is deferred to plan 04.4",
        },
    )


__all__ = [
    "SyncEnvelope",
    "state_repo_dir",
    "init",
    "status",
    "push",
    "pull",
]

"""Thin git wrappers over subprocess.

No interactive prompts; if a credential helper is needed, the user must
have it configured. Errors surface as (returncode, stderr_text) tuples.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_available() -> bool:
    return shutil.which("git") is not None


def _run(cmd: list[str], *, cwd: Path | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stderr or ""


def clone(repo_url: str, target: Path) -> tuple[int, str]:
    target.parent.mkdir(parents=True, exist_ok=True)
    return _run(["git", "clone", repo_url, str(target)])


def pull(repo: Path) -> tuple[int, str]:
    return _run(["git", "-C", str(repo), "pull", "--ff-only"])


def push(repo: Path) -> tuple[int, str]:
    return _run(["git", "-C", str(repo), "push"])


def commit_all(repo: Path, message: str) -> tuple[int, str]:
    rc, err = _run(["git", "-C", str(repo), "add", "-A"])
    if rc != 0:
        return rc, err
    return _run(["git", "-C", str(repo), "commit", "-m", message])


def last_commit(repo: Path) -> dict[str, str] | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--pretty=%H%n%an%n%ai%n%s"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    parts = proc.stdout.splitlines()
    if len(parts) < 4:
        return None
    return {"sha": parts[0], "author": parts[1], "date": parts[2], "subject": parts[3]}

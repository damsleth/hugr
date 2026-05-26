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


def pull_merge(repo: Path) -> tuple[int, str]:
    """Fetch and three-way merge the upstream branch into the current one.

    Fast-forwards when possible; otherwise git performs its recursive
    three-way merge (base = merge-base, ours = local, theirs = upstream).
    Returns nonzero with conflicts left in the worktree when the merge
    cannot auto-resolve; callers inspect :func:`unmerged_paths`.

    ``--no-rebase`` forces a merge regardless of the user's
    ``pull.rebase`` config; ``--no-edit`` keeps it non-interactive.
    """
    return _run(["git", "-C", str(repo), "pull", "--no-rebase", "--no-edit"])


def push(repo: Path) -> tuple[int, str]:
    return _run(["git", "-C", str(repo), "push"])


def unmerged_paths(repo: Path) -> list[str]:
    """Repo-relative paths left in conflict after a merge (index stage > 0)."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", "--diff-filter=U"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line for line in proc.stdout.splitlines() if line.strip()]


def read_stage(repo: Path, stage: int, rel_path: str) -> bytes | None:
    """Raw bytes of one merge stage (1=base, 2=ours, 3=theirs), or None."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f":{stage}:{rel_path}"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def resolve_with_ours(repo: Path, rel_path: str) -> tuple[int, str]:
    """Take our side of a conflicted path and stage the resolution.

    Falls back to ``--theirs`` when our side does not exist (e.g. a
    delete/modify conflict where we deleted), so the merge can complete.
    """
    rc, err = _run(["git", "-C", str(repo), "checkout", "--ours", "--", rel_path])
    if rc != 0:
        rc, err = _run(["git", "-C", str(repo), "checkout", "--theirs", "--", rel_path])
    if rc != 0:
        return rc, err
    return _run(["git", "-C", str(repo), "add", "--", rel_path])


def add_all(repo: Path) -> tuple[int, str]:
    return _run(["git", "-C", str(repo), "add", "-A"])


def commit_no_edit(repo: Path, message: str) -> tuple[int, str]:
    return _run(["git", "-C", str(repo), "commit", "--no-edit", "-m", message])


def ahead_count(repo: Path) -> int:
    """How many commits the local branch is ahead of its upstream."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--count", "@{u}..HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return 0
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return 0


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

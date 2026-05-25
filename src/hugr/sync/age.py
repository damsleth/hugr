"""Wrappers for the ``age`` binary (filippo.io/age).

We never bundle a Python re-implementation; the contract is "if the
user has ``age`` on PATH, hugr sync works". Otherwise ``is_available()``
returns False and the high-level sync functions surface a clear error.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def is_available() -> bool:
    return shutil.which("age") is not None and shutil.which("age-keygen") is not None


def generate_identity(target: Path) -> None:
    """Generate a new age keypair at *target* (mode 0600).

    The file is the age identity format; ``public_key_from_identity``
    reads the public key back from it.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["age-keygen", "-o", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"age-keygen failed: {proc.stderr.strip()}")
    target.chmod(0o600)


def public_key_from_identity(identity_path: Path) -> str | None:
    if not identity_path.is_file():
        return None
    for line in identity_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("# public key: "):
            return line.removeprefix("# public key: ").strip()
    # Some age-keygen versions write the public key as the first non-comment line.
    for line in identity_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("age1"):
            return line
    return None


def encrypt(data: bytes, recipients: list[str]) -> bytes:
    if not recipients:
        raise ValueError("encrypt requires at least one recipient")
    cmd: list[str] = ["age"]
    for r in recipients:
        cmd.extend(["-r", r])
    proc = subprocess.run(cmd, input=data, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"age encrypt failed: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout


def decrypt(data: bytes, identity_path: Path) -> bytes:
    proc = subprocess.run(
        ["age", "--decrypt", "-i", str(identity_path)],
        input=data,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"age decrypt failed: {proc.stderr.decode('utf-8', 'replace').strip()}")
    return proc.stdout

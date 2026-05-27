"""Tests for plan 04.3a `hugr sync`.

We don't depend on the real ``age`` binary or a remote git server; both
are stubbed where needed. One integration-shaped test uses a real local
bare git repo to exercise clone/commit/push, but it skips when neither
``git`` nor ``age`` is on PATH.
"""

from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from click.testing import CliRunner

from hugr import sync as sync_mod
from hugr.cli import cli
from hugr.sync import age as age_mod
from hugr.sync import devices as devices_mod
from hugr.sync import git as git_mod


def _isolate(tmp_path: Path, monkeypatch) -> Path:
  monkeypatch.setenv("HUGR_HOME", str(tmp_path / "hugr-home"))
  monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
  monkeypatch.setenv("HUGR_DEVICE_ID", "test-device")
  state = tmp_path / "state"
  monkeypatch.setenv("HUGR_STATE_DIR", str(state))
  return state


def test_device_id_honors_override(monkeypatch):
  monkeypatch.setenv("HUGR_DEVICE_ID", "alpha")
  assert devices_mod.device_id() == "alpha"


def test_register_recipient_replaces_same_device(tmp_path: Path):
  path = tmp_path / "recipients.txt"
  devices_mod.register_recipient(path, "laptop", "age1xxx")
  devices_mod.register_recipient(path, "laptop", "age1yyy")
  rows = devices_mod.read_recipients(path)
  assert len(rows) == 1
  assert rows[0]["public_key"] == "age1yyy"


def test_register_recipient_appends_other_device(tmp_path: Path):
  path = tmp_path / "recipients.txt"
  devices_mod.register_recipient(path, "laptop", "age1xxx")
  devices_mod.register_recipient(path, "phone", "age1zzz")
  rows = devices_mod.read_recipients(path)
  devices = sorted(r["device"] for r in rows)
  assert devices == ["laptop", "phone"]


def test_status_reports_not_initialized(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  envelope = sync_mod.status()
  assert envelope.ok is False
  assert envelope.error["code"] == "not_initialized"


def test_push_pull_init_require_git_and_age(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  monkeypatch.setattr(git_mod, "is_available", lambda: False)
  monkeypatch.setattr(age_mod, "is_available", lambda: False)

  env = sync_mod.init("git@example.com:repo.git")
  assert env.ok is False
  assert env.error["code"] == "missing_binary"
  assert "git" in env.error["message"] and "age" in env.error["message"]


@pytest.fixture
def fake_age(monkeypatch):
  """Replace the age helpers with pure-Python stand-ins.

  - generate_identity writes "AGE-IDENTITY: <hex>\\n# public key: age1<hex>"
  - public_key_from_identity reads the # public key: line
  - encrypt prepends a magic header so we can verify it was called
  - decrypt strips the header
  """

  def gen(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
      "AGE-IDENTITY: AGE-SECRET-KEY-TESTONLY\n"
      "# public key: age1testkeyabcdef\n"
    )
    path.write_text(body, encoding="utf-8")
    path.chmod(0o600)

  monkeypatch.setattr(age_mod, "is_available", lambda: True)
  monkeypatch.setattr(age_mod, "generate_identity", gen)
  monkeypatch.setattr(
    age_mod, "encrypt", lambda data, recipients: b"AGE-FAKE\n" + data
  )
  monkeypatch.setattr(
    age_mod, "decrypt", lambda data, identity: data.removeprefix(b"AGE-FAKE\n")
  )


def _init_bare_upstream(path: Path) -> None:
  subprocess.run(
    ["git", "init", "--bare", str(path)],
    capture_output=True,
    check=True,
  )


def _git_available() -> bool:
  return git_mod.is_available()


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_init_clones_and_registers_recipient(tmp_path: Path, monkeypatch, fake_age):
  state = _isolate(tmp_path, monkeypatch)
  bare = tmp_path / "upstream.git"
  _init_bare_upstream(bare)
  # The bare repo is empty; init's clone will produce an empty working tree.

  envelope = sync_mod.init(str(bare))
  assert envelope.ok is True, envelope.as_dict()
  assert envelope.data["device_id"] == "test-device"
  assert envelope.data["public_key"] == "age1testkeyabcdef"

  recipients_file = state / ".age-recipients.txt"
  rows = devices_mod.read_recipients(recipients_file)
  assert rows == [{"device": "test-device", "public_key": "age1testkeyabcdef"}]


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_push_writes_encrypted_master_config(tmp_path: Path, monkeypatch, fake_age):
  state = _isolate(tmp_path, monkeypatch)
  bare = tmp_path / "upstream.git"
  _init_bare_upstream(bare)

  # Seed a master config so _snapshot_targets() finds it
  cfg = Path(os.environ["XDG_CONFIG_HOME"]) / "hugr" / "config.toml"
  cfg.parent.mkdir(parents=True)
  cfg.write_text("version = 1\n")

  # Identify git author for the commit
  monkeypatch.setenv("GIT_AUTHOR_NAME", "T")
  monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.com")
  monkeypatch.setenv("GIT_COMMITTER_NAME", "T")
  monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.com")

  sync_mod.init(str(bare))
  envelope = sync_mod.push()
  assert envelope.ok is True, envelope.as_dict()

  snapshot = state / "shared" / "hugr" / "master-config.yaml.gz.age"
  assert snapshot.is_file()
  blob = snapshot.read_bytes()
  assert blob.startswith(b"AGE-FAKE\n")
  decoded = gzip.decompress(blob.removeprefix(b"AGE-FAKE\n"))
  assert decoded == b"version = 1\n"


def _tracked_files(repo: Path) -> list[str]:
  out = subprocess.run(
    ["git", "-C", str(repo), "ls-files"],
    capture_output=True,
    text=True,
    check=True,
  )
  return [line for line in out.stdout.splitlines() if line.strip()]


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_init_gitignores_private_identity(tmp_path: Path, monkeypatch, fake_age):
  state = _isolate(tmp_path, monkeypatch)
  bare = tmp_path / "upstream.git"
  _init_bare_upstream(bare)

  envelope = sync_mod.init(str(bare))
  assert envelope.ok is True, envelope.as_dict()

  gitignore = state / ".gitignore"
  assert gitignore.is_file()
  assert ".age/" in gitignore.read_text(encoding="utf-8").splitlines()
  # The identity exists on disk but git treats it as ignored.
  assert (state / ".age" / "identity.key").is_file()
  ignored = subprocess.run(
    ["git", "-C", str(state), "check-ignore", ".age/identity.key"],
    capture_output=True,
    text=True,
    check=False,
  )
  assert ignored.returncode == 0


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_push_never_tracks_private_identity(tmp_path: Path, monkeypatch, fake_age):
  _set_git_identity(monkeypatch)
  state = _isolate(tmp_path, monkeypatch)
  bare = tmp_path / "upstream.git"
  _init_bare_upstream(bare)

  cfg = Path(os.environ["XDG_CONFIG_HOME"]) / "hugr" / "config.toml"
  cfg.parent.mkdir(parents=True)
  cfg.write_text("version = 1\n")

  sync_mod.init(str(bare))
  envelope = sync_mod.push()
  assert envelope.ok is True, envelope.as_dict()

  tracked = _tracked_files(state)
  assert ".age/identity.key" not in tracked
  assert not any(t.startswith(".age/") for t in tracked)


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_push_untracks_previously_committed_identity(tmp_path: Path, monkeypatch, fake_age):
  """A repo where a buggy older push committed the key gets it scrubbed."""
  _set_git_identity(monkeypatch)
  state = _isolate(tmp_path, monkeypatch)
  bare = tmp_path / "upstream.git"
  _init_bare_upstream(bare)

  cfg = Path(os.environ["XDG_CONFIG_HOME"]) / "hugr" / "config.toml"
  cfg.parent.mkdir(parents=True)
  cfg.write_text("version = 1\n")

  sync_mod.init(str(bare))

  # Simulate the legacy bug: force-add the identity behind .gitignore.
  subprocess.run(
    ["git", "-C", str(state), "add", "-f", ".age/identity.key"],
    capture_output=True,
    check=True,
  )
  subprocess.run(
    ["git", "-C", str(state), "commit", "-m", "leak"],
    capture_output=True,
    check=True,
  )
  assert ".age/identity.key" in _tracked_files(state)

  envelope = sync_mod.push()
  assert envelope.ok is True, envelope.as_dict()
  assert ".age/identity.key" not in _tracked_files(state)


def test_cli_sync_status_returns_4_without_repo(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  result = CliRunner().invoke(cli, ["sync", "status", "--json"])
  assert result.exit_code == 4
  payload = json.loads(result.output)
  assert payload["error"]["code"] == "not_initialized"


def test_cli_sync_push_requires_yes_in_json_mode(tmp_path: Path, monkeypatch):
  _isolate(tmp_path, monkeypatch)
  result = CliRunner().invoke(cli, ["sync", "push", "--json"])
  assert result.exit_code == 1
  payload = json.loads(result.output)
  assert payload["error"]["code"] == "confirmation_required"


# --- three-way merge on pull (ledger sync conflicts) ----------------------


def _set_git_identity(monkeypatch) -> None:
  for key, val in {
    "GIT_AUTHOR_NAME": "T",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "T",
    "GIT_COMMITTER_EMAIL": "t@example.com",
  }.items():
    monkeypatch.setenv(key, val)


def _git(cwd: Path, *args: str) -> None:
  subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, check=True)


def _seed_upstream(tmp_path: Path, files: dict[str, str]) -> tuple[Path, Path]:
  """A bare repo seeded on `main`, plus a peer clone that authored the seed."""
  bare = tmp_path / "upstream.git"
  subprocess.run(["git", "init", "--bare", str(bare)], capture_output=True, check=True)
  subprocess.run(
    ["git", "-C", str(bare), "symbolic-ref", "HEAD", "refs/heads/main"],
    capture_output=True,
    check=True,
  )
  peer = tmp_path / "peer"
  subprocess.run(["git", "clone", str(bare), str(peer)], capture_output=True, check=True)
  _peer_commit(peer, files, message="seed")
  _git(peer, "push", "-u", "origin", "main")
  return bare, peer


def _peer_commit(peer: Path, files: dict[str, str], *, message: str) -> None:
  for rel, content in files.items():
    p = peer / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
  _git(peer, "add", "-A")
  _git(peer, "commit", "-m", message)


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_pull_three_way_merges_nonconflicting_changes(tmp_path, monkeypatch, fake_age):
  _set_git_identity(monkeypatch)
  state = _isolate(tmp_path, monkeypatch)
  bare, peer = _seed_upstream(tmp_path, {"base.txt": "base\n"})

  assert sync_mod.init(str(bare)).ok is True

  # A different device pushes a change to a different file.
  _peer_commit(peer, {"fromB.txt": "B\n"}, message="peer change")
  _git(peer, "push")

  # This device commits a non-overlapping local change, then pulls.
  (state / "fromA.txt").write_text("A\n", encoding="utf-8")
  git_mod.commit_all(state, "local A change")

  env = sync_mod.pull()
  assert env.exit_code == 0, env.as_dict()
  assert env.data["conflicts"] == []
  assert (state / "fromA.txt").is_file()
  assert (state / "fromB.txt").is_file()  # merged in from upstream
  assert env.data["pushed"] is True  # merge commit propagated back


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_pull_conflict_keeps_ours_and_saves_theirs(tmp_path, monkeypatch, fake_age):
  _set_git_identity(monkeypatch)
  state = _isolate(tmp_path, monkeypatch)
  bare, peer = _seed_upstream(tmp_path, {"shared/note.md": "base\n"})

  assert sync_mod.init(str(bare)).ok is True

  # Both devices edit the same note off the same base => real conflict.
  _peer_commit(peer, {"shared/note.md": "from peer\n"}, message="peer note")
  _git(peer, "push")

  (state / "shared" / "note.md").write_text("from A\n", encoding="utf-8")
  git_mod.commit_all(state, "local note change")

  env = sync_mod.pull()
  assert env.exit_code == 5, env.as_dict()  # partial success: needs review

  # Our side is the committed version; theirs is preserved in a sidecar.
  assert (state / "shared" / "note.md").read_text(encoding="utf-8") == "from A\n"
  conflicts = env.data["conflicts"]
  assert len(conflicts) == 1
  assert conflicts[0]["path"] == "shared/note.md"
  sidecar = state / conflicts[0]["saved_theirs_to"]
  assert sidecar.is_file()
  assert sidecar.read_text(encoding="utf-8") == "from peer\n"
  assert "test-device" in conflicts[0]["saved_theirs_to"]


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_pull_clean_fast_forward_does_not_push(tmp_path, monkeypatch, fake_age):
  _set_git_identity(monkeypatch)
  state = _isolate(tmp_path, monkeypatch)
  bare, peer = _seed_upstream(tmp_path, {"base.txt": "base\n"})

  assert sync_mod.init(str(bare)).ok is True

  # Upstream advances; this device has no local commits => fast-forward.
  _peer_commit(peer, {"fromB.txt": "B\n"}, message="peer change")
  _git(peer, "push")

  env = sync_mod.pull()
  assert env.exit_code == 0, env.as_dict()
  assert env.data["conflicts"] == []
  assert env.data["pushed"] is False  # nothing local to send back
  assert (state / "fromB.txt").is_file()

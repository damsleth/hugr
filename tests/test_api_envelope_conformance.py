"""Envelope conformance tests for action-class mnem.api wrappers.

CONVENTIONS.md invariant: ok <=> exit_code == 0.

These tests mock the subprocess layer so no real tools need to be
installed.  They exercise the _passthrough.call() path and assert that
when the underlying tool returns exit_code 0 with ok=true, the API
propagates that correctly, and vice-versa for failures.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import mnem.api as api
import mnem.api._passthrough as pt


def _make_ok_envelope(command: str = "ingest") -> bytes:
    """Minimal conformant action envelope, ok=true."""
    return json.dumps({
        "tool": "yaams",
        "version": "0.1.3",
        "command": command,
        "ok": True,
        "duration_ms": 1.0,
        "stats": {},
        "warnings": [],
        "error": None,
    }).encode()


def _make_fail_envelope(command: str = "ingest") -> bytes:
    """Minimal conformant action envelope, ok=false."""
    return json.dumps({
        "tool": "yaams",
        "version": "0.1.3",
        "command": command,
        "ok": False,
        "duration_ms": 1.0,
        "stats": {},
        "warnings": [],
        "error": {"code": "test_error", "message": "synthetic failure", "hint": None},
    }).encode()


def _patch_capture(returncode: int, stdout_bytes: bytes, stderr: str = ""):
    """Patch _capture_subprocess to return fixed values."""
    return patch.object(
        pt,
        "_capture_subprocess",
        return_value=(returncode, stdout_bytes, stderr),
    )


class TestYaamsIngestEnvelope:
    def test_ok_exit_matches_ok_true(self):
        with _patch_capture(0, _make_ok_envelope()):
            rc, stdout = api.yaams_ingest([])
        assert rc == 0
        doc = json.loads(stdout)
        assert doc["ok"] is True
        assert (rc == 0) == doc["ok"]

    def test_nonzero_exit_matches_ok_false(self):
        with _patch_capture(1, _make_fail_envelope()):
            rc, stdout = api.yaams_ingest([])
        assert rc != 0
        doc = json.loads(stdout)
        assert doc["ok"] is False
        assert (rc == 0) == doc["ok"]


class TestYaamsPromoteGenerate:
    def test_ok_envelope_conformance(self):
        with _patch_capture(0, _make_ok_envelope("promote generate")):
            rc, stdout = api.yaams_promote_generate([])
        doc = json.loads(stdout)
        assert (rc == 0) == doc["ok"]

    def test_fail_envelope_conformance(self):
        with _patch_capture(2, _make_fail_envelope("promote generate")):
            rc, stdout = api.yaams_promote_generate([])
        doc = json.loads(stdout)
        assert (rc == 0) == doc["ok"]


class TestOwaMail:
    def _make_mail_ok(self) -> bytes:
        return json.dumps({
            "tool": "owa-mail",
            "version": "0.1.2",
            "command": "send",
            "ok": True,
            "duration_ms": 5.0,
            "stats": {},
            "warnings": [],
            "error": None,
        }).encode()

    def _make_mail_fail(self) -> bytes:
        return json.dumps({
            "tool": "owa-mail",
            "version": "0.1.2",
            "command": "send",
            "ok": False,
            "duration_ms": 0.0,
            "stats": {},
            "warnings": [],
            "error": {"code": "auth_expired", "message": "token expired", "hint": "mnem auth reseed"},
        }).encode()

    def test_success_conformance(self):
        with _patch_capture(0, self._make_mail_ok()):
            rc, stdout = api.owa_mail(["send"])
        doc = json.loads(stdout)
        assert (rc == 0) == doc["ok"]

    def test_failure_conformance(self):
        with _patch_capture(3, self._make_mail_fail()):
            rc, stdout = api.owa_mail(["send"])
        doc = json.loads(stdout)
        assert (rc == 0) == doc["ok"]


class TestUnknownVerbReturnsOne:
    def test_unknown_verb_returns_exit_1_empty_bytes(self):
        rc, stdout = pt.call(["this-verb-does-not-exist"])
        assert rc == 1
        assert stdout == b""


class TestInteractiveVerbRaisesValueError:
    def test_promote_review_raises(self):
        import pytest
        with pytest.raises(ValueError, match="interactive"):
            pt.call(["promote", "review"])

    def test_auth_setup_raises(self):
        import pytest
        with pytest.raises(ValueError, match="interactive"):
            pt.call(["auth", "setup"])

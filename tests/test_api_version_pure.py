"""Tests for mnem.api.version() purity and CLI output equivalence.

- mnem.api.version() returns a dict; no stdout side-effects.
- The Click CLI command (mnem version --json) still emits identical JSON.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch

from mnem.commands.version import run as version_cli_run
from mnem.failure import SubprocessResult
import mnem.api as api


def _stub_run_subprocess(argv, *, tool, inject_json=True, extra_env=None):
    """Deterministic stub: every binary looks installed at v0.0.0."""
    return SubprocessResult(
        argv=argv,
        returncode=0,
        stdout=json.dumps({"tool": tool, "version": "0.0.0", "findings": []}),
        stderr="",
        stdout_envelope={"tool": tool, "version": "0.0.0", "findings": []},
        crashed=False,
    )


class TestApiVersionReturnShape:
    def test_returns_dict(self):
        with patch("mnem.commands.version.run_subprocess", side_effect=_stub_run_subprocess):
            result = api.version()
        assert isinstance(result, dict)

    def test_dict_has_required_keys(self):
        with patch("mnem.commands.version.run_subprocess", side_effect=_stub_run_subprocess):
            doc = api.version()
        assert "tool" in doc
        assert "version" in doc
        assert "components" in doc
        assert "packages" in doc
        assert doc["tool"] == "mnem"

    def test_no_ok_key_at_top_level(self):
        """Data commands must not have a top-level 'ok' key (CONVENTIONS.md)."""
        with patch("mnem.commands.version.run_subprocess", side_effect=_stub_run_subprocess):
            doc = api.version()
        assert "ok" not in doc

    def test_no_stdout_side_effects(self, capsys):
        with patch("mnem.commands.version.run_subprocess", side_effect=_stub_run_subprocess):
            api.version()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_components_is_dict(self):
        with patch("mnem.commands.version.run_subprocess", side_effect=_stub_run_subprocess):
            doc = api.version()
        assert isinstance(doc["components"], dict)

    def test_packages_is_dict(self):
        with patch("mnem.commands.version.run_subprocess", side_effect=_stub_run_subprocess):
            doc = api.version()
        assert isinstance(doc["packages"], dict)


class TestCliAndApiOutputEquivalence:
    def test_json_output_matches_api_dict(self):
        """CLI run(as_json=True) must emit the same dict that api.version() returns."""
        with patch("mnem.commands.version.run_subprocess", side_effect=_stub_run_subprocess):
            doc_api = api.version()
            buf = io.StringIO()
            version_cli_run(as_json=True, stream=buf)
            doc_cli = json.loads(buf.getvalue())
        assert doc_api == doc_cli

"""Tests for hugr.api.doctor() purity and CLI output equivalence.

- hugr.api.doctor() returns a dict and an int; no stdout side-effects.
- The Click CLI command (hugr doctor --json) still emits identical JSON.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch

from hugr.commands.doctor import _probe, run as doctor_cli_run
import hugr.api as api


def _stub_probe(binary: str) -> dict:
    """Deterministic stub so tests don't need real tool installs."""
    return {
        "tool": binary,
        "version": "0.0.0",
        "installed": True,
        "exit_code": 0,
        "findings": [],
    }


class TestApiDoctorReturnShape:
    def test_returns_tuple_of_dict_and_int(self):
        with patch("hugr.commands.doctor._probe", side_effect=_stub_probe):
            result = api.doctor()
        assert isinstance(result, tuple)
        assert len(result) == 2
        doc, exit_code = result
        assert isinstance(doc, dict)
        assert isinstance(exit_code, int)

    def test_dict_has_required_keys(self):
        with patch("hugr.commands.doctor._probe", side_effect=_stub_probe):
            doc, _ = api.doctor()
        assert "tool" in doc
        assert "version" in doc
        assert "components" in doc
        assert doc["tool"] == "hugr"

    def test_exit_code_is_zero_when_all_ok(self):
        with patch("hugr.commands.doctor._probe", side_effect=_stub_probe):
            _, exit_code = api.doctor()
        assert exit_code == 0

    def test_exit_code_nonzero_when_error_finding(self):
        def _erroring_probe(binary: str) -> dict:
            return {
                "tool": binary,
                "version": "0.0.0",
                "installed": True,
                "exit_code": 1,
                "findings": [
                    {"id": "test_err", "severity": "error", "message": "bad", "hint": None}
                ],
            }
        with patch("hugr.commands.doctor._probe", side_effect=_erroring_probe):
            _, exit_code = api.doctor()
        assert exit_code != 0

    def test_no_stdout_side_effects(self, capsys):
        with patch("hugr.commands.doctor._probe", side_effect=_stub_probe):
            api.doctor()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestCliAndApiOutputEquivalence:
    def test_json_output_matches_api_dict(self):
        """CLI run(as_json=True) must emit the same dict that api.doctor() returns."""
        with patch("hugr.commands.doctor._probe", side_effect=_stub_probe):
            doc_api, _ = api.doctor()
            buf = io.StringIO()
            doctor_cli_run(as_json=True, stream=buf)
            doc_cli = json.loads(buf.getvalue())
        assert doc_api == doc_cli

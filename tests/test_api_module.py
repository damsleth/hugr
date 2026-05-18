"""Tests for the hugr.api public surface.

Every exported symbol must be callable and have a return annotation
(type hint).  This pins the public surface contract so new verbs can't
be added without annotations.
"""

from __future__ import annotations

import inspect
import typing

import hugr.api as api


_EXPECTED_SYMBOLS = [
    "doctor",
    "version",
    "recall",
    "find",
    "inbox",
    "remember",
    "yaams_query",
    "yaams_ingest",
    "yaams_promote_generate",
    "yaams_promote_list",
    "ledger_init",
    "ledger_paths",
    "ledger_query",
    "ledger_loops",
    "ledger_notes",
    "ledger_context",
    "ledger_context_build",
    "ledger_context_profiles",
    "owa_piggy",
    "owa_cal",
    "owa_mail",
    "owa_graph",
    "owa_people",
    "owa_sched",
    "owa_drive",
]


def test_all_expected_symbols_exported():
    for name in _EXPECTED_SYMBOLS:
        assert hasattr(api, name), f"hugr.api missing exported symbol: {name}"


def test_all_symbols_callable():
    for name in _EXPECTED_SYMBOLS:
        obj = getattr(api, name)
        assert callable(obj), f"hugr.api.{name} is not callable"


def test_all_symbols_have_return_annotation():
    for name in _EXPECTED_SYMBOLS:
        obj = getattr(api, name)
        hints = typing.get_type_hints(obj)
        assert "return" in hints, (
            f"hugr.api.{name} has no return type annotation"
        )


def test_all_in_dunder_all():
    """Every expected symbol appears in __all__."""
    assert hasattr(api, "__all__")
    for name in _EXPECTED_SYMBOLS:
        assert name in api.__all__, f"{name} missing from hugr.api.__all__"


def test_passthrough_wrappers_accept_list_arg():
    """Passthrough wrappers take a single list[str] positional argument."""
    non_passthrough = {"doctor", "version", "recall", "find", "inbox", "remember"}
    passthrough_names = [n for n in _EXPECTED_SYMBOLS if n not in non_passthrough]
    for name in passthrough_names:
        obj = getattr(api, name)
        sig = inspect.signature(obj)
        params = list(sig.parameters.values())
        assert len(params) == 1, (
            f"hugr.api.{name} should have exactly one parameter (args: list[str]); "
            f"got {len(params)}"
        )
        assert params[0].name == "args", (
            f"hugr.api.{name} first param should be named 'args'; "
            f"got '{params[0].name}'"
        )

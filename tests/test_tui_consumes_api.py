"""Static import-boundary check: tui/ modules must only import from hugr.api.

Enforces the "surfaces share api" rule from the 03-interactive-surfaces plan:
- hugr.tui must NOT import from hugr.router
- hugr.tui must NOT import from hugr.commands.passthrough

Uses ast.parse + a visitor to walk every Python file under src/hugr/tui/.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


_SRC_ROOT = Path(__file__).parent.parent / "src" / "hugr"
_TUI_ROOT = _SRC_ROOT / "tui"
_WEB_ROOT = _SRC_ROOT / "web"

_FORBIDDEN_PREFIXES = (
  "hugr.router",
  "hugr.commands.passthrough",
)


def _collect_imports(tree: ast.AST) -> list[str]:
  """Return all module names referenced by import statements in tree."""
  names: list[str] = []
  for node in ast.walk(tree):
    if isinstance(node, ast.Import):
      for alias in node.names:
        names.append(alias.name)
    elif isinstance(node, ast.ImportFrom):
      if node.module:
        names.append(node.module)
  return names


def _tui_py_files() -> list[Path]:
  return sorted(_TUI_ROOT.rglob("*.py"))


def test_tui_root_exists() -> None:
  assert _TUI_ROOT.exists(), f"src/hugr/tui/ does not exist at {_TUI_ROOT}"


def test_tui_does_not_import_router() -> None:
  """No tui module imports hugr.router directly."""
  violations: list[str] = []
  for path in _tui_py_files():
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for name in _collect_imports(tree):
      if name.startswith("hugr.router"):
        violations.append(f"{path.relative_to(_TUI_ROOT.parent.parent.parent)}: imports {name!r}")
  assert not violations, (
    "tui modules must not import hugr.router directly; use hugr.api instead.\n"
    + "\n".join(violations)
  )


def test_tui_does_not_import_passthrough() -> None:
  """No tui module imports hugr.commands.passthrough directly."""
  violations: list[str] = []
  for path in _tui_py_files():
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for name in _collect_imports(tree):
      if name.startswith("hugr.commands.passthrough"):
        violations.append(f"{path.relative_to(_TUI_ROOT.parent.parent.parent)}: imports {name!r}")
  assert not violations, (
    "tui modules must not import hugr.commands.passthrough; use hugr.api instead.\n"
    + "\n".join(violations)
  )


def test_tui_files_found() -> None:
  """At least the expected 03.1 scaffold files are present."""
  expected = [
    _TUI_ROOT / "__init__.py",
    _TUI_ROOT / "app.py",
    _TUI_ROOT / "screens" / "__init__.py",
    _TUI_ROOT / "screens" / "ask.py",
    _TUI_ROOT / "widgets" / "__init__.py",
  ]
  for path in expected:
    assert path.exists(), f"Expected TUI file missing: {path}"


def test_web_does_not_import_router_or_passthrough() -> None:
  if not _WEB_ROOT.exists():
    pytest.skip("web surface not present")
  violations: list[str] = []
  for path in sorted(_WEB_ROOT.rglob("*.py")):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    for name in _collect_imports(tree):
      if name.startswith(_FORBIDDEN_PREFIXES):
        violations.append(f"{path.relative_to(_SRC_ROOT.parent)}: imports {name!r}")
  assert not violations, (
    "web modules must not import hugr.router or hugr.commands.passthrough; "
    "use hugr.api instead.\n" + "\n".join(violations)
  )

"""Web surface for hugr.

Requires the [web] extra. Importing this package is safe without FastAPI;
dependencies are imported lazily by ``hugr.web.app``.
"""

from __future__ import annotations

__all__ = ["create_app"]


def create_app():
  from hugr.web.app import create_app as _create_app
  return _create_app()

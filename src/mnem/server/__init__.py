"""Server runtime for mnem."""

from __future__ import annotations

__all__ = ["launch"]


def launch(*, host: str = "127.0.0.1", port: int = 7777, mcp: bool = False, insecure: bool = False) -> None:
  from mnem.server.app import launch as _launch
  _launch(host=host, port=port, mcp=mcp, insecure=insecure)

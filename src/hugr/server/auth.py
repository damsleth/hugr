"""Bind/auth guardrails for ``hugr server``."""

from __future__ import annotations

import os


AUTH_PROXY_VALUES = {"cloudflare", "tailscale", "none"}


def is_loopback(host: str) -> bool:
  return host in {"127.0.0.1", "localhost", "::1"}


def auth_proxy_from_env() -> str | None:
  value = os.environ.get("HUGR_AUTH_PROXY")
  if not value:
    return None
  normalized = value.strip().lower()
  return normalized if normalized in AUTH_PROXY_VALUES else None


def can_bind(host: str, *, insecure: bool = False) -> bool:
  if is_loopback(host):
    return True
  if insecure:
    return True
  return auth_proxy_from_env() is not None


def bind_refusal_message(host: str) -> str:
  return (
    f"refusing to bind {host}: non-loopback hugr server requires "
    "--insecure or HUGR_AUTH_PROXY=cloudflare|tailscale|none"
  )

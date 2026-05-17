from __future__ import annotations

from click.testing import CliRunner

from mnem.cli import cli
from mnem.server.auth import auth_proxy_from_env, can_bind, is_loopback


def test_loopback_hosts_allowed():
  assert is_loopback("127.0.0.1") is True
  assert is_loopback("localhost") is True
  assert can_bind("127.0.0.1") is True


def test_non_loopback_requires_guard(monkeypatch):
  monkeypatch.delenv("MNEM_AUTH_PROXY", raising=False)
  assert can_bind("0.0.0.0") is False
  assert can_bind("0.0.0.0", insecure=True) is True


def test_auth_proxy_env_allows_non_loopback(monkeypatch):
  monkeypatch.setenv("MNEM_AUTH_PROXY", "cloudflare")
  assert auth_proxy_from_env() == "cloudflare"
  assert can_bind("0.0.0.0") is True


def test_unknown_auth_proxy_does_not_allow_bind(monkeypatch):
  monkeypatch.setenv("MNEM_AUTH_PROXY", "unknown")
  assert auth_proxy_from_env() is None
  assert can_bind("0.0.0.0") is False


def test_server_refuses_non_loopback_without_guard(monkeypatch):
  monkeypatch.delenv("MNEM_AUTH_PROXY", raising=False)
  result = CliRunner().invoke(cli, ["server", "--host", "0.0.0.0"])
  assert result.exit_code == 3
  assert "refusing to bind" in result.output


def test_server_without_extra_fails_cleanly_on_loopback():
  result = CliRunner().invoke(cli, ["server"])
  assert result.exit_code == 4
  assert "server extra not installed" in result.output

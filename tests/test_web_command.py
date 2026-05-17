from __future__ import annotations

from click.testing import CliRunner

from mnem.cli import cli


def test_web_without_extra_fails_cleanly():
  result = CliRunner().invoke(cli, ["web"])
  assert result.exit_code == 4
  assert "web extra not installed" in result.output


def test_web_refuses_non_loopback_without_public():
  result = CliRunner().invoke(cli, ["web", "--host", "0.0.0.0"])
  assert result.exit_code == 3
  assert "refusing non-loopback" in result.output


def test_web_public_requires_token(monkeypatch):
  monkeypatch.delenv("MNEM_WEB_TOKEN", raising=False)
  result = CliRunner().invoke(cli, ["web", "--host", "0.0.0.0", "--public"])
  assert result.exit_code == 3
  assert "MNEM_WEB_TOKEN" in result.output

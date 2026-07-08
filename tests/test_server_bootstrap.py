"""Offline tests for server startup: transport security and the main() entry point."""

from __future__ import annotations

from unittest.mock import MagicMock

from pure_mpg_mcp import server


def test_transport_security_disabled_without_hosts(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    settings = server._transport_security()
    assert settings.enable_dns_rebinding_protection is False


def test_transport_security_allows_configured_hosts(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "mcp.example.org")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "app.onrender.com")
    settings = server._transport_security()
    assert "mcp.example.org" in settings.allowed_hosts
    assert "app.onrender.com:*" in settings.allowed_hosts
    assert "https://mcp.example.org" in settings.allowed_origins


def test_main_selects_transport(monkeypatch):
    run = MagicMock()
    monkeypatch.setattr(server.mcp, "run", run)
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("PORT", "9999")
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    server.main()
    run.assert_called_once_with(transport="streamable-http")
    assert server.mcp.settings.port == 9999

    run.reset_mock()
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    server.main()
    run.assert_called_once_with()

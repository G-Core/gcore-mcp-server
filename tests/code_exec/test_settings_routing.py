"""Tests for ``settings.get_routing_mode`` — environment-driven routing selection."""

from __future__ import annotations

import logging

import pytest

from gcore_mcp_server.config.settings import (
    ROUTING_CODE_EXEC,
    ROUTING_DIRECT,
    ROUTING_ENV_VAR,
    get_routing_mode,
)


def test_get_routing_mode_default(monkeypatch: pytest.MonkeyPatch):
    """Unset ``GCORE_MCP_ROUTING`` defaults to ``code_exec``."""
    monkeypatch.delenv(ROUTING_ENV_VAR, raising=False)
    assert get_routing_mode() == ROUTING_CODE_EXEC


def test_get_routing_mode_explicit_code_exec(monkeypatch: pytest.MonkeyPatch):
    """``GCORE_MCP_ROUTING=code_exec`` selects ``code_exec``."""
    monkeypatch.setenv(ROUTING_ENV_VAR, "code_exec")
    assert get_routing_mode() == ROUTING_CODE_EXEC


def test_get_routing_mode_explicit_direct(monkeypatch: pytest.MonkeyPatch):
    """``GCORE_MCP_ROUTING=direct`` selects ``direct``."""
    monkeypatch.setenv(ROUTING_ENV_VAR, "direct")
    assert get_routing_mode() == ROUTING_DIRECT


def test_get_routing_mode_case_insensitive(monkeypatch: pytest.MonkeyPatch):
    """Routing mode normalization is case-insensitive."""
    monkeypatch.setenv(ROUTING_ENV_VAR, "CODE_EXEC")
    assert get_routing_mode() == ROUTING_CODE_EXEC

    monkeypatch.setenv(ROUTING_ENV_VAR, "Direct")
    assert get_routing_mode() == ROUTING_DIRECT


def test_get_routing_mode_unknown_falls_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    """Unknown values fall back to ``code_exec`` with a warning log entry."""
    monkeypatch.setenv(ROUTING_ENV_VAR, "bogus")
    with caplog.at_level(logging.WARNING, logger="gcore_mcp_server.config.settings"):
        assert get_routing_mode() == ROUTING_CODE_EXEC

    # The warning mentions both the env var name and the bad value.
    warning_text = " ".join(rec.getMessage() for rec in caplog.records)
    assert ROUTING_ENV_VAR in warning_text
    assert "bogus" in warning_text

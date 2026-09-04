"""Tests for Host/Origin validation on the HTTP transport."""

import os
from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from gcore_mcp_server.http_security import (
    ALLOWED_HOSTS_ENV_VAR,
    ALLOWED_ORIGINS_ENV_VAR,
    DEFAULT_ALLOWED_HOSTS,
    build_http_middleware,
)


def _build_client(env: dict[str, str]) -> TestClient:
    """Build a test app whose middleware is configured from `env`."""
    with patch.dict(os.environ, env, clear=False):
        for var in (ALLOWED_HOSTS_ENV_VAR, ALLOWED_ORIGINS_ENV_VAR):
            if var not in env:
                os.environ.pop(var, None)
        app = Starlette(
            routes=[Route("/mcp", lambda _: PlainTextResponse("ok"), methods=["POST"])],
            middleware=build_http_middleware(),
        )
    return TestClient(app, base_url="http://127.0.0.1:8000")


class TestHostValidation:
    """The Host header must match the allowlist."""

    def test_loopback_is_allowed_by_default(self):
        client = _build_client({})
        assert client.post("/mcp", headers={"Host": "127.0.0.1:8000"}).status_code == 200

    def test_default_allowlist_is_loopback_only(self):
        assert DEFAULT_ALLOWED_HOSTS == ("127.0.0.1:*", "localhost:*", "[::1]:*")

    @pytest.mark.parametrize("host", ["localhost:9999", "[::1]:8000"])
    def test_wildcard_port_matches_any_port(self, host: str):
        client = _build_client({})
        assert client.post("/mcp", headers={"Host": host}).status_code == 200

    def test_rebinding_host_is_rejected(self):
        client = _build_client({})
        response = client.post("/mcp", headers={"Host": "rebind.attacker.example"})
        assert response.status_code == 421

    def test_allowlist_is_configurable(self):
        client = _build_client({ALLOWED_HOSTS_ENV_VAR: "mcp.internal:8000"})
        assert client.post("/mcp", headers={"Host": "mcp.internal:8000"}).status_code == 200
        assert client.post("/mcp", headers={"Host": "127.0.0.1:8000"}).status_code == 421


class TestOriginValidation:
    """The Origin header, when present, must match the allowlist."""

    def test_absent_origin_is_allowed(self):
        """Non-browser MCP clients do not send Origin and must keep working."""
        client = _build_client({})
        assert client.post("/mcp", headers={"Host": "127.0.0.1:8000"}).status_code == 200

    def test_no_origin_is_allowlisted_by_default(self):
        client = _build_client({})
        response = client.post(
            "/mcp",
            headers={"Host": "127.0.0.1:8000", "Origin": "https://app.example.com"},
        )
        assert response.status_code == 403

    def test_allowlisted_origin_is_accepted(self):
        client = _build_client({ALLOWED_ORIGINS_ENV_VAR: "https://app.example.com"})
        response = client.post(
            "/mcp",
            headers={"Host": "127.0.0.1:8000", "Origin": "https://app.example.com"},
        )
        assert response.status_code == 200

    def test_rebinding_origin_is_rejected(self):
        """A DNS-rebound page reaches the loopback listener but keeps its Origin."""
        client = _build_client({ALLOWED_ORIGINS_ENV_VAR: "https://app.example.com"})
        response = client.post(
            "/mcp",
            headers={"Host": "127.0.0.1:8000", "Origin": "https://evil.example"},
        )
        assert response.status_code == 403

    def test_host_is_checked_before_origin(self):
        client = _build_client({ALLOWED_ORIGINS_ENV_VAR: "https://app.example.com"})
        response = client.post(
            "/mcp",
            headers={"Host": "rebind.attacker.example", "Origin": "https://evil.example"},
        )
        assert response.status_code == 421

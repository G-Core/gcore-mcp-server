"""Tests for Host/Origin validation on the HTTP transport.

The validation itself is FastMCP's `HostOriginGuardMiddleware`; these tests
pin the configuration this server hands it, and assert the resulting behaviour
end-to-end through the real ASGI app.
"""

import os
from unittest.mock import patch

import pytest
from fastmcp import FastMCP
from starlette.testclient import TestClient

from gcore_mcp_server.config.settings import (
    ALLOWED_HOSTS_ENV_VAR,
    ALLOWED_ORIGINS_ENV_VAR,
    get_allow_list,
    resolve_transport,
)

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _client(allowed_hosts=None, allowed_origins=None) -> TestClient:
    """Build the HTTP app with the guard configuration `main()` passes to `mcp.run()`.

    `main()` runs the app under uvicorn; here the same app is driven in-process
    over ASGI so the tests exercise the real guard without a network listener.
    """
    mcp = FastMCP(name="test-server")

    @mcp.tool
    def ping() -> str:
        """Stand-in for a Gcore tool."""
        return "pong"

    app = mcp.http_app(
        host_origin_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )
    return TestClient(app, base_url="http://127.0.0.1:8000")


def _post(client: TestClient, extra: dict[str, str]) -> int:
    headers = dict(HEADERS)
    headers.update(extra)
    with client:
        return client.post("/mcp/", json=INIT, headers=headers).status_code


class TestAllowListParsing:
    """`GCORE_ALLOWED_*` parsing, which is what this server contributes."""

    def test_unset_variable_is_empty_list(self):
        """Never None: None would let FastMCP substitute its own FASTMCP_HTTP_ALLOWED_* settings."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ALLOWED_HOSTS_ENV_VAR, None)
            assert get_allow_list(ALLOWED_HOSTS_ENV_VAR) == []

    def test_empty_variable_is_empty_list(self):
        with patch.dict(os.environ, {ALLOWED_ORIGINS_ENV_VAR: "  "}):
            assert get_allow_list(ALLOWED_ORIGINS_ENV_VAR) == []

    def test_entries_are_split_and_stripped(self):
        with patch.dict(os.environ, {ALLOWED_HOSTS_ENV_VAR: " a:8000 , b:8000 ,"}):
            assert get_allow_list(ALLOWED_HOSTS_ENV_VAR) == ["a:8000", "b:8000"]


class TestHostValidation:
    """The Host header must match the allow-list."""

    def test_loopback_is_allowed_by_default(self):
        assert _post(_client(), {"Host": "127.0.0.1:8000"}) == 200

    @pytest.mark.parametrize("host", ["localhost:9999", "Localhost:8000"])
    def test_loopback_names_and_ports_are_allowed(self, host: str):
        assert _post(_client(), {"Host": host}) == 200

    def test_rebinding_host_is_rejected(self):
        assert _post(_client(), {"Host": "rebind.attacker.example"}) == 421

    def test_allow_list_admits_a_configured_host(self):
        client = _client(allowed_hosts=["mcp.internal:8000"])
        assert _post(client, {"Host": "mcp.internal:8000"}) == 200


class TestOriginValidation:
    """The Origin header, when present, must match the allow-list."""

    def test_absent_origin_is_allowed(self):
        """Non-browser MCP clients send no Origin and must keep working."""
        assert _post(_client(), {"Host": "127.0.0.1:8000"}) == 200

    def test_foreign_origin_is_rejected_by_default(self):
        status = _post(_client(), {"Host": "127.0.0.1:8000", "Origin": "https://app.example.com"})
        assert status == 403

    def test_allow_listed_origin_is_accepted(self):
        client = _client(allowed_origins=["https://app.example.com"])
        status = _post(client, {"Host": "127.0.0.1:8000", "Origin": "https://app.example.com"})
        assert status == 200

    def test_rebinding_origin_is_rejected(self):
        """A DNS-rebound page reaches the listener but keeps its own Origin."""
        client = _client(allowed_origins=["https://app.example.com"])
        status = _post(client, {"Host": "127.0.0.1:8000", "Origin": "https://evil.example"})
        assert status == 403

    def test_host_is_checked_before_origin(self):
        client = _client(allowed_origins=["https://app.example.com"])
        status = _post(
            client,
            {"Host": "rebind.attacker.example", "Origin": "https://evil.example"},
        )
        assert status == 421


class TestTransportSelection:
    """`GCORE_TRANSPORT` resolution, including the transports we refuse."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (None, "stdio"),
            ("stdio", "stdio"),
            ("http", "streamable-http"),
            ("HTTP", "streamable-http"),
            ("stream", "streamable-http"),
            ("streamable-http", "streamable-http"),
        ],
    )
    def test_known_values_resolve(self, raw, expected):
        assert resolve_transport(raw) == expected

    def test_unknown_value_falls_back_to_stdio(self):
        assert resolve_transport("carrier-pigeon") == "stdio"

    @pytest.mark.parametrize("raw", ["sse", "SSE", " sse "])
    def test_sse_is_refused(self, raw):
        """Regression: SSE must fail to start, not fall back or run unguarded."""
        with pytest.raises(ValueError, match="SSE transport is not supported"):
            resolve_transport(raw)


class TestSseIsUnguardedUpstream:
    """Documents *why* SSE is refused.

    FastMCP only installs `HostOriginGuardMiddleware` in its streamable-HTTP
    app; the SSE app ignores `host_origin_protection` and the allow-lists.
    This test pins that fact. If it ever fails, FastMCP has started guarding
    SSE and the refusal in `resolve_transport` can be reconsidered.
    """

    def test_sse_app_accepts_rebinding_headers(self):
        mcp = FastMCP(name="test-server")

        @mcp.tool
        def ping() -> str:
            """Stand-in for a Gcore tool."""
            return "pong"

        app = mcp.http_app(
            transport="sse",
            host_origin_protection=True,
            allowed_hosts=None,
            allowed_origins=None,
        )
        # The guard, when installed, wraps the whole app, so a POST to the SSE
        # message endpoint is enough to observe it -- and unlike GET /sse it
        # returns immediately rather than holding an event stream open.
        headers = {"Host": "rebind.attacker.example", "Origin": "https://evil.example"}
        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            status = client.post(
                "/messages/?session_id=00000000000000000000000000000000",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers=headers,
            ).status_code

        # 404 is the SDK's "Could not find session" answer, produced by the
        # SSE transport itself -- i.e. the request went past where a guard
        # would sit. 421/403 would mean FastMCP now guards SSE; anything else
        # means the probe no longer reaches the transport.
        assert status == 404, (
            f"expected the SSE transport's 404 for an unknown session, got {status}; "
            "if it is 421/403, FastMCP now guards SSE and the refusal in "
            "resolve_transport can be revisited."
        )


class TestMainWiring:
    """Exercise `main()` itself, so the guard cannot be dropped from the real
    launch path while the middleware tests above stay green."""

    @staticmethod
    def _load_server(env: dict[str, str]):
        """Import (or reload) the server module under the given environment.

        The transport is resolved at import time, so each case needs a fresh
        module. `patch.dict` restores the environment afterwards, including the
        GCORE_TOOLS default the module sets in HTTP mode.
        """
        import importlib

        for var in ("GCORE_TRANSPORT", "FASTMCP_TRANSPORT", "GCORE_TOOLS",
                    ALLOWED_HOSTS_ENV_VAR, ALLOWED_ORIGINS_ENV_VAR):
            os.environ.pop(var, None)
        os.environ.update(env)
        import gcore_mcp_server.server as server

        return importlib.reload(server)

    def test_stdio_names_its_transport_explicitly(self):
        """Regression for the FASTMCP_TRANSPORT bypass: a bare `mcp.run()` would
        let FastMCP start an HTTP/SSE listener from its own settings."""
        with patch.dict(os.environ, {}, clear=False):
            server = self._load_server({"FASTMCP_TRANSPORT": "sse"})
            with patch.object(server.mcp, "run") as run:
                server.main()
        run.assert_called_once()
        assert run.call_args.kwargs.get("transport") == "stdio"

    def test_http_passes_strict_guard_and_explicit_lists(self):
        with patch.dict(os.environ, {}, clear=False):
            server = self._load_server({"GCORE_TRANSPORT": "http"})
            with patch.object(server.mcp, "run") as run:
                server.main()
        kwargs = run.call_args.kwargs
        assert kwargs["transport"] == "streamable-http"
        assert kwargs["host_origin_protection"] is True
        # Explicit empty lists, never None (see get_allow_list).
        assert kwargs["allowed_hosts"] == []
        assert kwargs["allowed_origins"] == []

    def test_http_forwards_configured_lists(self):
        with patch.dict(os.environ, {}, clear=False):
            server = self._load_server({
                "GCORE_TRANSPORT": "http",
                ALLOWED_HOSTS_ENV_VAR: "mcp.internal",
                ALLOWED_ORIGINS_ENV_VAR: "https://app.example.com, https://b.example.com",
            })
            with patch.object(server.mcp, "run") as run:
                server.main()
        kwargs = run.call_args.kwargs
        assert kwargs["allowed_hosts"] == ["mcp.internal"]
        assert kwargs["allowed_origins"] == ["https://app.example.com", "https://b.example.com"]

    def test_sse_imports_cleanly_but_refuses_to_run(self):
        """Importing must not kill the process (tests, tooling); only main() exits."""
        with patch.dict(os.environ, {}, clear=False):
            server = self._load_server({"GCORE_TRANSPORT": "sse"})
            assert server.TRANSPORT_ERROR is not None
            with patch.object(server.mcp, "run") as run:
                with pytest.raises(SystemExit) as exc:
                    server.main()
        assert exc.value.code == 2
        run.assert_not_called()

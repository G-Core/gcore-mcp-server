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
        status = _post(
            _client(), {"Host": "127.0.0.1:8000", "Origin": "https://app.example.com"}
        )
        assert status == 403

    def test_allow_listed_origin_is_accepted(self):
        client = _client(allowed_origins=["https://app.example.com"])
        status = _post(
            client, {"Host": "127.0.0.1:8000", "Origin": "https://app.example.com"}
        )
        assert status == 200

    def test_rebinding_origin_is_rejected(self):
        """A DNS-rebound page reaches the listener but keeps its own Origin."""
        client = _client(allowed_origins=["https://app.example.com"])
        status = _post(
            client, {"Host": "127.0.0.1:8000", "Origin": "https://evil.example"}
        )
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
        """Regression: SSE must fail to start, not fall back to another transport."""
        with pytest.raises(ValueError, match="SSE transport is not supported"):
            resolve_transport(raw)


class TestMainWiring:
    """Exercise `main()` itself, so the guard cannot be dropped from the real
    launch path while the middleware tests above stay green."""

    @staticmethod
    def _run_main(env: dict[str, str]):
        """Run `main()` under ``env`` with a stub server; return the run() mock.

        `create_server` is patched so no SDK introspection happens; `main()`
        still resolves the transport and builds the run() arguments itself.
        """
        from unittest.mock import MagicMock

        import gcore_mcp_server.server as server

        for var in (
            "GCORE_TRANSPORT",
            "FASTMCP_TRANSPORT",
            "GCORE_TOOLS",
            "GCORE_READ_ONLY",
            ALLOWED_HOSTS_ENV_VAR,
            ALLOWED_ORIGINS_ENV_VAR,
        ):
            os.environ.pop(var, None)
        os.environ.update(env)
        fake = MagicMock()
        with patch.object(server, "create_server", return_value=fake) as create:
            server.main([])
        fake.run.policy = create.call_args.kwargs["policy"]
        return fake.run

    def test_http_is_read_only_by_default(self):
        """No client authentication on HTTP: changes need an explicit opt-in."""
        with patch.dict(os.environ, {}, clear=False):
            assert self._run_main({"GCORE_TRANSPORT": "http"}).policy.read_only
            assert not self._run_main(
                {"GCORE_TRANSPORT": "http", "GCORE_READ_ONLY": "false"}
            ).policy.read_only
            assert not self._run_main({}).policy.read_only  # stdio unchanged

    def test_stdio_names_its_transport_explicitly(self):
        """Regression for the FASTMCP_TRANSPORT bypass: a bare `mcp.run()` would
        let FastMCP start an HTTP/SSE listener from its own settings."""
        with patch.dict(os.environ, {}, clear=False):
            run = self._run_main({"FASTMCP_TRANSPORT": "sse"})
        run.assert_called_once()
        assert run.call_args.kwargs.get("transport") == "stdio"

    def test_http_passes_strict_guard_and_explicit_lists(self):
        with patch.dict(os.environ, {}, clear=False):
            run = self._run_main({"GCORE_TRANSPORT": "http"})
        kwargs = run.call_args.kwargs
        assert kwargs["transport"] == "streamable-http"
        assert kwargs["host_origin_protection"] is True
        # Explicit empty lists, never None (see get_allow_list).
        assert kwargs["allowed_hosts"] == []
        assert kwargs["allowed_origins"] == []

    def test_http_forwards_configured_lists(self):
        with patch.dict(os.environ, {}, clear=False):
            run = self._run_main(
                {
                    "GCORE_TRANSPORT": "http",
                    ALLOWED_HOSTS_ENV_VAR: "mcp.internal",
                    ALLOWED_ORIGINS_ENV_VAR: "https://app.example.com, https://b.example.com",
                }
            )
        kwargs = run.call_args.kwargs
        assert kwargs["allowed_hosts"] == ["mcp.internal"]
        assert kwargs["allowed_origins"] == [
            "https://app.example.com",
            "https://b.example.com",
        ]

    def test_sse_refuses_to_run(self):
        """SSE exits with status 2 before any server is built or run."""
        import gcore_mcp_server.server as server

        with patch.dict(os.environ, {}, clear=False):
            os.environ["GCORE_TRANSPORT"] = "sse"
            with patch.object(server, "create_server") as create:
                with pytest.raises(SystemExit) as exc:
                    server.main([])
        assert exc.value.code == 2
        create.assert_not_called()

    def test_importing_the_module_has_no_side_effects(self):
        """Importing must not build a client or a server (tests, tooling)."""
        import importlib

        import gcore_mcp_server.server as server

        with patch("gcore.AsyncGcore") as client_cls:
            importlib.reload(server)
        client_cls.assert_not_called()

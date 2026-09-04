"""Host/Origin allowlisting for the HTTP transport (DNS-rebinding protection)."""

from __future__ import annotations

import logging
import os
from typing import Sequence

from starlette.datastructures import Headers
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("gcore-mcp")

DEFAULT_ALLOWED_HOSTS: tuple[str, ...] = ("127.0.0.1:*", "localhost:*", "[::1]:*")
ALLOWED_HOSTS_ENV_VAR = "GCORE_ALLOWED_HOSTS"
ALLOWED_ORIGINS_ENV_VAR = "GCORE_ALLOWED_ORIGINS"


def _split(raw: str | None) -> list[str]:
    """Parse a comma-separated allow-list, normalized for case-insensitive use."""
    return [item.strip().lower() for item in (raw or "").split(",") if item.strip()]


def _matches(value: str, allowed: Sequence[str]) -> bool:
    """Match a Host/Origin value against the allow-list.

    Hostnames and URI schemes are case-insensitive (RFC 3986 §3.1, §3.2.2), and
    neither a Host nor an Origin header carries a case-sensitive component, so
    the whole value is compared lower-cased. Allow-list entries are already
    normalized by `_split`. A trailing `:*` matches any port.
    """
    value = value.strip().lower()
    for pattern in allowed:
        if pattern == value:
            return True
        if pattern.endswith(":*") and value.startswith(pattern[:-1]):
            return True
    return False


class TransportSecurityMiddleware:
    """Reject requests whose Host or Origin header is not allowlisted."""

    def __init__(
        self,
        app: ASGIApp,
        allowed_hosts: Sequence[str],
        allowed_origins: Sequence[str],
    ) -> None:
        self.app = app
        self.allowed_hosts = list(allowed_hosts)
        self.allowed_origins = list(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)

        host = headers.get("host")
        if not host or not _matches(host, self.allowed_hosts):
            logger.warning("Rejected request with Host header: %r", host)
            await PlainTextResponse("Invalid Host header", status_code=421)(
                scope, receive, send
            )
            return

        # An absent Origin means a non-browser client; only browsers set it.
        origin = headers.get("origin")
        if origin and not _matches(origin, self.allowed_origins):
            logger.warning("Rejected request with Origin header: %r", origin)
            await PlainTextResponse("Invalid Origin header", status_code=403)(
                scope, receive, send
            )
            return

        await self.app(scope, receive, send)


def build_http_middleware() -> list[Middleware]:
    """Build the middleware stack for the HTTP transport."""
    hosts = _split(os.getenv(ALLOWED_HOSTS_ENV_VAR)) or list(DEFAULT_ALLOWED_HOSTS)
    origins = _split(os.getenv(ALLOWED_ORIGINS_ENV_VAR))
    logger.info("HTTP transport allowed hosts: %s", hosts)
    logger.info("HTTP transport allowed origins: %s", origins or "<none>")
    return [
        Middleware(
            TransportSecurityMiddleware,
            allowed_hosts=hosts,
            allowed_origins=origins,
        )
    ]

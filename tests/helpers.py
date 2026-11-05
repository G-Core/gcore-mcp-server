"""Shared helpers for protocol-level tests."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import gcore

from gcore_mcp_server.catalog import Catalog
from gcore_mcp_server.config.server_config import Mode, ServerConfig
from gcore_mcp_server.runtime import SafetyPolicy
from gcore_mcp_server.server import create_server

BASE_URL = "https://api.gcore.com"
PROJECT_ID = 111
REGION_ID = 76


def make_client(
    project: int | None = PROJECT_ID, region: int | None = REGION_ID
) -> Any:
    return gcore.AsyncGcore(
        api_key="test-key",
        base_url=BASE_URL,
        cloud_project_id=project,
        cloud_region_id=region,
        max_retries=0,
    )


def make_server(
    mode: Mode = Mode.DYNAMIC,
    *,
    tools: str | None = None,
    code_execution: bool = True,
    code_writes: bool = False,
    policy: SafetyPolicy | None = None,
    max_result_chars: int = 40_000,
    client: Any | None = None,
    code_timeout_secs: float = 55.0,
    wait_secs: float | None = 50.0,
) -> Any:
    return create_server(
        ServerConfig(
            mode=mode,
            tools=tools,
            code_execution=code_execution,
            code_writes=code_writes,
            max_result_chars=max_result_chars,
            code_timeout_secs=code_timeout_secs,
            wait_secs=wait_secs,
        ),
        client=client if client is not None else make_client(),
        policy=policy or SafetyPolicy(),
    )


@lru_cache(maxsize=1)
def full_catalog() -> Catalog:
    return Catalog.from_client(make_client())


def text(result: Any) -> str:
    """Text of the first content block of a CallToolResult."""
    return result.content[0].text if result.content else ""


def data(result: Any) -> Any:
    return json.loads(text(result))


def tool_tokens(tools: list[Any]) -> int:
    """Approximate token cost of a tools/list response (o200k encoding)."""
    import tiktoken

    enc = tiktoken.get_encoding("o200k_base")
    blob = json.dumps([t.model_dump(exclude_none=True, mode="json") for t in tools])
    return len(enc.encode(blob))

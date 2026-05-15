"""Pytest fixtures and configuration for code_exec test suite."""

from __future__ import annotations

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run anyio tests on the asyncio backend."""
    return "asyncio"

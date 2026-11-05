"""Gcore API MCP server."""

from importlib.metadata import PackageNotFoundError, version

try:
    # The version lives only in pyproject.toml; read it from the installed package.
    __version__ = version("gcore-mcp-server")
except PackageNotFoundError:  # pragma: no cover - running from an uninstalled tree
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]

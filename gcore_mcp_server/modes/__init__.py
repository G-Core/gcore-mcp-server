"""Tool-surface modes: dynamic (meta-tools), direct (one tool per method)."""

from .direct import register_direct_tools
from .dynamic import register_dynamic_tools

__all__ = ["register_direct_tools", "register_dynamic_tools"]

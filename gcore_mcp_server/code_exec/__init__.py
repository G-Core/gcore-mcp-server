"""Code-execution mode: meta-tools that orchestrate the Gcore SDK via Monty.

Public surface used by ``server.py`` and tests:

* :func:`build_catalog` – build a searchable view of the SDK.
* :class:`Catalog`, :class:`ToolEntry`, :class:`ParamInfo` – catalog data types.
* :func:`execute_code` – run a short Python script inside the Monty sandbox.
* :func:`make_call_tool` – host-side dispatcher used inside the sandbox.
* :func:`register_meta_tools` – attach the three meta-tools to a FastMCP app.
* :class:`ExecResult` – typed return of ``execute_code``.
"""

from .catalog import Catalog, ParamInfo, ToolEntry, build_catalog
from .dispatch import make_call_tool
from .meta_tools import register_meta_tools
from .runner import ExecResult, execute_code

__all__ = [
    "Catalog",
    "ExecResult",
    "ParamInfo",
    "ToolEntry",
    "build_catalog",
    "execute_code",
    "make_call_tool",
    "register_meta_tools",
]

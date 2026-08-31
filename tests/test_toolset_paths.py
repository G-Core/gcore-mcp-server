"""Tests that toolset definitions stay in sync with the installed SDK."""

import pytest

from gcore import Gcore

from gcore_mcp_server.config.settings import generate_short_tool_name
from gcore_mcp_server.config.toolsets import get_raw_toolsets
from gcore_mcp_server.core.inspection import clear_inspection_cache, iter_sdk_methods


@pytest.fixture(scope="module")
def sdk_tool_names() -> set[str]:
    """Every method path the server can discover in the installed SDK."""
    clear_inspection_cache()
    client = Gcore(api_key="test-dummy-key-for-testing")
    return {full_name for full_name, _ in iter_sdk_methods(client)}


def test_every_toolset_entry_exists_in_sdk(sdk_tool_names: set[str]) -> None:
    """A toolset must not reference a method the SDK does not have.

    An entry that no longer resolves is dropped silently at startup - the
    server only logs a warning - so the tool disappears without any error.
    This is what breaks when the SDK renames a resource.
    """
    unresolved: dict[str, list[str]] = {}
    for toolset_name, tool_names in get_raw_toolsets().items():
        missing = sorted(set(tool_names) - sdk_tool_names)
        if missing:
            unresolved[toolset_name] = missing

    assert not unresolved, (
        "Toolset entries missing from the installed SDK: "
        + "; ".join(
            f"{toolset}: {', '.join(names)}"
            for toolset, names in sorted(unresolved.items())
        )
    )


def test_shortened_tool_names_are_unique(sdk_tool_names: set[str]) -> None:
    """Two SDK methods must not shorten to the same tool name.

    Tools are registered under their shortened name, so a collision means one
    method silently overwrites the other.
    """
    collisions: dict[str, list[str]] = {}
    for full_name in sdk_tool_names:
        collisions.setdefault(generate_short_tool_name(full_name), []).append(full_name)

    clashing = {
        short: sorted(names) for short, names in collisions.items() if len(names) > 1
    }

    assert not clashing, "Short tool names are not unique: " + "; ".join(
        f"{short} <- {', '.join(names)}" for short, names in sorted(clashing.items())
    )

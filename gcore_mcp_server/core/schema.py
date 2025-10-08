"""Type normalization for FastMCP compatibility."""

from typing import (
    Any,
    Union,
    get_origin,
    get_args,
)

from gcore import NotGiven, Omit

try:
    from gcore import Timeout
except ImportError:
    Timeout = None  # type: ignore


def _is_pydantic_compatible(param_type: Any) -> bool:
    """
    Check if a type can be handled by Pydantic without errors.

    Returns False for types that Pydantic cannot generate schemas for,
    preventing server initialization failures.
    """
    from typing import IO
    import os

    origin = get_origin(param_type)

    # Types that Pydantic cannot handle
    incompatible_origins = {IO}
    if origin in incompatible_origins:
        return False

    # Check for problematic type names
    if hasattr(param_type, "__name__"):
        incompatible_names = {"IO", "BinaryIO", "TextIO"}
        if param_type.__name__ in incompatible_names:
            return False

    # PathLike is also problematic
    if param_type is os.PathLike:
        return False

    return True


def normalize_sdk_type_for_mcp(param_type: Any) -> Any:
    """
    Normalize SDK type annotations to be FastMCP-compatible for schema generation.

    Converts:
    - Union[T, NotGiven] → T | None
    - Union[T, Omit] → T | None
    - T | NotGiven → T | None
    - T | Omit → T | None
    - Iterable[T] → list[T] (for JSON schema compatibility)
    - IO[T] → str (file paths as strings)
    - Any Pydantic-incompatible type → str (defensive fallback)

    This ensures FastMCP generates correct JSON schemas while maintaining
    backward compatibility with JSON string parsing.

    DEFENSIVE: If a new type appears that Pydantic can't handle, it will be
    converted to str rather than causing server initialization to fail.
    """
    from typing import List, IO, Iterable
    from collections.abc import Sequence, Iterable as abcIterable, Set as abcSet
    import types
    import os

    origin = get_origin(param_type)
    args = get_args(param_type)

    # DEFENSIVE: Check if Pydantic can handle this type
    # Convert incompatible types to str to prevent server hangs
    if not _is_pydantic_compatible(param_type):
        return str

    # Handle IO types - convert to string (for file paths)
    if origin is IO or (
        hasattr(param_type, "__name__") and param_type.__name__ == "IO"
    ):
        return str

    # Handle PathLike - convert to string
    if param_type is os.PathLike or (
        hasattr(param_type, "__name__") and "PathLike" in param_type.__name__
    ):
        return str

    # SDK-specific types to filter out
    sdk_types = {Omit, NotGiven, type(None)}
    if Timeout is not None:
        sdk_types.add(Timeout)
    sdk_type_names = {"Omit", "NotGiven", "Timeout"}

    # Handle Union types (both Union[...] and T | U syntax) with SDK-specific markers
    if origin is Union or origin is types.UnionType:
        # Filter out SDK-specific types
        actual_args = []
        for arg in args:
            # Check if arg is an SDK-specific class
            if arg in sdk_types:
                continue
            # Also check string representation for edge cases
            if hasattr(arg, "__name__") and arg.__name__ in sdk_type_names:
                continue
            actual_args.append(arg)

        has_none = type(None) in args
        has_sdk_marker = any(
            arg in sdk_types
            or (hasattr(arg, "__name__") and arg.__name__ in sdk_type_names)
            for arg in args
        )

        if not actual_args:
            # Union[NotGiven] or Union[Omit, None] → Any | None
            return Any | None

        # Recursively normalize each arg in the union
        normalized_args = [normalize_sdk_type_for_mcp(arg) for arg in actual_args]

        if len(normalized_args) == 1:
            # Union[T, NotGiven] → T | None (after normalizing T)
            if has_none or has_sdk_marker:
                return normalized_args[0] | None
            return normalized_args[0]

        # Union[T1, T2, NotGiven] → Union[T1, T2] | None (after normalizing T1, T2)
        union_type = Union[tuple(normalized_args)]
        if has_none or has_sdk_marker:
            return union_type | None
        return union_type

    # Convert Iterable[T] to List[T] for JSON schema compatibility
    # JSON doesn't distinguish between different iterable types
    if origin in (abcIterable, Iterable):
        if args:
            # Recursively normalize the inner type
            normalized_inner = normalize_sdk_type_for_mcp(args[0])
            return List[normalized_inner]
        return List[Any]

    # Convert Sequence[T] to List[T]
    if origin is Sequence:
        if args:
            normalized_inner = normalize_sdk_type_for_mcp(args[0])
            return List[normalized_inner]
        return List[Any]

    # Convert Set[T] to List[T] (JSON doesn't have sets)
    if origin in (set, abcSet):
        if args:
            normalized_inner = normalize_sdk_type_for_mcp(args[0])
            return List[normalized_inner]
        return List[Any]

    # Handle Mapping/Dict types - recursively normalize value types
    from collections.abc import Mapping

    if origin in (dict, Mapping):
        if args and len(args) >= 2:
            # Normalize both key and value types
            normalized_key = normalize_sdk_type_for_mcp(args[0])
            normalized_value = normalize_sdk_type_for_mcp(args[1])
            return dict[normalized_key, normalized_value]
        return dict[Any, Any]

    # For any other generic type, try to recursively normalize args
    if origin and args:
        try:
            normalized_args = tuple(normalize_sdk_type_for_mcp(arg) for arg in args)
            # Try to reconstruct the generic type with normalized args
            return origin[normalized_args]
        except Exception:
            # If reconstruction fails, return as-is
            pass

    # DEFENSIVE FALLBACK: If we reach here with a complex type,
    # try to verify it's Pydantic-compatible
    # This is a last resort to prevent server hangs from unknown types
    if origin or args:
        try:
            # Quick test: can Pydantic handle this?
            from pydantic import TypeAdapter

            TypeAdapter(param_type)
            # If we got here, Pydantic can handle it
            return param_type
        except Exception:
            # Pydantic can't handle it - convert to Any to be safe
            # This prevents server hangs but loses some type information
            import logging

            logger = logging.getLogger("gcore-mcp")
            logger.warning(
                f"Type normalization: Unknown type {param_type} is not Pydantic-compatible, "
                f"converting to Any. This may result in less specific schema information."
            )
            return Any

    return param_type

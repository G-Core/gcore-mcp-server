"""Shared SDK result serialization helpers."""

from __future__ import annotations

from typing import Any


def serialize_result(result: Any) -> Any:  # noqa: ANN401
    """Convert SDK result to JSON-serializable format."""
    if result is None:
        return None

    # Handle basic types
    if isinstance(result, (str, int, float, bool)):
        return result

    # Handle lists
    if isinstance(result, list):
        return [serialize_result(item) for item in result]  # type: ignore[misc]

    # Handle dicts
    if isinstance(result, dict):
        return {key: serialize_result(value) for key, value in result.items()}  # type: ignore[misc]

    # Handle objects with model_dump() method (Pydantic v2)
    if hasattr(result, "model_dump") and callable(getattr(result, "model_dump")):
        try:
            return serialize_result(result.model_dump())
        except Exception:
            pass

    # Handle objects with __dict__
    if hasattr(result, "__dict__"):
        try:
            obj_dict: dict[str, Any] = {}
            for key, value in result.__dict__.items():
                if not key.startswith("_"):  # Skip private attributes
                    obj_dict[key] = serialize_result(value)
            return obj_dict
        except Exception:
            pass

    # Fallback to string representation
    return str(result)

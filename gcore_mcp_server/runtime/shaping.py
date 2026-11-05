"""Turn SDK results and errors into compact, model-friendly output."""

from __future__ import annotations

import datetime
import enum
import json
import uuid
from decimal import Decimal
from typing import Any, cast

from fastmcp.exceptions import ToolError
from pydantic import BaseModel
from pydantic_core import to_jsonable_python

DEFAULT_MAX_RESULT_CHARS = 40_000


def text_result(data: Any) -> Any:
    """A tool result as one JSON text block, with no ``structuredContent``.

    Every reader of these tools is a model, and none of them has a fixed
    result shape to declare as an ``outputSchema``. A structured copy would
    add nothing, and clients that pass both to the model (Codex does) would
    pay for every result twice.
    """
    from fastmcp.tools.base import ToolResult
    from mcp_types import TextContent

    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    return ToolResult(content=[TextContent(type="text", text=text)])


def to_jsonable(value: Any) -> Any:
    """Convert an SDK result into plain JSON data.

    Results speak the SDK's interface, like the arguments do: SDK models give
    exactly their declared fields, under the SDK's (Python) names. Two kinds
    of keys the raw response carries are left out:

    * the API's spelling of a renamed field (``originGroup`` next to
      ``origin_group``), which SDK responses keep because they are built
      without validation;
    * fields this SDK version doesn't declare yet; they appear once the SDK
      is upgraded, so results, schemas and the ``returns`` outline agree.

    ``None`` fields are removed: models carry dozens of unset optional fields,
    and dropping them typically halves the tokens a result costs. So are the
    empty lists in a task's ``created_resources`` (one per resource kind,
    about 40, of which a task fills one or two).
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        mapping: dict[Any, Any] = dict(value)  # pyright: ignore[reportUnknownArgumentType]
        return {str(k): to_jsonable(v) for k, v in mapping.items() if v is not None}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, BaseModel):
        out: dict[str, Any] = {}
        for name in type(value).model_fields:
            field_value = getattr(value, name, None)
            if field_value is not None:
                out[name] = to_jsonable(field_value)
        created = out.get("created_resources")
        if isinstance(created, dict):
            kinds = cast(dict[str, Any], created)
            out["created_resources"] = {k: v for k, v in kinds.items() if v != []}
        return out
    if isinstance(value, (datetime.date, datetime.time, enum.Enum, uuid.UUID, Decimal)):
        return to_jsonable_python(value)
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        try:
            # warnings=False: some SDK models declare str for numeric
            # fields (e.g. region latitude); the data is still right.
            return to_jsonable(dump(mode="json", exclude_none=True, warnings=False))
        except Exception:
            pass
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if hasattr(value, "__dict__"):
        attrs: dict[str, Any] = dict(vars(value))  # pyright: ignore[reportUnknownArgumentType]
        return {
            k: to_jsonable(v)
            for k, v in attrs.items()
            if not k.startswith("_") and v is not None
        }
    return str(value)


def _size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str))


def _fit_list(items: list[Any], budget: int) -> int:
    """How many leading ``items`` fit into ``budget`` characters."""
    used = 2
    for i, item in enumerate(items):
        used += _size(item) + 2  # json.dumps separates items with ", "
        if used > budget:
            return i
    return len(items)


HINT_NARROW = "Result too large. Narrow it with filters or limit/offset."
HINT_WITH_CODE = (
    "Result too large. Narrow it with filters or limit/offset, or use "
    "execute_code to filter/aggregate before returning."
)
HINT_IN_SCRIPT = (
    "Script result too large. Return less: select the fields you need, filter, "
    "or aggregate in the script."
)


def truncate(
    value: Any, max_chars: int = DEFAULT_MAX_RESULT_CHARS, hint: str = HINT_NARROW
) -> tuple[Any, bool]:
    """Shrink ``value`` to roughly ``max_chars`` of JSON.

    Lists (and paginated ``{"results": [...]}`` pages) keep as many leading
    items as fit and gain a ``_truncated`` note saying how many were dropped
    and how to get the rest. Anything else is cut as text. Returns
    ``(value, truncated)``.
    """
    if max_chars <= 0 or _size(value) <= max_chars:
        return value, False

    if isinstance(value, list):
        items: list[Any] = list(value)  # pyright: ignore[reportUnknownArgumentType]
        note = {"_truncated": {"shown": len(items), "total": len(items), "hint": hint}}
        keep = _fit_list(items, max_chars - _size(note) - 2)
        note["_truncated"]["shown"] = keep
        return [*items[:keep], note], True
    if isinstance(value, dict):
        page: dict[str, Any] = dict(value)  # pyright: ignore[reportUnknownArgumentType]
        for key in ("results", "items", "data"):
            seq = page.get(key)
            if isinstance(seq, list):
                items = list(seq)  # pyright: ignore[reportUnknownArgumentType]
                note = {"shown": len(items), "total": len(items), "hint": hint}
                rest = {k: v for k, v in page.items() if k != key}
                rest["_truncated"] = note
                keep = _fit_list(items, max_chars - _size(rest) - len(key) - 6)
                note["shown"] = keep
                page[key] = items[:keep]
                page["_truncated"] = note
                if _size(page) <= max_chars:
                    return page, True
                break  # other fields alone are too big: cut as text below
    text = json.dumps(value, ensure_ascii=False, default=str)
    keep_chars = max(
        0, max_chars - _size({"partial_json": "", "_truncated": {"hint": hint}})
    )
    out: dict[str, Any] = {
        "partial_json": text[:keep_chars],
        "_truncated": {"hint": hint},
    }
    # JSON-escaping the embedded text can make it longer; shrink until it fits.
    while keep_chars > 0 and _size(out) > max_chars:
        keep_chars = max(0, keep_chars - (_size(out) - max_chars))
        out["partial_json"] = text[:keep_chars]
    return out, True


# --------------------------------------------------------------------------- errors


def _status_hint(status: int, tool: str) -> str:
    if status == 401:
        return "The API key is missing or invalid. Check GCORE_API_KEY."
    if status == 403:
        return "The API key is not allowed to do this. Use a key with the needed permissions."
    if status == 404:
        if tool.startswith("cloud."):
            return (
                "Not found. Check the ID (list the resource first) and the "
                "project_id/region_id."
            )
        return "Not found. Check the ID or name (list the resource first)."
    if status == 409:
        return "Conflict with the resource's current state; fetch it and retry."
    if status in (400, 422):
        return (
            "The API rejected the arguments; its message above says why. "
            "get_tool_schema lists the parameters."
        )
    if status == 429:
        return "Rate limited. Wait a little and retry."
    if status >= 500:
        return "Gcore API server error. Retrying later may help."
    return ""


def describe_error(exc: BaseException, tool: str) -> str:
    """One readable message for any failure while calling ``tool``."""
    import gcore
    from pydantic import ValidationError

    if isinstance(exc, ToolError):
        return str(exc)
    if isinstance(exc, gcore.APIStatusError):
        body = exc.body
        # The API's own hint knows the actual problem ("detach the resources
        # in blocking_resources"); a generic one would only point elsewhere.
        # It is shown once, on the Hint line.
        api_hint = (
            cast(dict[str, Any], body).get("hint") if isinstance(body, dict) else None
        )
        if isinstance(api_hint, str) and api_hint.strip():
            hint = api_hint.strip()
            body = {k: v for k, v in cast(dict[str, Any], body).items() if k != "hint"}
        else:
            hint = _status_hint(exc.status_code, tool)
        detail = (
            json.dumps(body, default=str)[:1500] if body is not None else exc.message
        )
        return f"{tool} failed: HTTP {exc.status_code}: {detail}" + (
            f"\nHint: {hint}" if hint else ""
        )
    if isinstance(exc, gcore.APITimeoutError):
        return f"{tool} failed: request timed out. Retry, or for long operations use the *_and_poll variant."
    if isinstance(exc, gcore.APIConnectionError):
        return f"{tool} failed: could not reach the Gcore API ({exc}). Check GCORE_BASE_URL and network access."
    if isinstance(exc, ValidationError):
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(arguments)'}: {err['msg']}"
            for err in exc.errors()[:10]
        )
        return (
            f"Invalid arguments for {tool}: {problems}\n"
            f"Hint: call get_tool_schema('{tool}') for the expected parameters."
        )
    message = str(exc) or type(exc).__name__
    if "project_id" in message:
        message += "\nHint: pass project_id (find it with cloud.projects.list)."
    elif "region_id" in message:
        message += "\nHint: pass region_id (find it with cloud.regions.list)."
    return f"{tool} failed: {type(exc).__name__}: {message}"

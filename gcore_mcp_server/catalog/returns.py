"""What an operation returns, summarized from the SDK's return type.

``get_tool_schema`` shows this next to the argument schema, so a model writing
a script knows the result's field names instead of guessing them (or spending
a call printing a sample). It is a compact outline, not a JSON schema: the
SDK's field names (which is what results contain, see
``runtime.shaping.to_jsonable``), with nested objects listed one level deep.
"""

from __future__ import annotations

import types
from typing import Annotated, Any, Callable, Union, get_args, get_origin, get_type_hints

from pydantic import BaseModel

MAX_NESTED = 15
"""Field names listed for a nested object before the list is cut."""

SMALL_OBJECT = 6
"""Objects one level further down are expanded only up to this many fields
(``usage{cost,currency,unit,value}``); bigger ones show as ``{...}``."""

DEPTH = 2


def describe_returns(method: Callable[..., Any]) -> dict[str, Any] | None:
    """Outline of what ``method`` returns, or ``None`` if the SDK doesn't say."""
    try:
        ret = get_type_hints(method).get("return")
    except Exception:
        return None
    if ret is None:
        return None
    return _describe(ret)


def _describe(tp: Any) -> dict[str, Any]:
    if _name(get_origin(tp)) == "AsyncPaginator":
        return _page(get_args(tp)[1])
    tp = _strip(tp)
    if tp is type(None):
        return {"nothing": "the result is {'ok': true}"}
    models = _models(tp)
    if models:
        return {"fields": _fields(models, DEPTH)}
    if get_origin(tp) is list:
        item = _strip(get_args(tp)[0]) if get_args(tp) else Any
        item_models = _models(item)
        if item_models:
            return {"list_of": _fields(item_models, DEPTH)}
        return {"list_of": _name(item)}
    return {"type": _name(tp)}


def _page(page: Any) -> dict[str, Any]:
    """One page of a list operation: its list key, other keys and item fields."""
    out: dict[str, Any] = {}
    other: list[str] = []
    for name, field in page.model_fields.items():
        key = name
        ann = _strip(field.annotation)
        if get_origin(ann) is list and "list_key" not in out:
            out["list_key"] = key
            item_models = _models(_strip(get_args(ann)[0]))
            out["item_fields"] = _fields(item_models, DEPTH)
        else:
            other.append(key)
    if other:
        out["other_keys"] = other
    return out


def _fields(models: list[type[BaseModel]], depth: int) -> list[str]:
    """Field names of ``models`` (merged, for a union), nested objects inline.

    ``instance{id,name,status}`` is an object, ``addresses[]{addr,type}`` a
    list of objects. Objects inside those are expanded only when small.
    """
    seen: dict[str, str] = {}
    for model in models:
        for name, field in model.model_fields.items():
            key = name
            if key in seen:
                continue
            seen[key] = _field_text(key, field.annotation, depth)
    return list(seen.values())


def _field_text(key: str, annotation: Any, depth: int) -> str:
    ann = _strip(annotation)
    suffix = ""
    if get_origin(ann) is list and get_args(ann):
        ann = _strip(get_args(ann)[0])
        suffix = "[]"
    models = _models(ann)
    if not models:
        return key + suffix
    small = sum(len(m.model_fields) for m in models) <= SMALL_OBJECT
    if depth == 0 or (depth == 1 and not small):
        return f"{key}{suffix}{{...}}"
    inner = _fields(models, depth - 1)
    if len(inner) > MAX_NESTED:
        inner = [*inner[:MAX_NESTED], "..."]
    return f"{key}{suffix}{{{','.join(inner)}}}"


def _strip(tp: Any) -> Any:
    """Drop ``Annotated`` and ``Optional`` wrappers."""
    while True:
        origin = get_origin(tp)
        if origin is Annotated:
            tp = get_args(tp)[0]
        elif origin is Union or isinstance(tp, types.UnionType):
            args = [a for a in get_args(tp) if a is not type(None)]
            if len(args) != 1:
                return tp
            tp = args[0]
        else:
            return tp


def _models(tp: Any) -> list[type[BaseModel]]:
    """The model classes ``tp`` stands for: one, several (a union) or none."""
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        return [tp]
    if get_origin(tp) is Union or isinstance(tp, types.UnionType):
        found: list[type[BaseModel]] = []
        for arg in get_args(tp):
            found.extend(_models(_strip(arg)))
        return found
    return []


def _name(tp: Any) -> str:
    return getattr(tp, "__name__", None) or str(tp).replace("typing.", "")

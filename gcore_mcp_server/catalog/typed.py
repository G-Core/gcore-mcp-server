"""Build a typed, validating async function for one SDK method.

The function's signature is what FastMCP turns into the tool's JSON schema, and
calling it through a Pydantic ``TypeAdapter`` validates and coerces arguments
before the SDK is called. Both the direct mode (one MCP tool per method) and the
discovery mode (``call_tool``) go through this one function, so the schema a
model reads is exactly what the server enforces.
"""

from __future__ import annotations

import inspect
import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
import types
from typing import (
    Annotated,
    Any,
    Callable,
    Iterable,
    Iterator,
    Literal,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

from pydantic import Field, TypeAdapter

from gcore_mcp_server.core.schema import normalize_sdk_type_for_mcp

from . import uploads

logger = logging.getLogger(__name__)

# Transport-level knobs every SDK method accepts. They are noise for a model
# and would let it override auth headers, so they are never exposed.
HIDDEN_PARAMS = frozenset(
    {
        "extra_headers",
        "extra_query",
        "extra_body",
        "timeout",
        # The server bounds every polling call (GCORE_WAIT_TIMEOUT); offering
        # these only suggests a model could wait longer through them.
        "polling_interval_seconds",
        "polling_timeout_seconds",
    }
)

PROJECT_NOTE = (
    "If omitted, the account's default project is used (except for destructive "
    "operations). cloud.projects.list shows all projects."
)
CLIENT_NOTE = (
    "If omitted, the account's client ID is used (except for destructive operations)."
)
REGION_NOTE = (
    "If omitted, list operations search every region; other operations need it. "
    "cloud.regions.list shows all regions."
)


def scoped_path_params(method: Callable[..., Any], full_name: str) -> frozenset[str]:
    """``project_id``/``region_id`` parameters that are URL path parameters.

    Those fall back to a default when omitted. For a few operations
    (``cloud.tasks.list``, ``cloud.audit_logs.list``) they are optional
    *filters* instead, where leaving them unset means "all".
    """
    try:
        src = inspect.getsource(method)
    except (OSError, TypeError):
        return frozenset()
    found: set[str] = set()
    for param in ("project_id", "region_id"):
        if f"_get_cloud_{param}_path_param" in src or (
            # *_and_poll wrappers pass the argument on to the base method.
            full_name.endswith("_and_poll") and f"{param}={param}" in src
        ):
            found.add(param)
    return frozenset(found)


_SDK_SENTINELS = ("NotGiven", "Omit", "Timeout")

# Arguments the caller passed as null on purpose, set around one call by the
# dispatcher. ``None`` otherwise means "not given" and is dropped so the SDK
# applies its defaults; but for a nullable field, an explicit null is a value
# ("port_id: null" unassigns a floating IP), so it must reach the SDK.
_EXPLICIT_NULLS: ContextVar[frozenset[str]] = ContextVar(
    "explicit_nulls", default=frozenset()
)


@contextmanager
def explicit_nulls(names: Iterable[str]) -> Iterator[None]:
    """Mark ``names`` as passed as null by the caller, for calls made inside."""
    token = _EXPLICIT_NULLS.set(frozenset(names))
    try:
        yield
    finally:
        _EXPLICIT_NULLS.reset(token)


def _nullable(annotation: Any) -> bool:
    """The SDK accepts ``None`` for this parameter (``Optional[str] | Omit``)."""
    return type(None) in get_args(annotation) or any(
        _nullable(a) for a in get_args(annotation) if get_origin(a) is not None
    )


def _is_sentinel(value: Any) -> bool:
    return type(value).__name__ in _SDK_SENTINELS


def _accepts_str(annotation: Any) -> bool:
    """True when ``annotation`` (possibly a union) admits a plain string."""
    if annotation is str or annotation is Any:
        return True
    origin = get_origin(annotation)
    if origin is Annotated:
        return _accepts_str(get_args(annotation)[0])
    if origin is Union or isinstance(annotation, types.UnionType):
        return any(_accepts_str(a) for a in get_args(annotation))
    if origin is Literal:
        return any(isinstance(a, str) for a in get_args(annotation))
    return False


def build_typed_function(
    method: Callable[..., Any],
    full_name: str,
    arg_docs: dict[str, str],
    description: str,
    path_params: frozenset[str] | None = None,
) -> tuple[Callable[..., Any], list[str]]:
    """Return ``(async_fn, string_params)`` for ``method``.

    ``async_fn`` has a cleaned, fully annotated signature and calls the SDK
    method with the validated arguments (dropping ``None`` values so the SDK
    applies its own defaults). ``string_params`` lists parameters that accept a
    plain string, which the dispatcher must not JSON-decode.
    """
    sig = inspect.signature(method)
    try:
        hints = get_type_hints(method, include_extras=False)
    except Exception as exc:  # pragma: no cover - SDK type hints always resolve today
        logger.warning("Type hints unavailable for %s: %s", full_name, exc)
        hints = {
            n: p.annotation
            for n, p in sig.parameters.items()
            if p.annotation is not inspect.Parameter.empty
        }

    params: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {}
    string_params: list[str] = []
    file_params: list[str] = []

    if path_params is None:
        path_params = scoped_path_params(method, full_name)
    for name, param in sig.parameters.items():
        if name in HIDDEN_PARAMS or name in ("self", "cls"):
            continue
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        raw = hints.get(name, Any)
        doc = arg_docs.get(name, "")
        if uploads.is_file_param(raw):
            # File contents: taken as a local path (see catalog/uploads.py).
            file_params.append(name)
            typ = str
            doc = uploads.describe(full_name)
        else:
            try:
                typ = normalize_sdk_type_for_mcp(raw)
                TypeAdapter(typ)
            except Exception:
                # A type Pydantic cannot describe: accept anything rather than
                # drop the whole method.
                typ = Any

        required = param.default is inspect.Parameter.empty
        if name == "project_id" and name in path_params:
            required = False
            doc = f"{doc + '. ' if doc else ''}{PROJECT_NOTE}"
        elif name == "region_id" and name in path_params:
            required = False
            doc = f"{doc + '. ' if doc else ''}{REGION_NOTE}"
        elif name == "client_id" and required:
            # Filled in by runtime.scope (one API key, one client).
            required = False
            doc = f"{doc + '. ' if doc else ''}{CLIENT_NOTE}"

        default: Any = inspect.Parameter.empty
        if not required:
            default = None
            if param.default is not inspect.Parameter.empty and not _is_sentinel(
                param.default
            ):
                default = param.default
            typ = typ | None if typ is not Any else Any

        if _accepts_str(typ):
            string_params.append(name)

        annotated = Annotated[typ, Field(description=doc)] if doc else typ
        annotations[name] = annotated
        params.append(
            inspect.Parameter(
                name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotated,
            )
        )

    nullable = frozenset(n for n in sig.parameters if _nullable(hints.get(n, Any)))

    async def call_sdk(**kwargs: Any) -> Any:
        keep_null = _EXPLICIT_NULLS.get() & nullable
        clean = {k: v for k, v in kwargs.items() if v is not None or k in keep_null}
        for name in file_params:
            if clean.get(name) is not None:
                clean[name] = uploads.open_upload(full_name, clean[name])
        result = method(**clean)
        if inspect.isawaitable(result):
            result = await result
        return result

    call_sdk.__name__ = full_name.replace(".", "_")
    call_sdk.__qualname__ = call_sdk.__name__
    call_sdk.__doc__ = description
    annotations["return"] = Any
    call_sdk.__annotations__ = annotations
    call_sdk.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        parameters=params, return_annotation=Any
    )
    return call_sdk, string_params


def coerce_json_strings(
    arguments: dict[str, Any], string_params: list[str]
) -> dict[str, Any]:
    """Decode JSON-encoded strings passed for non-string parameters.

    Some clients serialize nested objects as strings. Only values that look
    like JSON objects/arrays, for parameters that do not accept strings, are
    decoded.
    """
    out = dict(arguments)
    for key, value in arguments.items():
        if key in string_params or not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped[:1] in ("[", "{"):
            try:
                out[key] = json.loads(stripped)
            except json.JSONDecodeError:
                pass
    return out

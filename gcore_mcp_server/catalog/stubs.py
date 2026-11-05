"""Typed Python modules for execute_code scripts, generated from the SDK.

A script imports an API resource as a module and calls its operations as
typed functions::

    import gcore.cloud.floating_ips as fips
    page = await fips.list(region_id=76)
    page["results"][0]["floating_ip_address"]

This module writes the ``.pyi`` stub for each resource (``cloud.floating_ips``)
so the sandbox's type checker knows every operation's arguments and result
fields, and stops a script that misspells one before any API call runs.

Arguments come from the same typed signatures the input schemas are built
from (``typed.build_typed_function``), so stubs and schemas can't disagree.
Results are ``TypedDict``s of the SDK's response models, matching what the
server returns (``runtime.shaping.to_jsonable``):

* SDK field names, declared fields only;
* every key optional (``total=False``): ``None`` fields are dropped, so a key
  may be absent, but a present value is never ``None``;
* the server's own additions: ``_scope`` when the default project was filled
  in, and the region-search keys on lists that searched every region.

Nothing is committed to the repository: stubs are generated on demand from
the installed SDK, so an SDK upgrade carries through by itself.
"""

from __future__ import annotations

import datetime
import enum
import re
import sys
import types
import typing
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel
from typing_extensions import is_typeddict

from .catalog import ToolEntry

ROOT = "gcore"
"""Top-level package scripts import from (``import gcore.dns.zones``)."""

# Placeholders the SDK uses for "argument not given"; not real values.
_SENTINELS = frozenset({"NotGiven", "Omit", "Timeout"})

_HEADER = (
    "import builtins as _b\n"
    "from typing import Any, Literal, TypedDict\n"
    "from typing_extensions import NotRequired\n"
)

# Keys the server adds to results (see runtime.dispatch and runtime.scope).
_SCOPE_KEY = ("_scope", "_b.dict[_b.str, Any]")
_REGION_KEYS = (
    ("regions_searched", "_b.int"),
    ("regions_failed", "_b.dict[_b.str, _b.str]"),
    ("regions_without_service", "_b.dict[_b.str, Any]"),
    ("incomplete", "_b.dict[_b.str, Any]"),
    ("note", "_b.str"),
)


@dataclass
class ModuleStub:
    """The stub of one resource module, and how much of it is untyped."""

    path: str
    source: str
    fallbacks: int
    """Spots typed as ``Any`` because the SDK type was not understood."""


def module_stub(path: str, entries: list[ToolEntry]) -> ModuleStub:
    """Stub for the resource ``path`` (``cloud.floating_ips``) and its operations."""
    writer = _Writer()
    for entry in entries:
        writer.function(entry)
    return ModuleStub(path, writer.source(), writer.fallbacks)


@dataclass
class _Writer:
    classes: dict[str, str] = field(default_factory=dict[str, str])
    names: dict[Any, str] = field(default_factory=dict[Any, str])
    functions: list[str] = field(default_factory=list[str])
    fallbacks: int = 0
    # Module namespaces of the models being written, innermost last: forward
    # references (recursive models) resolve against them.
    namespaces: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    def source(self) -> str:
        parts = [_HEADER, *(c for c in self.classes.values() if c), *self.functions]
        return "\n\n".join(parts) + "\n"

    # ------------------------------------------------------------ functions

    def function(self, entry: ToolEntry) -> None:
        required = set(entry.required_params)
        params: list[str] = []
        signature = entry.fn.__signature__  # pyright: ignore[reportFunctionMemberAccess]
        for param in signature.parameters.values():
            annotation = self.render(param.annotation, result=False)
            default = "" if param.name in required else " = ..."
            params.append(f"{param.name}: {annotation}{default}")
        method = entry.name.rsplit(".", 1)[-1]
        args = ", ".join(["*", *params]) if params else ""
        self.functions.append(
            f"async def {method}({args}) -> {self.returns(entry)!r}: ..."
        )

    def returns(self, entry: ToolEntry) -> str:
        try:
            ret = typing.get_type_hints(entry.method).get("return")
        except Exception:
            self.fallbacks += 1
            return "Any"
        extra: list[tuple[str, str]] = []
        if "project_id" in entry.path_params or entry.fills_client_id:
            extra.append(_SCOPE_KEY)
        if entry.searches_all_regions:
            extra.extend(_REGION_KEYS)
        if getattr(get_origin(ret), "__name__", "") == "AsyncPaginator":
            return self.with_keys(self.model(get_args(ret)[1]), extra)
        if ret is None or ret is type(None):
            self.classes.setdefault("Ok", "class Ok(TypedDict):\n    ok: _b.bool")
            return "Ok"
        rendered = self.render(ret, result=True)
        if extra and rendered in self.classes:
            return self.with_keys(rendered, extra)
        return rendered

    def with_keys(self, base: str, extra: list[tuple[str, str]]) -> str:
        """``base`` plus keys the server adds, as a subclass."""
        if not extra:
            return base
        name = self.reserve(("with", base, tuple(extra)), f"{base}Result")
        if not self.classes[name]:
            lines = [f"class {name}({base}, total=False):"]
            lines += [f"    {key}: {annotation!r}" for key, annotation in extra]
            self.classes[name] = "\n".join(lines)
        return name

    # -------------------------------------------------------------- classes

    def reserve(self, key: Any, base: str) -> str:
        """A class name for ``key``, unique in this stub (recursion-safe)."""
        if key in self.names:
            return self.names[key]
        base = re.sub(r"\W+", "_", base).strip("_") or "Result"
        name, n = base, 2
        while name in self.classes:
            name, n = f"{base}_{n}", n + 1
        self.names[key] = name
        self.classes[name] = ""
        return name

    def model(self, model: Any, variants: list[Any] | None = None) -> str:
        """``TypedDict`` of a response model (or of several, merged)."""
        models = variants or [model]
        key = tuple(models)
        label = "_".join(m.__name__ for m in models[:2])
        if key in self.names:
            return self.names[key]
        name = self.reserve(key, label)
        lines = [f"class {name}(TypedDict, total=False):"]
        seen: set[str] = set()
        for m in models:
            self.namespaces.append(vars(sys.modules.get(m.__module__, types)))
            try:
                for field_name, info in m.model_fields.items():
                    if field_name not in seen:
                        seen.add(field_name)
                        rendered = self.render(info.annotation, result=True)
                        lines.append(f"    {field_name}: {rendered!r}")
            finally:
                self.namespaces.pop()
        if len(lines) == 1:
            lines.append("    pass")
        self.classes[name] = "\n".join(lines)
        return name

    def typeddict(self, td: Any) -> str:
        """An SDK argument ``TypedDict`` (nested arguments), keys required or not."""
        if td in self.names:
            return self.names[td]
        name = self.reserve(td, td.__name__)
        try:
            hints = typing.get_type_hints(td)
        except Exception:
            self.fallbacks += 1
            hints = {}
        required = getattr(td, "__required_keys__", frozenset(hints))
        lines = [f"class {name}(TypedDict):"]
        for key, annotation in hints.items():
            rendered = self.render(annotation, result=False)
            if key not in required:
                rendered = f"NotRequired[{rendered}]"
            lines.append(f"    {key}: {rendered!r}")
        if len(lines) == 1:
            lines.append("    pass")
        self.classes[name] = "\n".join(lines)
        return name

    # ------------------------------------------------------------ rendering

    def render(self, tp: Any, result: bool) -> str:
        """Stub text for a type. ``result``: in a result, ``None`` never occurs."""
        if isinstance(tp, (str, typing.ForwardRef)):
            resolved = self.resolve(tp)
            if resolved is None:
                self.fallbacks += 1
                return "Any"
            tp = resolved
        origin = get_origin(tp)
        if origin is Annotated:
            return self.render(get_args(tp)[0], result)
        if tp is Any or tp is object:
            return "Any"
        if tp is type(None):
            return "None"
        if tp in (str, int, float, bool, bytes):
            return f"_b.{tp.__name__}"
        if tp in (datetime.datetime, datetime.date, datetime.time):
            return "_b.str"  # JSON text, in and out
        if isinstance(tp, type) and issubclass(tp, enum.Enum):
            return "_b.str"
        if origin is Literal:
            return f"Literal[{', '.join(repr(a) for a in get_args(tp))}]"
        if origin is Union or isinstance(tp, types.UnionType):
            return self.union(tp, result)
        if _is_sequence(tp):
            args = get_args(tp)
            return f"_b.list[{self.render(args[0], result) if args else 'Any'}]"
        if _is_mapping(tp):
            args = get_args(tp)
            if len(args) == 2:
                key, value = (self.render(a, result) for a in args)
                return f"_b.dict[{key}, {value}]"
            return "_b.dict[_b.str, Any]"
        if isinstance(tp, type) and issubclass(tp, BaseModel):
            return self.model(tp)
        if is_typeddict(typing.cast(Any, tp)):
            return self.typeddict(tp)
        if isinstance(tp, typing.TypeVar):
            return "Any"
        self.fallbacks += 1
        return "Any"

    def resolve(self, ref: str | typing.ForwardRef) -> Any | None:
        """Evaluate a forward reference where its model was defined."""
        text = ref.__forward_arg__ if isinstance(ref, typing.ForwardRef) else ref
        for namespace in reversed(self.namespaces):
            try:
                return eval(text, dict(vars(typing)), namespace)  # noqa: S307
            except Exception:
                continue
        return None

    def union(self, tp: Any, result: bool) -> str:
        args = [
            a
            for a in get_args(tp)
            if getattr(a, "__name__", "") not in _SENTINELS
            and not (result and a is type(None))
        ]
        models = [_unannotated(a) for a in args]
        models = [m for m in models if isinstance(m, type) and issubclass(m, BaseModel)]
        if result and len(models) > 1 and len(models) == len(args):
            # Variants of one result (e.g. flavors with or without prices):
            # one type with every key, all optional - which is what the data
            # looks like, and lets scripts read any of them without narrowing.
            return self.model(models[0], variants=models)
        rendered = list(dict.fromkeys(self.render(a, result) for a in args))
        return " | ".join(rendered) if rendered else "None"


def _unannotated(tp: Any) -> Any:
    return get_args(tp)[0] if get_origin(tp) is Annotated else tp


def _is_sequence(tp: Any) -> bool:
    origin = get_origin(tp) or tp
    name = getattr(origin, "__name__", "")
    return origin in (list, tuple, set, frozenset) or name in (
        "Iterable",
        "Sequence",
        "List",
        "Set",
        "Tuple",
    )


def _is_mapping(tp: Any) -> bool:
    origin = get_origin(tp) or tp
    return origin is dict or getattr(origin, "__name__", "") in ("Mapping", "Dict")

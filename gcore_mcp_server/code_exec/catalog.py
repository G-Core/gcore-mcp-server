"""SDK catalog: introspection + BM25-ranked search for code-execution mode."""

from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Union, get_args, get_origin

from rank_bm25 import BM25Okapi  # type: ignore[import-untyped]

from gcore_mcp_server.config.settings import generate_short_tool_name
from gcore_mcp_server.config.toolsets import get_raw_toolsets
from gcore_mcp_server.core.inspection import iter_sdk_methods
from gcore_mcp_server.core.schema import normalize_sdk_type_for_mcp


@dataclass(frozen=True)
class ParamInfo:
    """JSON-schema-ish description of a single SDK method parameter."""

    name: str
    type_schema: dict[str, Any]
    required: bool
    default: Any | None


@dataclass(frozen=True)
class ToolEntry:
    """A single SDK method exposed to the catalog."""

    full_name: str
    short_name: str
    doc_short: str
    doc_full: str
    # `list[ParamInfo]` (not bare `list`) is intentional: it is callable and
    # returns an empty list at runtime, while keeping pyright strict mode from
    # reporting `params` as a partially-unknown type.
    params: list[ParamInfo] = field(default_factory=list[ParamInfo])
    toolset: str | None = None
    requires_project: bool = False
    requires_region: bool = False
    # The SDK callable. Host-only — never serialized into the sandbox.
    method: Callable[..., Any] | None = None


# ---------------------------------------------------------------------------
# Tokenization & type mapping helpers
# ---------------------------------------------------------------------------

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_SPLIT_SEPARATORS = re.compile(r"[._\s]+")


def _tokenize(text: str) -> list[str]:
    """Tokenize text on dots, underscores, whitespace and camelCase boundaries.

    Output tokens are lowercased and non-empty.
    """
    if not text:
        return []
    pieces = _SPLIT_SEPARATORS.split(text)
    tokens: list[str] = []
    for piece in pieces:
        if not piece:
            continue
        sub = _CAMEL_BOUNDARY.sub(" ", piece).split()
        for tok in sub:
            tok = tok.lower().strip()
            if tok:
                tokens.append(tok)
    return tokens


def _type_to_schema(annotation: Any) -> dict[str, Any]:
    """Map a normalized Python type annotation to a minimal JSON-schema dict.

    Falls back to ``{"type": "object"}`` for anything not explicitly recognized.
    """
    if annotation is inspect.Parameter.empty or annotation is None:
        return {"type": "object"}

    # Strip Optional / Union wrappers to inspect inner type when possible.
    origin = get_origin(annotation)
    args = get_args(annotation)

    # Unwrap Optional[T] / Union[T, None] / T | None
    try:
        import types as _types

        if origin is Union or origin is _types.UnionType:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return _type_to_schema(non_none[0])
            # Heterogeneous union – fall through to a generic object schema.
            return {"type": "object"}
    except Exception:
        pass

    # Re-fetch origin in case we did not unwrap.
    origin = get_origin(annotation) or annotation

    # Primitive scalars
    if annotation is str or origin is str:
        return {"type": "string"}
    if annotation is bool or origin is bool:
        return {"type": "boolean"}
    if annotation is int or origin is int:
        return {"type": "integer"}
    if annotation is float or origin is float:
        return {"type": "number"}
    if annotation is type(None):
        return {"type": "null"}

    # Containers
    if origin in (list, tuple, set, frozenset):
        return {"type": "array"}
    if origin is dict:
        return {"type": "object"}

    return {"type": "object"}


def _doc_short(doc: str) -> str:
    """Return the first non-empty line of a docstring."""
    if not doc:
        return ""
    for raw in doc.splitlines():
        stripped = raw.strip()
        if stripped:
            return stripped
    return ""


def _toolset_map() -> dict[str, str]:
    """Reverse-index raw toolset definitions: full_name -> toolset name (first match)."""
    out: dict[str, str] = {}
    for toolset_name, members in get_raw_toolsets().items():
        for full_name in members:
            out.setdefault(full_name, toolset_name)
    return out


def _make_entry(
    full_name: str,
    method: Callable[..., Any],
    toolset_map: dict[str, str],
) -> ToolEntry:
    """Build a ``ToolEntry`` from one SDK method."""
    short_name = generate_short_tool_name(full_name)
    doc_full = inspect.getdoc(method) or ""
    doc_first = _doc_short(doc_full)

    requires_project = False
    requires_region = False
    params: list[ParamInfo] = []

    try:
        sig = inspect.signature(method)
    except (TypeError, ValueError):
        sig = None

    if sig is not None:
        try:
            hints = inspect.get_annotations(method, eval_str=True)
        except Exception:
            hints = {}

        for name, param in sig.parameters.items():
            if name in ("self", "cls"):
                continue
            if name == "project_id":
                requires_project = True
            if name == "region_id":
                requires_region = True

            raw_annotation = hints.get(name, param.annotation)
            try:
                normalized = normalize_sdk_type_for_mcp(raw_annotation)
            except Exception:
                normalized = raw_annotation
            schema = _type_to_schema(normalized)

            has_default = param.default is not inspect.Parameter.empty
            # Treat Optional[...] annotations as non-required even without default.
            is_optional_annot = False
            try:
                import types as _types

                origin = get_origin(raw_annotation)
                if origin is Union or origin is _types.UnionType:
                    is_optional_annot = type(None) in get_args(raw_annotation)
            except Exception:
                pass

            required = not has_default and not is_optional_annot

            default_value: Any | None = None
            if has_default:
                d: Any = param.default
                # Replace SDK sentinel defaults with None so the schema is JSON-safe.
                name_attr: str = getattr(
                    type(d),  # pyright: ignore[reportUnknownArgumentType]
                    "__name__",
                    "",
                )
                if name_attr in ("NotGiven", "Omit", "Timeout"):
                    default_value = None
                else:
                    default_value = d

            params.append(
                ParamInfo(
                    name=name,
                    type_schema=schema,
                    required=required,
                    default=default_value,
                )
            )

    toolset = toolset_map.get(full_name)

    return ToolEntry(
        full_name=full_name,
        short_name=short_name,
        doc_short=doc_first,
        doc_full=doc_full,
        params=params,
        toolset=toolset,
        requires_project=requires_project,
        requires_region=requires_region,
        method=method,
    )


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


class Catalog:
    """Searchable view over the introspected SDK methods."""

    def __init__(self, entries: list[ToolEntry]) -> None:
        self.entries: list[ToolEntry] = list(entries)
        self.by_name: dict[str, ToolEntry] = {}
        for entry in self.entries:
            # full_name takes precedence over short_name in case of collision.
            self.by_name[entry.full_name] = entry
        for entry in self.entries:
            if entry.short_name and entry.short_name != entry.full_name:
                self.by_name.setdefault(entry.short_name, entry)

        # Build BM25 over per-entry documents.
        self._tokenized_docs: list[list[str]] = [
            _tokenize(
                " ".join(
                    [
                        entry.full_name,
                        entry.short_name,
                        " ".join(p.name for p in entry.params),
                        entry.doc_short,
                    ]
                )
            )
            for entry in self.entries
        ]
        # rank-bm25 requires at least one document; guard the empty case.
        if self._tokenized_docs and any(self._tokenized_docs):
            # Replace any fully-empty doc with a single placeholder token so
            # BM25Okapi does not error on zero-length input.
            safe_docs = [d if d else ["_empty_"] for d in self._tokenized_docs]
            self._bm25: BM25Okapi | None = BM25Okapi(safe_docs)
        else:
            self._bm25 = None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Return top ``limit`` catalog entries ranked against ``query``.

        Each result is a small dict: ``name``, ``short_doc``, ``toolset``,
        ``requires_project``, ``requires_region``.
        """
        if not self.entries:
            return []

        query_tokens = _tokenize(query)
        if self._bm25 is None or not query_tokens:
            # Fall back to a deterministic order if BM25 cannot score.
            ranked_indices = list(range(min(limit, len(self.entries))))
            return [self._summary(self.entries[i]) for i in ranked_indices]

        # rank-bm25 is untyped; coerce its numpy output to plain floats.
        raw_scores = self._bm25.get_scores(query_tokens)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        scores: list[float] = [
            float(s)  # pyright: ignore[reportUnknownArgumentType]
            for s in raw_scores  # pyright: ignore[reportUnknownVariableType]
        ]

        for idx, entry in enumerate(self.entries):
            full_tokens = _tokenize(entry.full_name)
            short_tokens = _tokenize(entry.short_name)
            name_tokens = set(full_tokens) | set(short_tokens)
            if name_tokens & set(query_tokens):
                scores[idx] += 0.5
            # Exact prefix match on either name.
            q_lower = query.strip().lower()
            if q_lower and (
                entry.full_name.lower().startswith(q_lower)
                or entry.short_name.lower().startswith(q_lower)
            ):
                scores[idx] += 1.0
            if entry.toolset and entry.toolset.lower() in query_tokens:
                scores[idx] += 0.3

        # Stable sort by descending score.
        ordered = sorted(
            range(len(self.entries)),
            key=lambda i: (-scores[i], self.entries[i].full_name),
        )
        top = ordered[: max(0, int(limit))]
        return [self._summary(self.entries[i]) for i in top]

    @staticmethod
    def _summary(entry: ToolEntry) -> dict[str, Any]:
        return {
            "name": entry.full_name,
            "short_doc": entry.doc_short,
            "toolset": entry.toolset,
            "requires_project": entry.requires_project,
            "requires_region": entry.requires_region,
        }

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def get_schema(self, name: str) -> dict[str, Any]:
        """Return a JSON-schema-ish description of one SDK method.

        Raises ``KeyError`` if ``name`` is not in the catalog.
        """
        entry = self.by_name.get(name)
        if entry is None:
            raise KeyError(
                f"unknown tool: {name!r}. Try search_tools(query) to discover."
            )
        return {
            "name": entry.full_name,
            "doc": entry.doc_full,
            "params": [
                {
                    "name": p.name,
                    "type": p.type_schema,
                    "required": p.required,
                    "default": p.default,
                }
                for p in entry.params
            ],
            "requires_project": entry.requires_project,
            "requires_region": entry.requires_region,
        }


def build_catalog(client: Any) -> Catalog:
    """Walk the SDK and build a searchable ``Catalog``."""
    toolset_map = _toolset_map()
    entries = [
        _make_entry(full_name, method, toolset_map)
        for full_name, method in iter_sdk_methods(client)
    ]
    return Catalog(entries)

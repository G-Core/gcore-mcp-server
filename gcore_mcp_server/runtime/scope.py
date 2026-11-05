"""Cloud project and region when the user hasn't fixed them.

Only ``GCORE_API_KEY`` is required. Cloud operations live under a project and a
region, and people work across several of both, so the server fills them in
per call instead of requiring ``GCORE_CLOUD_PROJECT_ID``/``GCORE_CLOUD_REGION_ID``:

* **Project** - when a call omits ``project_id``, the account's default project
  is used (or its only project), and the result says so. Destructive calls never
  get a project filled in: the model must name it.
* **Region** - when a ``list`` call omits ``region_id``, every active region is
  searched in parallel and the results are merged. Any other call, and a list
  inside one resource (``instances.interfaces.list``), needs an explicit
  region; the error lists the regions to choose from.

The environment variables still pin a project and/or region for users who want
the server scoped to one; then nothing here applies to that parameter.

The lookups respect the deny-list: when ``cloud.projects.list`` (or
``cloud.regions.list``) is denied, nothing is looked up and the parameter must
be passed explicitly.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, cast

from fastmcp.exceptions import ToolError

from gcore_mcp_server.catalog import Access, ToolEntry

from .shaping import describe_error

logger = logging.getLogger(__name__)

CACHE_TTL_SECS = 300.0
FANOUT_CONCURRENCY = 8
FANOUT_VERBS = frozenset({"list"})
PAGE_SIZE = 1000


@dataclass(frozen=True)
class Project:
    id: int
    name: str
    is_default: bool
    client_id: int | None = None


@dataclass(frozen=True)
class Region:
    id: int
    name: str


@dataclass
class Scoped:
    """How :meth:`CloudScope.resolve` adjusted one call."""

    args: dict[str, Any]
    fan_out: list[Region] | None = None
    note: dict[str, Any] | None = None


def _never_denied(_name: str) -> bool:
    return False


class CloudScope:
    """Fills in project/region per call; caches the account's lists briefly."""

    def __init__(self, client: Any, is_denied: Callable[[str], bool] | None = None):
        self.client = client
        self.is_denied: Callable[[str], bool] = is_denied or _never_denied
        self._lock = asyncio.Lock()
        self._projects: tuple[float, list[Project]] | None = None
        self._regions: tuple[float, list[Region]] | None = None

    # ------------------------------------------------------------ account data

    @property
    def pinned_project(self) -> int | None:
        return getattr(self.client, "cloud_project_id", None)

    @property
    def pinned_region(self) -> int | None:
        return getattr(self.client, "cloud_region_id", None)

    async def projects(self) -> list[Project]:
        async with self._lock:
            if self._projects and time.monotonic() - self._projects[0] < CACHE_TTL_SECS:
                return self._projects[1]
            # Iterate every page: the default project may not be on the first.
            projects = [
                Project(
                    int(p.id),
                    str(p.name),
                    bool(getattr(p, "is_default", False)),
                    _int_or_none(getattr(p, "client_id", None)),
                )
                async for p in self.client.cloud.projects.list(limit=PAGE_SIZE)
                if getattr(p, "state", "ACTIVE") != "DELETED"
            ]
            self._projects = (time.monotonic(), projects)
            return projects

    async def regions(self) -> list[Region]:
        async with self._lock:
            if self._regions and time.monotonic() - self._regions[0] < CACHE_TTL_SECS:
                return self._regions[1]
            regions = [
                Region(int(r.id), str(getattr(r, "display_name", None) or r.id))
                async for r in self.client.cloud.regions.list(limit=PAGE_SIZE)
                if getattr(r, "state", "ACTIVE") == "ACTIVE"
            ]
            self._regions = (time.monotonic(), regions)
            return regions

    @staticmethod
    async def _lookup(entry: ToolEntry, param: str, name: str, fetch: Any) -> Any:
        """Run a project/region lookup; failures read like any other API error."""
        try:
            return await fetch()
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError(
                f"{entry.name} needs {param}, and looking it up failed. "
                f"{describe_error(exc, name)}"
            ) from exc

    # ----------------------------------------------------------------- resolve

    async def resolve(self, entry: ToolEntry, args: dict[str, Any]) -> Scoped:
        params = entry.path_params
        missing_project = (
            "project_id" in params
            and args.get("project_id") is None
            and self.pinned_project is None
        )
        missing_region = (
            "region_id" in params
            and args.get("region_id") is None
            and self.pinned_region is None
        )
        missing_client = entry.fills_client_id and args.get("client_id") is None
        if not (missing_project or missing_region or missing_client):
            return Scoped(args)

        for missing, param, lookup in (
            (missing_project, "project_id", "cloud.projects.list"),
            (missing_region, "region_id", "cloud.regions.list"),
            (missing_client, "client_id", "cloud.projects.list"),
        ):
            if missing and self.is_denied(lookup):
                raise ToolError(
                    f"{entry.name} needs {param}. It can't be filled in automatically "
                    f"because {lookup} is denied (GCORE_DENY_TOOLS); pass it "
                    "explicitly, or ask the user for it."
                )

        args = dict(args)
        note: dict[str, Any] = {}
        if missing_client:
            projects = await self._lookup(
                entry, "client_id", "cloud.projects.list", self.projects
            )
            clients = sorted({p.client_id for p in projects if p.client_id is not None})
            if entry.access is Access.DESTRUCTIVE or len(clients) != 1:
                why = (
                    "This operation is destructive, so it must be named explicitly."
                    if entry.access is Access.DESTRUCTIVE
                    else "It can't be determined from the account's projects."
                )
                raise ToolError(
                    f"{entry.name} needs client_id. {why} The account's client "
                    f"ID{'s' if len(clients) != 1 else ''}: "
                    f"{', '.join(map(str, clients)) or 'unknown'}."
                )
            args["client_id"] = clients[0]
            note["client_id"] = clients[0]
        if missing_project:
            projects = await self._lookup(
                entry, "project_id", "cloud.projects.list", self.projects
            )
            chosen = self._default_project(projects)
            if entry.access is Access.DESTRUCTIVE or chosen is None:
                raise ToolError(self._project_error(entry, projects))
            args["project_id"] = chosen.id
            note["project"] = {"id": chosen.id, "name": chosen.name}
            if len(projects) > 1:
                note["project_note"] = (
                    f"Default project used; the account has {len(projects)} "
                    "projects. Pass project_id for another."
                )

        if missing_region:
            regions = await self._lookup(
                entry, "region_id", "cloud.regions.list", self.regions
            )
            if (
                entry.access is Access.READ
                and entry.name.rsplit(".", 1)[-1] in FANOUT_VERBS
                and not self._needs_other_ids(entry)
            ):
                return Scoped(args, fan_out=regions, note=note)
            raise ToolError(self._region_error(entry, regions))
        return Scoped(args, note=note or None)

    @staticmethod
    def _needs_other_ids(entry: ToolEntry) -> bool:
        """A list inside one resource (``instances.interfaces.list(instance_id)``).

        That resource lives in one region, so searching every region would only
        add a "not found" from each of the others: ask for the region instead.
        """
        try:
            params = inspect.signature(entry.fn).parameters.values()
        except (TypeError, ValueError):
            return False
        return any(
            p.default is inspect.Parameter.empty
            and p.name not in ("project_id", "region_id")
            for p in params
        )

    @staticmethod
    def _default_project(projects: list[Project]) -> Project | None:
        for p in projects:
            if p.is_default:
                return p
        return projects[0] if len(projects) == 1 else None

    @staticmethod
    def _project_error(entry: ToolEntry, projects: list[Project]) -> str:
        listed = ", ".join(
            f"{p.id} ({p.name}{', default' if p.is_default else ''})" for p in projects
        )
        why = (
            "This operation is destructive, so the project must be named explicitly."
            if entry.access is Access.DESTRUCTIVE
            else "The account has no default project."
        )
        return (
            f"{entry.name} needs project_id. {why} Projects: {listed or 'none'}. "
            "Use the one the user means; if unclear, ask them."
        )

    @staticmethod
    def _region_error(entry: ToolEntry, regions: list[Region]) -> str:
        listed = ", ".join(f"{r.id} ({r.name})" for r in regions)
        return (
            f"{entry.name} needs region_id. Active regions: {listed}. Use the region "
            "the resource is in (list operations without region_id search all "
            "regions and show each item's region); if unclear, ask the user."
        )


def _api_reason(exc: BaseException) -> str:
    """The API's own explanation of a failure (its ``title``/``detail``)."""
    for err in (exc, exc.__cause__):
        body = getattr(err, "body", None)
        if isinstance(body, dict):
            body_dict = cast(dict[str, Any], body)
            for key in ("detail", "title", "message"):
                if isinstance(body_dict.get(key), str) and body_dict[key]:
                    return body_dict[key]
    return (str(exc).splitlines() or [""])[0][:160]


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _not_available(exc: BaseException) -> bool:
    message = str(exc)
    return '"not-available"' in message or "not available in this region" in message


def merge_region_results(
    per_region: list[tuple[Region, Any | BaseException]],
) -> dict[str, Any]:
    """Combine one list call per region into a single result."""
    results: list[Any] = []
    failed: dict[str, str] = {}
    unavailable: list[str] = []
    unavailable_reason = ""
    total = 0  # the API's own totals, which count items beyond the first page
    capped: list[str] = []
    for region, data in per_region:
        if isinstance(data, BaseException) and _not_available(data):
            # Service not offered in this region (or not enabled for the
            # account): nothing to find there, not an error worth reporting.
            unavailable.append(f"{region.id} ({region.name})")
            unavailable_reason = unavailable_reason or _api_reason(data)
            continue
        if isinstance(data, BaseException):
            failed[f"{region.id} ({region.name})"] = _api_reason(data)
            continue
        value: Any = data
        items: Any = (
            cast(dict[str, Any], value).get("results")
            if isinstance(value, dict)
            else value
        )
        if not isinstance(items, list):
            items = [value]
        api_count = (
            cast(dict[str, Any], value).get("count")
            if isinstance(value, dict)
            else None
        )
        n = len(cast(list[Any], items))
        total += api_count if isinstance(api_count, int) and api_count > n else n
        if isinstance(api_count, int) and api_count > n:
            capped.append(f"{region.id} ({region.name}): {n} of {api_count}")
        item: Any
        for item in cast(list[Any], items):
            if isinstance(item, dict) and "region_id" not in item:
                item = {"region_id": region.id, **cast(dict[str, Any], item)}
            results.append(item)
    merged: dict[str, Any] = {
        "count": total,
        "results": results,
        "regions_searched": len(per_region) - len(failed) - len(unavailable),
    }
    if capped:
        merged["incomplete"] = {
            "note": f"{len(results)} of {total} items returned: some regions have "
            "more than one page. Call again with that region_id and limit/offset "
            "for the rest.",
            "regions": capped,
        }
    if unavailable:
        # Not a gap in the results: the service isn't offered there, so there
        # is nothing to find. Say so in the API's words, or models read a bare
        # count as "regions could not be reached".
        merged["regions_without_service"] = {
            "regions": unavailable,
            "api_says": unavailable_reason,
            "note": "Nothing to find there; these regions are not missing from "
            "the results.",
        }
    if failed:
        merged["regions_failed"] = failed
    return merged


async def gather_regions(
    regions: list[Region], call: Any
) -> list[tuple[Region, Any | BaseException]]:
    """Run ``call(region)`` for every region with bounded concurrency."""
    sem = asyncio.Semaphore(FANOUT_CONCURRENCY)

    async def one(region: Region) -> tuple[Region, Any | BaseException]:
        async with sem:
            try:
                return region, await call(region)
            except Exception as exc:  # one region failing must not fail the rest
                return region, exc

    return list(await asyncio.gather(*(one(r) for r in regions)))

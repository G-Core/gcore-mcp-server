"""Live-test settings, read from the environment only (never printed).

* ``GCORE_LIVE_API_KEY`` - API key of a test account.
* ``GCORE_LIVE_PROJECT_ID`` / ``GCORE_LIVE_REGION_ID`` - where test resources
  are created.
* ``GCORE_LIVE_RESTRICTED_API_KEY`` (optional) - a key without write access,
  for the permission-error test.

Live tests skip unless the first three are set (e.g. in CI).
"""

from __future__ import annotations

import os


def live_api_key() -> str | None:
    return os.getenv("GCORE_LIVE_API_KEY") or None


def restricted_api_key() -> str | None:
    return os.getenv("GCORE_LIVE_RESTRICTED_API_KEY") or None


def live_location() -> tuple[int, int] | None:
    project, region = (
        os.getenv("GCORE_LIVE_PROJECT_ID"),
        os.getenv("GCORE_LIVE_REGION_ID"),
    )
    if not (project and region):
        return None
    return int(project), int(region)


def live_configured() -> bool:
    return bool(live_api_key()) and live_location() is not None

"""The live scenario files parse and only use known settings (no API calls)."""

from __future__ import annotations

import string

import pytest

from tests.live.run_scenarios import (
    FIXTURES,
    HARNESSES,
    HTTP_HARNESSES,
    OPTIONAL,
    Scenario,
    load_all,
)

KNOWN = {
    "project_id",
    "region_id",
    "prefix",
    "short",
    "month",
    "prev_month",
    *(v for v in OPTIONAL.values() if v != "restricted_key"),  # a key, not text
}
NEEDED = {v: k for k, v in OPTIONAL.items()}
SCENARIOS = load_all()


def test_there_are_core_and_extended_scenarios() -> None:
    tiers = [s.tier for s in SCENARIOS]
    assert tiers.count("core") >= 10 and "extended" in tiers


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_scenario_is_well_formed(scenario: Scenario) -> None:
    assert scenario.tier in ("core", "extended")
    assert scenario.harnesses and set(scenario.harnesses) <= set(HARNESSES)
    if scenario.transport != "http":  # limit harnesses only when one can't run it
        assert scenario.harnesses == list(HARNESSES)
    assert scenario.passing.startswith("- ")
    assert scenario.fixture in (None, *FIXTURES)
    used = {f for _, f, _, _ in string.Formatter().parse(scenario.prompt) if f}
    assert used <= KNOWN, used - KNOWN
    for name in used & set(NEEDED):
        assert NEEDED[name] in scenario.needs, f"declare needs: {NEEDED[name]}"
    if scenario.fixture == "duplicate_vms":
        assert "GCORE_LIVE_REGION2_ID" in scenario.needs
    assert scenario.key in ("live", "restricted")
    if scenario.key == "restricted":
        assert "GCORE_LIVE_RESTRICTED_API_KEY" in scenario.needs
    if scenario.transport == "http":
        assert set(scenario.harnesses) <= set(HTTP_HARNESSES)

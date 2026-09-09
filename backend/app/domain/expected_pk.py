"""Expected (planning) vs observed (post-study) PK parameters.

Expected Tmax / t½ are planning inputs for sampling / washout design.
Observed Tmax is a study PK endpoint after concentrations are available.
Never invent either. Never treat observed Cmax-time as a planning input.
"""

from __future__ import annotations

from typing import Any

# Planning (pre-study) field paths — only VERIFIED values may unblock engines
EXPECTED_TMAX_FIELDS: tuple[str, ...] = (
    "pk.expected_tmax",
    "pk.Tmax",  # legacy verified planning Tmax from SmPC / research
    "tmax",
)

EXPECTED_HALF_LIFE_FIELDS: tuple[str, ...] = (
    "pk.expected_t_half",
    "pk.t_half",
    "half_life",
)

# Post-study / derived — never used to design sampling
OBSERVED_TMAX_FIELDS: tuple[str, ...] = (
    "pk.observed_tmax",
    "pk.observed_Tmax",
    "results.tmax",
)


def resolve_verified_expected_tmax(
    facts: dict[str, Any],
    statuses: dict[str, str],
) -> Any:
    """Return verified expected (planning) Tmax or None. Does not invent."""
    for key in EXPECTED_TMAX_FIELDS:
        if statuses.get(key) == "VERIFIED" and facts.get(key) is not None:
            return facts[key]
    return None


def resolve_verified_expected_half_life(
    facts: dict[str, Any],
    statuses: dict[str, str],
) -> Any:
    for key in EXPECTED_HALF_LIFE_FIELDS:
        if statuses.get(key) == "VERIFIED" and facts.get(key) is not None:
            return facts[key]
    return None


def tmax_role_note() -> dict[str, str]:
    return {
        "expected_tmax": (
            "Planning input from SmPC / literature / research — used to design sampling "
            "around anticipated Cmax. Requires expert VERIFIED before sampling engine uses it."
        ),
        "observed_tmax": (
            "Post-study PK parameter derived from concentration–time data. "
            "Not a substitute for expected_tmax when designing the schedule."
        ),
    }

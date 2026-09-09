"""Versioned PK / washout / observation / sampling rule catalog.

Practical workflow multipliers are stored as PROPOSED rules — not VERIFIED norms.
Verified regulatory sources must be attached before Production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DomainRule:
    rule_id: str
    expression: str
    parameters: dict[str, Any]
    source: str
    version: str
    status: str  # VERIFIED | PROPOSED | NEEDS_REVIEW


PK_RULES_VERSION = "1"

# Observation ≈ half_life_max * N  (practical / template-derived — PROPOSED)
RULE_OBS_HALF_LIFE_MULTIPLIER = DomainRule(
    rule_id="PK.OBS.THALF_MULT.v1",
    expression="observation_min_h = half_life_max_h * multiplier",
    parameters={"multiplier": 3.0},
    source="TEMPLATE_COMMENT / practical workflow — not verified regulatory",
    version="1",
    status="PROPOSED",
)

# Washout ≈ half_life_max * N days equivalent
RULE_WASHOUT_HALF_LIFE_MULTIPLIER = DomainRule(
    rule_id="PK.WASHOUT.THALF_MULT.v1",
    expression="washout_min_h = half_life_max_h * multiplier",
    parameters={"multiplier": 5.0},
    source="TEMPLATE_COMMENT / practical workflow — not verified regulatory",
    version="1",
    status="PROPOSED",
)

# Sampling density configuration (algorithmic — not fixed point counts)
RULE_SAMPLING_DENSITY = DomainRule(
    rule_id="PK.SAMP.DENSITY.v1",
    expression=(
        "capture_window = [tmax_min*(1-pre_margin), tmax_max*(1+post_margin)]; "
        "tmax_interval = max(min_interval_h, window_span * tmax_interval_fraction); "
        "require >= min_points_in_capture_window inside capture_window; "
        "post_interval grows after tmax; terminal uses terminal_interval_h"
    ),
    parameters={
        "absorb_span_factor": 2.0,
        "min_interval_h": 0.25,
        "tmax_pre_margin_fraction": 0.25,
        "tmax_post_margin_fraction": 0.25,
        "tmax_interval_fraction": 0.25,
        "min_points_in_capture_window": 2,
        "post_interval_start_h": 0.5,
        "post_interval_growth": 1.5,
        "terminal_interval_h": 2.0,
        "terminal_start_fraction_of_obs": 0.6,
        "default_window_before_min": 5.0,
        "default_window_after_min": 5.0,
        "tmax_window_before_min": 2.0,
        "tmax_window_after_min": 2.0,
    },
    source=(
        "Configurable sampling density algorithm (SPEC §25–27) — "
        "margin fractions are PROPOSED workflow parameters, not verified regulatory norms"
    ),
    version="1",
    status="PROPOSED",
)

RULE_CROSSOVER_REQUIRES_WASHOUT = DomainRule(
    rule_id="PK.WASHOUT.CROSSOVER_REQUIRED.v1",
    expression="if design in crossover/replicate families then washout required",
    parameters={
        "designs_requiring_washout": [
            "CROSSOVER_2X2",
            "REPLICATE_2X2X4",
        ]
    },
    source="Design logic — washout between periods",
    version="1",
    status="PROPOSED",
)

ALL_PK_RULES: tuple[DomainRule, ...] = (
    RULE_OBS_HALF_LIFE_MULTIPLIER,
    RULE_WASHOUT_HALF_LIFE_MULTIPLIER,
    RULE_SAMPLING_DENSITY,
    RULE_CROSSOVER_REQUIRES_WASHOUT,
)


def get_rule(rule_id: str) -> DomainRule:
    for rule in ALL_PK_RULES:
        if rule.rule_id == rule_id:
            return rule
    raise KeyError(rule_id)


def result_status_for_rules(rule_ids: list[str]) -> str:
    """If any applied rule is not VERIFIED → PROPOSED (or NEEDS_REVIEW if any NEEDS_REVIEW)."""
    statuses = []
    for rid in rule_ids:
        try:
            statuses.append(get_rule(rid).status)
        except KeyError:
            statuses.append("NEEDS_REVIEW")
    if any(s == "NEEDS_REVIEW" for s in statuses):
        return "NEEDS_REVIEW"
    if all(s == "VERIFIED" for s in statuses) and statuses:
        return "CALCULATED"
    return "PROPOSED"

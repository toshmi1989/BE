"""Versioned statistical defaults and rounding — no hidden UI magic numbers."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class DomainRule:
    rule_id: str
    expression: str
    parameters: dict
    source: str
    version: str
    status: str


STATS_RULES_VERSION = "1"
SAMPLE_SIZE_ALGORITHM_2X2 = "BE_TOST_2X2_NCT.v1"
POOLING_ALGORITHM_IVW = "CV_POOL_IVW_LOG.v1"

RULE_STAT_DEFAULTS = DomainRule(
    rule_id="STAT.DEFAULTS.ABE.v1",
    expression="alpha=0.05; power=0.80; BE=[0.80,1.25]; expected_ratio=1.0; log-transform",
    parameters={
        "alpha": 0.05,
        "power": 0.80,
        "be_lower": 0.80,
        "be_upper": 1.25,
        "expected_ratio": 1.0,
        "transformation": "LN",
        "analysis_method": "ANOVA_TOST_90CI",
    },
    source="Configurable ABE defaults (SPEC §35) — attach verified regulatory source before Production",
    version="1",
    status="PROPOSED",
)

RULE_ROUNDING_2X2 = DomainRule(
    rule_id="STAT.ROUND.2X2_EVEN.v1",
    expression="evaluable_n = smallest even integer >= raw_n; randomized/screened via reserve policy then even",
    parameters={"parity": "even", "mode": "ceil"},
    source="Balanced 2×2 sequence allocation convention",
    version="1",
    status="PROPOSED",
)

RULE_CV_ABS_MAX = DomainRule(
    rule_id="STAT.CV.ABS_MAX.v1",
    expression="0 < cv_value < abs_max",
    parameters={"abs_max_percent": 200.0},
    source="Mathematical sanity bound — not a clinical rule",
    version="1",
    status="PROPOSED",
)


@dataclass(frozen=True)
class RoundingPolicy:
    rule_id: str
    parity: str  # even | none
    mode: str  # ceil

    def round_n(self, value: float) -> int:
        if value <= 0:
            raise ValueError("N must be positive before rounding")
        n = int(ceil(value - 1e-12))
        if self.parity == "even" and n % 2 == 1:
            n += 1
        return n


ROUNDING_2X2 = RoundingPolicy(
    rule_id=RULE_ROUNDING_2X2.rule_id,
    parity=str(RULE_ROUNDING_2X2.parameters["parity"]),
    mode=str(RULE_ROUNDING_2X2.parameters["mode"]),
)

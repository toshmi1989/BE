"""Subject reserve / dropout — separate from statistical evaluable N."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import ValidationError
from app.domain.stats_rules import ROUNDING_2X2, RoundingPolicy


@dataclass
class ReserveInput:
    evaluable_n: int
    dropout_pct: float = 0.0
    reserve_pct: float = 0.0
    screen_failure_pct: float = 0.0
    rounding: RoundingPolicy = ROUNDING_2X2


@dataclass
class ReserveResult:
    evaluable_n: int
    randomized_n: int
    screened_n: int
    formula: str
    rationale: str
    rule_id: str


def apply_subject_reserve(inp: ReserveInput) -> ReserveResult:
    if inp.evaluable_n <= 0:
        raise ValidationError("evaluable_n must be > 0", field="evaluable_n")
    for name, val in (
        ("dropout_pct", inp.dropout_pct),
        ("reserve_pct", inp.reserve_pct),
        ("screen_failure_pct", inp.screen_failure_pct),
    ):
        if val < 0 or val >= 100:
            raise ValidationError(f"{name} must be in [0, 100)", field=name)

    # randomized = evaluable / (1 - dropout/100) * (1 + reserve/100)
    drop = inp.dropout_pct / 100.0
    reserve = inp.reserve_pct / 100.0
    screen = inp.screen_failure_pct / 100.0
    raw_rand = inp.evaluable_n / (1.0 - drop) * (1.0 + reserve)
    randomized = inp.rounding.round_n(raw_rand)
    raw_screen = randomized / (1.0 - screen) if screen < 1 else randomized
    screened = inp.rounding.round_n(raw_screen)

    formula = (
        "randomized_n = round_policy(evaluable_n / (1 - dropout_pct/100) * (1 + reserve_pct/100)); "
        "screened_n = round_policy(randomized_n / (1 - screen_failure_pct/100))"
    )
    rationale = (
        f"evaluable={inp.evaluable_n}; dropout={inp.dropout_pct}%; reserve={inp.reserve_pct}%; "
        f"screen_fail={inp.screen_failure_pct}%; rounding={inp.rounding.rule_id}"
    )
    return ReserveResult(
        evaluable_n=inp.evaluable_n,
        randomized_n=randomized,
        screened_n=screened,
        formula=formula,
        rationale=rationale,
        rule_id=inp.rounding.rule_id,
    )

"""Half-life dependent calculations (observation / washout minima)."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import ValidationError
from app.domain.pk_rules import (
    RULE_OBS_HALF_LIFE_MULTIPLIER,
    RULE_WASHOUT_HALF_LIFE_MULTIPLIER,
    result_status_for_rules,
)
from app.domain.units import TimeUnit, to_hours


@dataclass
class HalfLifeInputs:
    half_life_min: float | None
    half_life_max: float | None
    half_life_unit: str = TimeUnit.H.value
    design_type: str | None = None


@dataclass
class HalfLifeDependentResult:
    observation_minimum_h: float | None
    washout_minimum_h: float | None
    recommended_observation_h: float | None
    recommended_washout_h: float | None
    rationale: str
    rule_ids: list[str]
    status: str


def calculate_half_life_dependent_values(inp: HalfLifeInputs) -> HalfLifeDependentResult:
    if inp.half_life_min is None and inp.half_life_max is None:
        raise ValidationError("half_life_min or half_life_max required", field="half_life")

    hl_max = inp.half_life_max if inp.half_life_max is not None else inp.half_life_min
    hl_min = inp.half_life_min if inp.half_life_min is not None else inp.half_life_max
    assert hl_max is not None and hl_min is not None

    if hl_min <= 0 or hl_max <= 0:
        raise ValidationError("half-life values must be > 0", field="half_life")
    if hl_min > hl_max:
        raise ValidationError("half_life_min must be <= half_life_max", field="half_life_min")

    hl_max_h = to_hours(hl_max, inp.half_life_unit)
    obs_mult = float(RULE_OBS_HALF_LIFE_MULTIPLIER.parameters["multiplier"])
    wo_mult = float(RULE_WASHOUT_HALF_LIFE_MULTIPLIER.parameters["multiplier"])

    obs_min = hl_max_h * obs_mult
    wo_min = hl_max_h * wo_mult
    rule_ids = [
        RULE_OBS_HALF_LIFE_MULTIPLIER.rule_id,
        RULE_WASHOUT_HALF_LIFE_MULTIPLIER.rule_id,
    ]
    status = result_status_for_rules(rule_ids)

    rationale = (
        f"Using half_life_max={hl_max_h:g} h; "
        f"observation_min = {obs_mult:g}×t½ ({RULE_OBS_HALF_LIFE_MULTIPLIER.rule_id}, "
        f"status={RULE_OBS_HALF_LIFE_MULTIPLIER.status}); "
        f"washout_min = {wo_mult:g}×t½ ({RULE_WASHOUT_HALF_LIFE_MULTIPLIER.rule_id}, "
        f"status={RULE_WASHOUT_HALF_LIFE_MULTIPLIER.status}). "
        "Not auto-verified regulatory norms."
    )

    return HalfLifeDependentResult(
        observation_minimum_h=obs_min,
        washout_minimum_h=wo_min,
        recommended_observation_h=obs_min,
        recommended_washout_h=wo_min,
        rationale=rationale,
        rule_ids=rule_ids,
        status=status,
    )

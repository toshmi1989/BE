"""Observation duration plan."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import ValidationError
from app.domain.half_life import HalfLifeInputs, calculate_half_life_dependent_values
from app.domain.units import TimeUnit, to_hours


@dataclass
class ObservationCalcInput:
    half_life_min: float | None
    half_life_max: float | None
    half_life_unit: str = TimeUnit.H.value
    selected_duration: float | None = None
    selected_unit: str = TimeUnit.H.value
    manual_override: bool = False


@dataclass
class ObservationCalcResult:
    calculated_minimum_h: float | None
    selected_duration_h: float | None
    final_sampling_time_h: float | None
    unit: str
    rule_ids: list[str]
    rationale: str
    status: str
    issues: list[dict]


def calculate_observation(inp: ObservationCalcInput) -> ObservationCalcResult:
    if inp.half_life_min is None and inp.half_life_max is None:
        raise ValidationError("half-life required for observation calculation", field="half_life")

    hl = calculate_half_life_dependent_values(
        HalfLifeInputs(
            half_life_min=inp.half_life_min,
            half_life_max=inp.half_life_max,
            half_life_unit=inp.half_life_unit,
        )
    )
    assert hl.observation_minimum_h is not None
    issues: list[dict] = []
    selected_h = None
    if inp.selected_duration is not None:
        if inp.selected_duration <= 0:
            raise ValidationError("selected_duration must be > 0", field="selected_duration")
        selected_h = to_hours(inp.selected_duration, inp.selected_unit)
        if selected_h < hl.observation_minimum_h:
            issues.append(
                {
                    "severity": "CRITICAL",
                    "code": "OBSERVATION_BELOW_MINIMUM",
                    "message": (
                        f"selected duration {selected_h:g} h < "
                        f"calculated minimum {hl.observation_minimum_h:g} h"
                    ),
                    "field": "selected_duration",
                }
            )

    status = "NEEDS_REVIEW" if issues else hl.status
    if inp.manual_override and not issues:
        status = "PROPOSED"

    return ObservationCalcResult(
        calculated_minimum_h=hl.observation_minimum_h,
        selected_duration_h=selected_h,
        final_sampling_time_h=selected_h if selected_h is not None else hl.recommended_observation_h,
        unit=TimeUnit.H.value,
        rule_ids=hl.rule_ids,
        rationale=hl.rationale,
        status=status,
        issues=issues,
    )

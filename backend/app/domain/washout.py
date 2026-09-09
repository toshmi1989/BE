"""Washout plan calculation and validation."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import ValidationError
from app.domain.half_life import HalfLifeInputs, calculate_half_life_dependent_values
from app.domain.pk_rules import RULE_CROSSOVER_REQUIRES_WASHOUT, result_status_for_rules
from app.domain.units import TimeUnit, convert_time, to_hours


@dataclass
class WashoutCalcInput:
    half_life_min: float | None
    half_life_max: float | None
    half_life_unit: str = TimeUnit.H.value
    design_type: str | None = None
    selected_value: float | None = None
    selected_unit: str = TimeUnit.DAY.value
    manual_override: bool = False


@dataclass
class WashoutCalcResult:
    calculated_minimum: float | None
    calculated_unit: str
    selected_value: float | None
    selected_unit: str
    requires_washout: bool
    rule_ids: list[str]
    rationale: str
    status: str
    critical_issues: list[dict]


def calculate_washout(inp: WashoutCalcInput) -> WashoutCalcResult:
    designs_req = list(RULE_CROSSOVER_REQUIRES_WASHOUT.parameters["designs_requiring_washout"])
    requires = inp.design_type in designs_req if inp.design_type else False

    # Parallel must not auto-require washout
    if inp.design_type == "PARALLEL":
        requires = False

    critical: list[dict] = []
    rule_ids = [RULE_CROSSOVER_REQUIRES_WASHOUT.rule_id]

    if not requires:
        return WashoutCalcResult(
            calculated_minimum=None,
            calculated_unit=TimeUnit.DAY.value,
            selected_value=inp.selected_value,
            selected_unit=inp.selected_unit,
            requires_washout=False,
            rule_ids=rule_ids,
            rationale="Design does not require inter-period washout (e.g. PARALLEL).",
            status=result_status_for_rules(rule_ids),
            critical_issues=[],
        )

    if inp.half_life_min is None and inp.half_life_max is None:
        raise ValidationError(
            "half-life required to calculate washout for crossover/replicate design",
            field="half_life",
        )

    hl = calculate_half_life_dependent_values(
        HalfLifeInputs(
            half_life_min=inp.half_life_min,
            half_life_max=inp.half_life_max,
            half_life_unit=inp.half_life_unit,
            design_type=inp.design_type,
        )
    )
    rule_ids.extend(hl.rule_ids)
    assert hl.washout_minimum_h is not None
    calc_days = convert_time(hl.washout_minimum_h, TimeUnit.H, TimeUnit.DAY)

    selected = inp.selected_value
    if selected is not None:
        if selected <= 0:
            raise ValidationError("selected washout must be > 0", field="selected_value")
        selected_h = to_hours(selected, inp.selected_unit)
        if selected_h < hl.washout_minimum_h:
            critical.append(
                {
                    "severity": "CRITICAL",
                    "code": "WASHOUT_BELOW_MINIMUM",
                    "message": (
                        f"selected washout {selected} {inp.selected_unit} "
                        f"< calculated minimum {calc_days:g} day"
                    ),
                    "field": "selected_value",
                }
            )

    status = "NEEDS_REVIEW" if critical else result_status_for_rules(rule_ids)
    if inp.manual_override and not critical:
        status = "PROPOSED"

    return WashoutCalcResult(
        calculated_minimum=calc_days,
        calculated_unit=TimeUnit.DAY.value,
        selected_value=selected,
        selected_unit=inp.selected_unit,
        requires_washout=True,
        rule_ids=rule_ids,
        rationale=hl.rationale,
        status=status,
        critical_issues=critical,
    )

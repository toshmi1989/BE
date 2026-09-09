"""Subject plan validation and lightweight calculation helper.

Does not implement statistical sample-size formulas (Phase 4).
Missing values are never coerced to zero.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import ValidationError


@dataclass
class SubjectPlanValues:
    target_evaluable_n: int | None = None
    planned_randomized_n: int | None = None
    reserve_n: int | None = None
    planned_screened_n: int | None = None


def _positive_int(field: str, value: int | None) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValidationError(f"{field} must be an integer > 0 when supplied", field=field)


def validate_subject_plan(values: SubjectPlanValues) -> None:
    _positive_int("target_evaluable_n", values.target_evaluable_n)
    _positive_int("planned_randomized_n", values.planned_randomized_n)
    _positive_int("planned_screened_n", values.planned_screened_n)

    if values.reserve_n is not None:
        if not isinstance(values.reserve_n, int) or isinstance(values.reserve_n, bool) or values.reserve_n < 0:
            raise ValidationError("reserve_n must be an integer >= 0 when supplied", field="reserve_n")

    if (
        values.planned_randomized_n is not None
        and values.target_evaluable_n is not None
        and values.planned_randomized_n < values.target_evaluable_n
    ):
        raise ValidationError(
            "planned_randomized_n must be >= target_evaluable_n",
            field="planned_randomized_n",
        )

    if (
        values.planned_screened_n is not None
        and values.planned_randomized_n is not None
        and values.planned_screened_n < values.planned_randomized_n
    ):
        raise ValidationError(
            "planned_screened_n must be >= planned_randomized_n",
            field="planned_screened_n",
        )


def calculate_subject_plan(values: SubjectPlanValues) -> SubjectPlanValues:
    """Validate and return plan as-is. No statistical inference; no zero-filling."""
    validate_subject_plan(values)
    return SubjectPlanValues(
        target_evaluable_n=values.target_evaluable_n,
        planned_randomized_n=values.planned_randomized_n,
        reserve_n=values.reserve_n,
        planned_screened_n=values.planned_screened_n,
    )

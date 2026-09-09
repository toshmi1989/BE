"""Phase 15.4 — Math wrapper around canonical 2×2 TOST calculator.

Canonical SoT: ``app.domain.sample_size.Crossover2x2SampleSizeCalculator``
(``CROSSOVER_2X2_TOST_NCT`` / ``BE_TOST_2X2_NCT.v1``).

This module does not invent a second formula — it adds explicit validation,
inflation method labeling, and raw_n / achieved_power surfaces for the engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.domain.exceptions import ValidationError
from app.domain.sample_size import (
    SampleSizeInput,
    SampleSizeResult,
    be_power_2x2_nct,
    calculate_sample_size,
)
from app.domain.sample_size_engine_classes import (
    CANONICAL_ALGORITHM,
    CANONICAL_METHOD_ID,
    DESIGN_TO_CALCULATOR,
)
from app.domain.stats_rules import ROUNDING_2X2
from app.domain.subject_reserve import ReserveInput, apply_subject_reserve


@dataclass(frozen=True)
class ExplicitNumericInputs:
    cv_percent: float
    expected_ratio: float
    alpha: float
    power: float
    be_lower: float
    be_upper: float
    dropout_percent: float | None = None
    inflation_method: str | None = None


def validate_numeric_ranges(inp: ExplicitNumericInputs) -> None:
    """Fail explicitly — never silently clamp."""
    if inp.cv_percent <= 0:
        raise ValidationError("CV <= 0 is INVALID", field="cv_value")
    if inp.expected_ratio <= 0:
        raise ValidationError("GMR/expected_ratio <= 0 is INVALID", field="expected_ratio")
    if inp.alpha <= 0 or inp.alpha >= 1:
        raise ValidationError("alpha must be in (0, 1)", field="alpha")
    if inp.power <= 0 or inp.power >= 1:
        raise ValidationError("power must be in (0, 1)", field="power")
    if inp.be_lower <= 0 or inp.be_upper <= 0 or inp.be_lower >= inp.be_upper:
        raise ValidationError("invalid BE limits", field="be_limits")
    if inp.dropout_percent is not None and (
        inp.dropout_percent < 0 or inp.dropout_percent >= 100
    ):
        raise ValidationError("dropout_percent must be in [0, 100)", field="dropout_percent")


def inflate_randomized_n(
    required_n: int,
    *,
    dropout_percent: float,
    inflation_method: str,
) -> int:
    """Separate evaluable N from planned randomized N with explicit method."""
    if inflation_method == "NONE":
        return int(required_n)
    if inflation_method != "DIVIDE_BY_RETAINMENT_RATE":
        raise ValidationError(
            f"Unsupported inflation_method: {inflation_method}",
            field="inflation_method",
        )
    reserve = apply_subject_reserve(
        ReserveInput(
            evaluable_n=required_n,
            dropout_pct=dropout_percent,
            reserve_pct=0.0,
            screen_failure_pct=0.0,
            rounding=ROUNDING_2X2,
        )
    )
    return int(reserve.randomized_n)


def run_standard_2x2(
    *,
    design: str,
    parameter: str,
    cv_percent: float,
    expected_ratio: float,
    alpha: float,
    power: float,
    be_lower: float,
    be_upper: float,
    dropout_percent: float | None,
    inflation_method: str | None,
) -> dict[str, Any]:
    """Deterministic authoritative calculation for STANDARD_2X2_CROSSOVER."""
    calc_design = DESIGN_TO_CALCULATOR.get(design)
    if calc_design != "CROSSOVER_2X2":
        raise ValidationError(
            "2×2 formula cannot be applied to unsupported design",
            field="design",
        )

    nums = ExplicitNumericInputs(
        cv_percent=cv_percent,
        expected_ratio=expected_ratio,
        alpha=alpha,
        power=power,
        be_lower=be_lower,
        be_upper=be_upper,
        dropout_percent=dropout_percent,
        inflation_method=inflation_method,
    )
    validate_numeric_ranges(nums)

    # Evaluable N first (dropout applied separately with explicit method)
    result: SampleSizeResult = calculate_sample_size(
        SampleSizeInput(
            design_type="CROSSOVER_2X2",
            selected_cv_percent=cv_percent,
            expected_ratio=expected_ratio,
            alpha=alpha,
            power=power,
            be_lower=be_lower,
            be_upper=be_upper,
            parameter=parameter,
            dropout_pct=0.0,
            reserve_pct=0.0,
            screen_failure_pct=0.0,
        )
    )

    required_n = result.evaluable_n
    raw_n = result.raw_n_before_rounding
    achieved = result.achieved_power

    randomized_n = None
    if required_n is not None:
        if inflation_method is None and dropout_percent is not None:
            raise ValidationError(
                "inflation_method required when dropout is set",
                field="inflation_method",
            )
        if dropout_percent is None and inflation_method and inflation_method != "NONE":
            raise ValidationError(
                "dropout_percent required for inflation",
                field="dropout_percent",
            )
        if inflation_method == "NONE" or dropout_percent is None:
            randomized_n = required_n
            inflation_method = inflation_method or "NONE"
        else:
            randomized_n = inflate_randomized_n(
                required_n,
                dropout_percent=float(dropout_percent),
                inflation_method=inflation_method,
            )
        # Recompute achieved power for rounded evaluable N (validation aid)
        if achieved is None and required_n is not None:
            achieved = be_power_2x2_nct(
                required_n, cv_percent, expected_ratio, alpha, be_lower, be_upper
            )

    return {
        "required_n": required_n,
        "randomized_n": randomized_n,
        "raw_n": raw_n,
        "achieved_power": achieved,
        "target_power": power,
        "method": CANONICAL_METHOD_ID,
        "algorithm_version": CANONICAL_ALGORITHM,
        "formula": result.formula,
        "software_version": result.software_version,
        "status": result.status,
        "warnings": list(result.warnings),
        "inflation_method": inflation_method,
        "rounding_rule": ROUNDING_2X2.rule_id,
        "never_rounds_down": True,
    }


def assert_rounding_never_down(raw_n: float, required_n: int) -> None:
    if required_n < math.ceil(raw_n - 1e-12):
        raise AssertionError("Rounding must never reduce required N")

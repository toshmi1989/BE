"""CV study validation and compatibility checks."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import ValidationError
from app.domain.stats_rules import RULE_CV_ABS_MAX


PK_CV_PARAMETERS = ("Cmax", "AUC0_t", "AUC0_inf")
CV_UNITS = ("percent", "%", "fraction")
CV_TYPES = ("WITHIN_SUBJECT", "BETWEEN_SUBJECT", "TOTAL", "REFERENCE_WS", "TEST_WS", "OTHER")


@dataclass
class CVStudyData:
    analyte_id: str | None
    parameter: str
    design: str | None
    condition: str | None
    dose: str | None
    n_total: int | None
    n_be_analysis: int | None
    cv_value: float
    cv_unit: str
    source_id: str | None
    cv_type: str = "WITHIN_SUBJECT"


def normalize_cv_to_percent(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"percent", "%"}:
        return float(value)
    if u == "fraction":
        return float(value) * 100.0
    raise ValidationError(f"Unsupported cv_unit: {unit}", field="cv_unit")


def validate_cv_study(data: CVStudyData) -> None:
    if data.parameter not in PK_CV_PARAMETERS:
        raise ValidationError(
            f"Unsupported parameter: {data.parameter}",
            field="parameter",
            details={"allowed": list(PK_CV_PARAMETERS)},
        )
    if data.cv_unit not in CV_UNITS:
        raise ValidationError(f"Unsupported cv_unit: {data.cv_unit}", field="cv_unit")
    if data.cv_type not in CV_TYPES:
        raise ValidationError(f"Unsupported cv_type: {data.cv_type}", field="cv_type")

    cv_pct = normalize_cv_to_percent(data.cv_value, data.cv_unit)
    abs_max = float(RULE_CV_ABS_MAX.parameters["abs_max_percent"])
    if cv_pct <= 0:
        raise ValidationError("CV must be > 0", field="cv_value")
    if cv_pct >= abs_max:
        raise ValidationError(
            f"CV must be < {abs_max}% (sanity bound {RULE_CV_ABS_MAX.rule_id})",
            field="cv_value",
        )

    if not data.source_id:
        raise ValidationError("source_id required for CV study", field="source_id")
    if not data.analyte_id:
        raise ValidationError("analyte_id required", field="analyte_id")

    if data.n_total is not None and data.n_total <= 0:
        raise ValidationError("n_total must be > 0 when supplied", field="n_total")
    if data.n_be_analysis is not None and data.n_be_analysis <= 0:
        raise ValidationError("n_be_analysis must be > 0 when supplied", field="n_be_analysis")
    if (
        data.n_total is not None
        and data.n_be_analysis is not None
        and data.n_be_analysis > data.n_total
    ):
        raise ValidationError(
            "n_be_analysis must be <= n_total when both supplied",
            field="n_be_analysis",
        )


@dataclass
class CompatibilityResult:
    compatible: bool
    status: str
    warnings: list[str]
    mismatches: list[str]


def check_cv_compatibility(studies: list[CVStudyData]) -> CompatibilityResult:
    if len(studies) < 2:
        return CompatibilityResult(True, "PROPOSED", [], [])

    warnings: list[str] = []
    mismatches: list[str] = []

    analytes = {s.analyte_id for s in studies}
    params = {s.parameter for s in studies}
    designs = {s.design for s in studies}
    conditions = {s.condition for s in studies}
    doses = {s.dose for s in studies}
    types = {s.cv_type for s in studies}

    if len(analytes) > 1:
        mismatches.append("analyte_id")
    if len(params) > 1:
        mismatches.append("parameter")
    if len(types) > 1:
        mismatches.append("cv_type")
    if len(designs) > 1:
        warnings.append("design class differs across CV studies")
        # design class mismatch is compatibility fail for silent pooling
        mismatches.append("design")
    if len(conditions) > 1:
        mismatches.append("condition")
    if len(doses) > 1:
        warnings.append("dose differs across CV studies")
        mismatches.append("dose")

    if mismatches:
        return CompatibilityResult(
            compatible=False,
            status="NEEDS_REVIEW",
            warnings=warnings,
            mismatches=mismatches,
        )
    return CompatibilityResult(True, "PROPOSED", warnings, [])

"""CV selection for sample size — never silent MAX without explicit rule."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.cv_validation import CVStudyData, normalize_cv_to_percent
from app.domain.exceptions import ValidationError


SELECTION_METHODS = (
    "SINGLE_STUDY",
    "POOLED",
    "EXPERT_SELECTED",
    "GUIDELINE_DERIVED",
)


@dataclass
class CVSelectionResult:
    selected_cv: float | None
    cv_unit: str
    source_study_ids: list[str]
    rationale: str
    selection_method: str
    status: str
    warnings: list[str] = field(default_factory=list)
    parameter: str | None = None
    analyte_id: str | None = None


def select_cv_for_sample_size(
    *,
    method: str,
    studies: list[CVStudyData] | None = None,
    pooled_cv: float | None = None,
    expert_cv: float | None = None,
    guideline_cv: float | None = None,
    selected_study_index: int | None = None,
    cv_unit: str = "percent",
) -> CVSelectionResult:
    if method not in SELECTION_METHODS:
        raise ValidationError(f"Unknown selection_method: {method}", field="selection_method")

    if method == "SINGLE_STUDY":
        if not studies:
            raise ValidationError("studies required for SINGLE_STUDY", field="studies")
        idx = 0 if selected_study_index is None else selected_study_index
        if idx < 0 or idx >= len(studies):
            raise ValidationError("selected_study_index out of range", field="selected_study_index")
        s = studies[idx]
        return CVSelectionResult(
            selected_cv=normalize_cv_to_percent(s.cv_value, s.cv_unit),
            cv_unit="percent",
            source_study_ids=[s.source_id] if s.source_id else [],
            rationale=f"Single study CV selected (index={idx}); not auto-max.",
            selection_method=method,
            status="PROPOSED",
            parameter=s.parameter,
            analyte_id=s.analyte_id,
        )

    if method == "POOLED":
        if pooled_cv is None:
            raise ValidationError("pooled_cv required for POOLED selection", field="pooled_cv")
        ids = [s.source_id for s in (studies or []) if s.source_id]
        return CVSelectionResult(
            selected_cv=float(pooled_cv),
            cv_unit="percent",
            source_study_ids=ids,
            rationale="Pooled CV from pooling engine output.",
            selection_method=method,
            status="PROPOSED",
            parameter=studies[0].parameter if studies else None,
            analyte_id=studies[0].analyte_id if studies else None,
        )

    if method == "EXPERT_SELECTED":
        if expert_cv is None or expert_cv <= 0:
            raise ValidationError("expert_cv > 0 required", field="expert_cv")
        return CVSelectionResult(
            selected_cv=normalize_cv_to_percent(expert_cv, cv_unit),
            cv_unit="percent",
            source_study_ids=[],
            rationale="Expert-selected CV; requires verification before VERIFIED status.",
            selection_method=method,
            status="NEEDS_REVIEW",
            warnings=["Expert CV is not auto-verified"],
        )

    # GUIDELINE_DERIVED
    if guideline_cv is None or guideline_cv <= 0:
        raise ValidationError("guideline_cv > 0 required", field="guideline_cv")
    return CVSelectionResult(
        selected_cv=normalize_cv_to_percent(guideline_cv, cv_unit),
        cv_unit="percent",
        source_study_ids=[],
        rationale="Guideline-derived CV input (structured); not invented by engine.",
        selection_method=method,
        status="PROPOSED",
    )

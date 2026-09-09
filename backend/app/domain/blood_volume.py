"""Sample count and blood volume calculations — deterministic, explainable."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import ValidationError


@dataclass
class SampleCountInput:
    points_per_period: int
    periods: int
    planned_subjects: int | None


@dataclass
class SampleCountResult:
    points_per_period: int
    periods: int
    planned_subjects: int | None
    total_subject_periods: int | None
    total_pk_samples: int | None
    rationale: str


def calculate_sample_count(inp: SampleCountInput) -> SampleCountResult:
    if inp.points_per_period <= 0:
        raise ValidationError("points_per_period must be > 0", field="points_per_period")
    if inp.periods <= 0:
        raise ValidationError("periods must be > 0", field="periods")
    if inp.planned_subjects is not None and inp.planned_subjects <= 0:
        raise ValidationError("planned_subjects must be > 0 when supplied", field="planned_subjects")

    subject_periods = None
    total = None
    if inp.planned_subjects is not None:
        subject_periods = inp.planned_subjects * inp.periods
        total = subject_periods * inp.points_per_period

    rationale = (
        f"points_per_period={inp.points_per_period}; periods={inp.periods}; "
        f"planned_subjects={inp.planned_subjects}; "
        "withdrawn subjects not inferred."
    )
    return SampleCountResult(
        points_per_period=inp.points_per_period,
        periods=inp.periods,
        planned_subjects=inp.planned_subjects,
        total_subject_periods=subject_periods,
        total_pk_samples=total,
        rationale=rationale,
    )


@dataclass
class BloodVolumeInput:
    subjects: int
    periods: int
    sampling_points_per_period: int
    blood_volume_per_pk_sample_ml: float
    screening_volume_ml: float = 0.0
    safety_laboratory_volume_ml: float = 0.0
    other_blood_volume_ml: float = 0.0
    reserve_duplicate_factor: float = 1.0


@dataclass
class BloodVolumeResult:
    pk_volume_ml: float
    screening_volume_ml: float
    safety_volume_ml: float
    other_volume_ml: float
    total_volume_ml: float
    volume_per_subject_ml: float
    volume_per_period_ml: float
    rationale: str
    breakdown: dict


def calculate_blood_volume(inp: BloodVolumeInput) -> BloodVolumeResult:
    if inp.subjects <= 0:
        raise ValidationError("subjects must be > 0", field="subjects")
    if inp.periods <= 0:
        raise ValidationError("periods must be > 0", field="periods")
    if inp.sampling_points_per_period <= 0:
        raise ValidationError(
            "sampling_points_per_period must be > 0", field="sampling_points_per_period"
        )
    if inp.blood_volume_per_pk_sample_ml <= 0:
        raise ValidationError(
            "blood_volume_per_pk_sample_ml must be > 0", field="blood_volume_per_pk_sample_ml"
        )
    if inp.reserve_duplicate_factor <= 0:
        raise ValidationError("reserve_duplicate_factor must be > 0", field="reserve_duplicate_factor")
    for name, val in (
        ("screening_volume_ml", inp.screening_volume_ml),
        ("safety_laboratory_volume_ml", inp.safety_laboratory_volume_ml),
        ("other_blood_volume_ml", inp.other_blood_volume_ml),
    ):
        if val < 0:
            raise ValidationError(f"{name} must be >= 0", field=name)

    pk_per_subject = (
        inp.sampling_points_per_period
        * inp.periods
        * inp.blood_volume_per_pk_sample_ml
        * inp.reserve_duplicate_factor
    )
    screening = float(inp.screening_volume_ml)
    safety = float(inp.safety_laboratory_volume_ml)
    other = float(inp.other_blood_volume_ml)
    per_subject = pk_per_subject + screening + safety + other
    total = per_subject * inp.subjects
    per_period = (
        inp.sampling_points_per_period
        * inp.blood_volume_per_pk_sample_ml
        * inp.reserve_duplicate_factor
    )

    rationale = (
        "pk_volume_per_subject = points_per_period × periods × volume_per_sample × reserve_factor; "
        "total = per_subject × subjects. Sample counts and blood volumes kept separate."
    )
    breakdown = {
        "pk_volume_per_subject_ml": pk_per_subject,
        "formula_pk": (
            f"{inp.sampling_points_per_period} × {inp.periods} × "
            f"{inp.blood_volume_per_pk_sample_ml} × {inp.reserve_duplicate_factor}"
        ),
        "screening_volume_ml": screening,
        "safety_volume_ml": safety,
        "other_volume_ml": other,
        "subjects": inp.subjects,
        "periods": inp.periods,
        "points_per_period": inp.sampling_points_per_period,
    }
    return BloodVolumeResult(
        pk_volume_ml=pk_per_subject * inp.subjects,
        screening_volume_ml=screening * inp.subjects,
        safety_volume_ml=safety * inp.subjects,
        other_volume_ml=other * inp.subjects,
        total_volume_ml=total,
        volume_per_subject_ml=per_subject,
        volume_per_period_ml=per_period,
        rationale=rationale,
        breakdown=breakdown,
    )

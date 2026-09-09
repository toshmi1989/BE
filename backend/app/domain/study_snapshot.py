"""Canonical study snapshot — deterministic serialization for synopsis consistency.

ONE STUDY VALUE → ONE CANONICAL SOURCE → MANY PROTOCOL SECTIONS

SubjectPlan owns N counts; SamplingPlan owns points; Product/Reference/Design/Food
are single sources. SampleSizeCalculation is a CALCULATED result that must align
with SubjectPlan after acceptance.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from app.domain.canonical_sampling import get_canonical_sampling_plan
from app.domain.canonical_subjects import get_canonical_subject_counts


def _stable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _stable(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [_stable(x) for x in obj]
    if isinstance(obj, float):
        return round(obj, 12)
    if isinstance(obj, UUID):
        return str(obj)
    if type(obj).__name__ in {"datetime", "date", "time"}:
        return str(obj)
    return obj


@dataclass
class StudyCanonicalSnapshot:
    schema_version: str
    project_id: str
    protocol_number: str | None
    study_title: str | None
    client_input: dict | None
    sponsor: dict | None
    organizations: dict | None
    test_product: dict | None
    reference_product: dict | None
    reference_assessment: dict | None
    design: dict | None
    periods: int | None
    sequences: list
    food_condition: str | None
    food: dict | None
    subject_plan: dict | None
    evaluable_n: int | None
    randomized_n: int | None
    screened_n: int | None
    reserve_n: int | None
    eligibility_counts: dict
    eligibility: dict | None
    analytes: list
    pk_parameters: list
    washout: dict | None
    observation_duration: float | None
    observation_unit: str | None
    sampling: dict | None
    sampling_points: list
    blood_volume: dict | None
    statistics: dict | None
    evidence_summary: dict
    sources: list
    validation_status: dict | None = None

    def to_dict(self) -> dict:
        return _stable(asdict(self))

    def fingerprint(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_consistency_snapshot(ctx: dict) -> dict:
    """Canonical values for synopsis / section engines — SubjectPlan-first N."""
    design = ctx.get("design") or {}
    food = ctx.get("food") or {}
    study = ctx.get("study") or {}
    product = ctx.get("product") or {}
    reference = ctx.get("reference_product") or {}
    washout = ctx.get("washout") or {}
    observation = ctx.get("observation") or {}
    selection = ctx.get("cv_selection") or {}
    subjects_c = get_canonical_subject_counts(ctx)
    sampling_c = get_canonical_sampling_plan(ctx)

    return _stable(
        {
            "protocol_number": study.get("protocol_number"),
            "test_product": {
                "trade_name": product.get("trade_name"),
                "inn": product.get("inn"),
                "manufacturer": product.get("manufacturer"),
                "dosage": product.get("dosage"),
                "dosage_form": product.get("dosage_form"),
                "route": product.get("route"),
                "composition": product.get("composition"),
                "manufacturer_country": product.get("manufacturer_country"),
                "registration_number": product.get("registration_number"),
                "storage_conditions": product.get("storage_conditions"),
                "shelf_life": product.get("shelf_life"),
                "batch": product.get("batch"),
            },
            "reference_product": {
                "trade_name": reference.get("trade_name"),
                "inn": reference.get("inn"),
                "manufacturer": reference.get("manufacturer"),
                "dosage": reference.get("dosage"),
                "dosage_form": reference.get("dosage_form"),
                "purchased_status": reference.get("purchased_status"),
                "manufacturer_country": reference.get("manufacturer_country"),
                "registration_number": reference.get("registration_number"),
            },
            "design": design.get("type"),
            "periods": design.get("periods"),
            "sequences": design.get("sequences") or [],
            "food_condition": food.get("condition") or design.get("food_condition"),
            "evaluable_n": subjects_c.evaluable_n,
            "randomized_n": subjects_c.randomized_n,
            "screened_n": subjects_c.screened_n,
            "reserve_n": subjects_c.reserve_n,
            "subject_counts_source": subjects_c.source,
            "analytes": [
                {"id": a.get("id"), "name": a.get("name"), "type": a.get("type")}
                for a in (ctx.get("analytes") or [])
            ],
            "washout": {
                "value": washout.get("selected_value"),
                "unit": washout.get("unit"),
                "minimum": washout.get("calculated_minimum"),
            },
            "observation_duration": observation.get("selected_duration")
            or observation.get("final_sampling_time")
            or sampling_c.observation_duration,
            "sampling_points": [
                {"time_h": p.get("time_h"), "reason": p.get("reason")}
                for p in sampling_c.points
            ],
            "sampling_points_per_period": sampling_c.points_per_period,
            "pk_parameters": [
                {
                    "analyte_id": p.get("analyte_id"),
                    "parameter_code": p.get("parameter_code"),
                    "range_min": p.get("range_min"),
                    "range_max": p.get("range_max"),
                }
                for p in (ctx.get("pk_parameters") or [])
            ],
            "selected_cv": selection.get("selected_cv"),
            "snapshot_kind": "consistency",
            "version": "STUDY.CONSISTENCY.v2",
        }
    )


def build_canonical_snapshot(ctx: dict) -> StudyCanonicalSnapshot:
    consistency = build_consistency_snapshot(ctx)
    eligibility = ctx.get("eligibility") or {}
    subjects_c = get_canonical_subject_counts(ctx)
    sampling_c = get_canonical_sampling_plan(ctx)
    study = ctx.get("study") or {}
    return StudyCanonicalSnapshot(
        schema_version="2",
        project_id=str(ctx.get("project_id")),
        protocol_number=consistency.get("protocol_number"),
        study_title=study.get("title"),
        client_input=ctx.get("client_input") or study.get("client_input"),
        sponsor=ctx.get("sponsor"),
        organizations=ctx.get("organizations"),
        test_product=consistency.get("test_product"),
        reference_product=consistency.get("reference_product"),
        reference_assessment=ctx.get("reference_assessment"),
        design={
            "type": consistency.get("design"),
            "periods": consistency.get("periods"),
            "sequences": list(consistency.get("sequences") or []),
            "treatments": (ctx.get("design") or {}).get("treatments"),
            "blinding": (ctx.get("design") or {}).get("blinding"),
            "randomization": (ctx.get("design") or {}).get("randomization"),
        },
        periods=consistency.get("periods"),
        sequences=list(consistency.get("sequences") or []),
        food_condition=consistency.get("food_condition"),
        food=ctx.get("food"),
        subject_plan=ctx.get("subjects"),
        evaluable_n=subjects_c.evaluable_n,
        randomized_n=subjects_c.randomized_n,
        screened_n=subjects_c.screened_n,
        reserve_n=subjects_c.reserve_n,
        eligibility_counts={
            "inclusion": len(eligibility.get("inclusion") or []),
            "non_inclusion": len(eligibility.get("non_inclusion") or []),
            "exclusion": len(eligibility.get("exclusion") or []),
        },
        eligibility={
            "inclusion": list(eligibility.get("inclusion") or []),
            "non_inclusion": list(eligibility.get("non_inclusion") or []),
            "exclusion": list(eligibility.get("exclusion") or []),
        },
        analytes=list(consistency.get("analytes") or []),
        pk_parameters=list(consistency.get("pk_parameters") or []),
        washout=consistency.get("washout"),
        observation_duration=consistency.get("observation_duration"),
        observation_unit=(ctx.get("observation") or {}).get("unit"),
        sampling=sampling_c.to_dict(),
        sampling_points=list(consistency.get("sampling_points") or []),
        blood_volume=ctx.get("blood_volume"),
        statistics={
            "selected_cv": consistency.get("selected_cv"),
            "sample_size": ctx.get("sample_size"),
            "config": ctx.get("statistical_config"),
            "subject_counts_source": subjects_c.source,
            "diverges_from_subject_plan": subjects_c.diverges_from_sample_size,
        },
        evidence_summary=ctx.get("evidence_summary") or {"count": 0},
        sources=list(ctx.get("sources") or []),
        validation_status=ctx.get("validation_status"),
    )

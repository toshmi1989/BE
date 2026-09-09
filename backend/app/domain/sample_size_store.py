"""Phase 15.4 — In-memory immutable calculation store (study-scoped)."""

from __future__ import annotations

from typing import Any

from app.domain.sample_size_models import SampleSizeCalculationRecord, SampleSizeExpertReview

_BY_ID: dict[str, SampleSizeCalculationRecord] = {}
_BY_STUDY: dict[str, list[str]] = {}


def reset_sample_size_store() -> None:
    _BY_ID.clear()
    _BY_STUDY.clear()


def put_calculation(rec: SampleSizeCalculationRecord) -> SampleSizeCalculationRecord:
    if rec.id in _BY_ID:
        raise ValueError("Calculations are immutable — create a new version instead of overwrite")
    _BY_ID[rec.id] = rec
    _BY_STUDY.setdefault(rec.study_id, []).append(rec.id)
    return rec


def restore_calculations(records: list[SampleSizeCalculationRecord]) -> None:
    """Hydrate from DB — allows rewrite of empty memory for a study."""
    for rec in records:
        _BY_ID[rec.id] = rec
        ids = _BY_STUDY.setdefault(rec.study_id, [])
        if rec.id not in ids:
            ids.append(rec.id)


def get_calculation(calc_id: str) -> SampleSizeCalculationRecord | None:
    return _BY_ID.get(calc_id)


def list_calculations(study_id: str) -> list[SampleSizeCalculationRecord]:
    ids = _BY_STUDY.get(study_id, [])
    return [_BY_ID[i] for i in ids if i in _BY_ID]


def next_version_number(study_id: str) -> int:
    existing = list_calculations(study_id)
    if not existing:
        return 1
    return max(c.version_number for c in existing) + 1


def append_review(calc_id: str, review: SampleSizeExpertReview) -> SampleSizeCalculationRecord:
    rec = _BY_ID.get(calc_id)
    if rec is None:
        raise KeyError(calc_id)
    # Reviews mutate review list only (append); calculation numeric fields stay frozen.
    # Status may update as review outcome — treated as workflow state, not recalculation overwrite.
    rec.reviews = list(rec.reviews) + [review]
    if review.decision == "ACCEPT_CALCULATION":
        rec.status = "ACCEPTED"
        rec.eligible_for_protocol_use = True
    elif review.decision == "REJECT_CALCULATION":
        rec.status = "REJECTED"
        rec.eligible_for_protocol_use = False
    elif review.decision == "ACCEPT_CURRENT_N":
        rec.status = "ACCEPTED"
        rec.eligible_for_protocol_use = False  # accepted current, not calculated
    elif review.decision == "REQUEST_RECALCULATION":
        rec.status = "PENDING_REVIEW"
        rec.eligible_for_protocol_use = False
    return rec


def calculation_inputs_view(rec: SampleSizeCalculationRecord) -> dict[str, Any]:
    return {
        "calculation_id": rec.id,
        "inputs": [i.to_dict() for i in rec.inputs],
        "anonymous_inputs_allowed": False,
    }


def calculation_provenance_view(rec: SampleSizeCalculationRecord) -> dict[str, Any]:
    return {
        "calculation_id": rec.id,
        "fingerprint": rec.fingerprint,
        "version_number": rec.version_number,
        "method": rec.method,
        "algorithm_version": rec.algorithm_version,
        "calculation_version": rec.calculation_version,
        "inputs": [i.to_dict() for i in rec.inputs],
        "cv_source_claim_ids": [
            i.source_claim_id for i in rec.inputs if i.name == "cv_value" and i.source_claim_id
        ],
        "study_mutated": False,
        "immutable": True,
    }

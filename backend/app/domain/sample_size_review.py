"""Phase 15.4 — Expert review of sample-size calculations (no silent Study mutation)."""

from __future__ import annotations

from typing import Any

from app.domain.exceptions import ValidationError
from app.domain.sample_size_models import SampleSizeExpertReview
from app.domain.sample_size_store import append_review, get_calculation


def request_review(calc_id: str, *, reviewer: str, comment: str = "") -> dict[str, Any]:
    rec = get_calculation(calc_id)
    if rec is None:
        raise ValidationError("Calculation not found", field="calculation_id")
    if rec.status == "BLOCKED":
        raise ValidationError("Cannot review a blocked calculation", field="status")
    rec.status = "PENDING_REVIEW"
    return {
        "calculation_id": calc_id,
        "status": rec.status,
        "reviewer_requested": reviewer,
        "comment": comment,
        "study_mutated": False,
    }


def approve_calculation(
    calc_id: str,
    *,
    reviewer: str,
    decision: str,
    comment: str = "",
    project_to_study: bool = False,
) -> dict[str, Any]:
    """Approval records decision only. Study projection requires explicit separate rules."""
    if decision not in {
        "ACCEPT_CALCULATION",
        "ACCEPT_CURRENT_N",
        "REQUEST_RECALCULATION",
    }:
        raise ValidationError("Invalid approve decision", field="decision")
    rec = get_calculation(calc_id)
    if rec is None:
        raise ValidationError("Calculation not found", field="calculation_id")

    # AI cannot approve
    if reviewer.strip().upper() in {"AI", "MOCKAI", "SYSTEM_AI"}:
        raise ValidationError("AI cannot approve sample-size calculation", field="reviewer")

    if project_to_study:
        # Phase 15.4: do not auto-project unless canonical projection explicitly permitted.
        # Default: refuse silent mutation.
        raise ValidationError(
            "Study projection from sample-size approval is not enabled in Phase 15.4 "
            "(calculation/recommendation alone must not mutate Study)",
            field="project_to_study",
        )

    review = SampleSizeExpertReview(
        calculation_id=calc_id,
        reviewer=reviewer,
        decision=decision,
        comment=comment,
        projected_to_study=False,
    )
    append_review(calc_id, review)
    return {
        "calculation_id": calc_id,
        "review": review.to_dict(),
        "status": rec.status,
        "study_mutated": False,
        "old_value": None,
        "new_value": None,
        "change_impact": None,
    }


def reject_calculation(
    calc_id: str,
    *,
    reviewer: str,
    comment: str = "",
) -> dict[str, Any]:
    if reviewer.strip().upper() in {"AI", "MOCKAI", "SYSTEM_AI"}:
        raise ValidationError("AI cannot reject/approve sample-size calculation", field="reviewer")
    rec = get_calculation(calc_id)
    if rec is None:
        raise ValidationError("Calculation not found", field="calculation_id")
    review = SampleSizeExpertReview(
        calculation_id=calc_id,
        reviewer=reviewer,
        decision="REJECT_CALCULATION",
        comment=comment,
        projected_to_study=False,
    )
    append_review(calc_id, review)
    # History preserved — record still in store
    return {
        "calculation_id": calc_id,
        "review": review.to_dict(),
        "status": rec.status,
        "history_preserved": True,
        "study_mutated": False,
    }

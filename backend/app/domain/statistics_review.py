"""Phase 15.5 — Expert review / modify for StatisticsPlan."""

from __future__ import annotations

from typing import Any

from app.domain.exceptions import ValidationError
from app.domain.statistics_models import StatisticsExpertReview
from app.domain.statistics_store import append_review, get_plan, mark_superseded


def request_review(plan_id: str, *, reviewer: str, comment: str = "") -> dict[str, Any]:
    plan = get_plan(plan_id)
    if plan is None:
        raise ValidationError("StatisticsPlan not found", field="plan_id")
    plan.status = "REVIEW_REQUIRED"
    plan.audit = list(plan.audit) + [
        {"event": "REQUEST_REVIEW", "reviewer": reviewer, "comment": comment}
    ]
    return {"plan_id": plan_id, "status": plan.status, "study_mutated": False}


def approve_plan(plan_id: str, *, reviewer: str, comment: str = "") -> dict[str, Any]:
    if reviewer.strip().upper() in {"AI", "MOCKAI", "SYSTEM_AI"}:
        raise ValidationError("AI cannot approve StatisticsPlan", field="reviewer")
    plan = get_plan(plan_id)
    if plan is None:
        raise ValidationError("StatisticsPlan not found", field="plan_id")
    review = StatisticsExpertReview(
        plan_id=plan_id,
        reviewer=reviewer,
        action="APPROVE",
        plan_version=plan.version,
        comment=comment,
    )
    append_review(plan_id, review)
    return {"plan_id": plan_id, "review": review.to_dict(), "status": plan.status, "study_mutated": False}


def reject_plan(plan_id: str, *, reviewer: str, comment: str = "") -> dict[str, Any]:
    if reviewer.strip().upper() in {"AI", "MOCKAI", "SYSTEM_AI"}:
        raise ValidationError("AI cannot reject/approve StatisticsPlan", field="reviewer")
    plan = get_plan(plan_id)
    if plan is None:
        raise ValidationError("StatisticsPlan not found", field="plan_id")
    review = StatisticsExpertReview(
        plan_id=plan_id,
        reviewer=reviewer,
        action="REJECT",
        plan_version=plan.version,
        comment=comment,
    )
    append_review(plan_id, review)
    return {
        "plan_id": plan_id,
        "review": review.to_dict(),
        "status": plan.status,
        "history_preserved": True,
        "study_mutated": False,
    }


def modify_plan(
    plan_id: str,
    *,
    reviewer: str,
    modifications: dict[str, Any],
    comment: str = "",
    recompute_fn=None,
) -> dict[str, Any]:
    """Expert modification → new plan version (old remains auditable)."""
    if reviewer.strip().upper() in {"AI", "MOCKAI", "SYSTEM_AI"}:
        raise ValidationError("AI cannot modify StatisticsPlan", field="reviewer")
    old = get_plan(plan_id)
    if old is None:
        raise ValidationError("StatisticsPlan not found", field="plan_id")
    if recompute_fn is None:
        raise ValidationError("recompute_fn required for modify", field="recompute_fn")

    review = StatisticsExpertReview(
        plan_id=plan_id,
        reviewer=reviewer,
        action="MODIFY",
        plan_version=old.version,
        comment=comment,
        modifications=modifications,
    )
    append_review(plan_id, review)
    mark_superseded(plan_id, reason="expert_modify")

    new_plan = recompute_fn(old, modifications, reviewer=reviewer)
    new_plan.supersedes_id = old.id
    return {
        "old_plan_id": old.id,
        "new_plan_id": new_plan.id,
        "new_version": new_plan.version,
        "study_mutated": False,
        "review": review.to_dict(),
    }

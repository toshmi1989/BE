"""Phase 15.5 — In-memory immutable StatisticsPlan store."""

from __future__ import annotations

from typing import Any

from app.domain.statistics_models import StatisticsExpertReview, StatisticsPlan

_BY_ID: dict[str, StatisticsPlan] = {}
_BY_STUDY: dict[str, list[str]] = {}


def reset_statistics_store() -> None:
    _BY_ID.clear()
    _BY_STUDY.clear()


def put_plan(plan: StatisticsPlan) -> StatisticsPlan:
    if plan.id in _BY_ID:
        raise ValueError("StatisticsPlan versions are immutable — create a new version")
    _BY_ID[plan.id] = plan
    _BY_STUDY.setdefault(plan.study_id, []).append(plan.id)
    return plan


def get_plan(plan_id: str) -> StatisticsPlan | None:
    return _BY_ID.get(plan_id)


def list_plans(study_id: str) -> list[StatisticsPlan]:
    ids = _BY_STUDY.get(study_id, [])
    return [_BY_ID[i] for i in ids if i in _BY_ID]


def latest_plan(study_id: str) -> StatisticsPlan | None:
    rows = list_plans(study_id)
    return rows[-1] if rows else None


def next_plan_version(study_id: str) -> int:
    rows = list_plans(study_id)
    if not rows:
        return 1
    return max(p.version for p in rows) + 1


def append_review(plan_id: str, review: StatisticsExpertReview) -> StatisticsPlan:
    plan = _BY_ID.get(plan_id)
    if plan is None:
        raise KeyError(plan_id)
    plan.reviews = list(plan.reviews) + [review]
    plan.audit = list(plan.audit) + [
        {
            "event": "REVIEW",
            "action": review.action,
            "reviewer": review.reviewer,
            "timestamp": review.timestamp,
            "plan_version": review.plan_version,
        }
    ]
    if review.action == "APPROVE":
        plan.status = "APPROVED"
    elif review.action == "REJECT":
        plan.status = "REJECTED"
    elif review.action == "REQUEST_MORE_INFORMATION":
        plan.status = "REVIEW_REQUIRED"
    return plan


def mark_superseded(plan_id: str, *, reason: str) -> None:
    plan = _BY_ID.get(plan_id)
    if plan is None:
        return
    if plan.status not in {"SUPERSEDED", "REJECTED"}:
        plan.status = "SUPERSEDED"
    plan.audit = list(plan.audit) + [
        {"event": "SUPERSEDED", "reason": reason, "timestamp": review_now()}
    ]


def review_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def plan_parameters_view(plan: StatisticsPlan) -> dict[str, Any]:
    return {
        "plan_id": plan.id,
        "parameters": [p.to_dict() for p in plan.parameters],
        "display": [p.display_dict() for p in plan.parameters],
    }


def plan_evidence_view(plan: StatisticsPlan) -> dict[str, Any]:
    return {
        "plan_id": plan.id,
        "choices": [c.to_dict() for c in plan.choices],
        "current_study_facts": plan.current_study_facts,
        "knowledge_gaps": plan.knowledge_gaps,
        "source_roles_present": sorted({c.source_role for c in plan.choices}),
        "proposed_not_authoritative": True,
    }

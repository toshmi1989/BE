"""Decision engine orchestrator — Phase 15.0 / 15.1.

recompute → recommendations only. study_mutated always False unless explicit expert approve projection.
Dependency-aware invalidation (Phase 15.1).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.content_change_impact import compute_content_change_impact
from app.domain.decision_context import DecisionContext, build_context_from_package
from app.domain.decision_dependency import domains_affected_by_field
from app.domain.decision_design import evaluate_design
from app.domain.decision_engines import (
    evaluate_analyte_pk,
    evaluate_food,
    evaluate_sampling,
    evaluate_washout,
)
from app.domain.decision_models import AnalogueStudyEvidence, ProtocolDecision
from app.domain.study_input_package import StudyInputPackage
from app.domain.validation_graph import change_impact as validation_change_impact


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


EVALUATORS = {
    "DESIGN": evaluate_design,
    "FOOD": evaluate_food,
    "WASHOUT": evaluate_washout,
    "SAMPLING": evaluate_sampling,
    "ANALYTE_PK": evaluate_analyte_pk,
}


def recompute_decisions(
    ctx: DecisionContext,
    *,
    previous: list[ProtocolDecision] | None = None,
    domains: list[str] | None = None,
) -> list[ProtocolDecision]:
    """Generate fresh recommendations. Supersede prior non-terminal decisions.

    If domains is provided, only those domains are recomputed (dependency-aware).
    """
    terminal = {"APPROVED", "REJECTED", "KEEP_CURRENT"}
    prev_by_domain = {p.domain: p for p in (previous or []) if p.status not in terminal}
    terminal_by_domain = {p.domain: p for p in (previous or []) if p.status in terminal}
    target_domains = list(domains) if domains is not None else list(EVALUATORS.keys())
    out: list[ProtocolDecision] = []
    # Preserve non-recomputed / terminal decisions from previous
    if previous:
        for p in previous:
            if p.status in terminal:
                out.append(p)
            elif domains is not None and p.domain not in target_domains and p.status != "SUPERSEDED":
                out.append(p)
    for domain in target_domains:
        if domain in terminal_by_domain:
            continue
        fn = EVALUATORS.get(domain)
        if not fn:
            continue
        decision = fn(ctx)
        old = prev_by_domain.get(domain)
        if old and old.status not in terminal:
            if old.recommendation:
                old.recommendation.superseded = True
                decision.recommendation_history = list(old.recommendation_history) + [old.recommendation]
            old.status = "SUPERSEDED"
            decision.recommendation_history = list(decision.recommendation_history)
            if old.recommendation and old.recommendation not in decision.recommendation_history:
                decision.recommendation_history.append(old.recommendation)
        elif old and old.recommendation_history:
            decision.recommendation_history = list(old.recommendation_history)
        decision.study_mutated = False
        out.append(decision)
    # Stable domain order
    order = {d: i for i, d in enumerate(EVALUATORS.keys())}
    out.sort(key=lambda x: order.get(x.domain, 99))
    return out


def recompute_from_package(
    package: StudyInputPackage,
    *,
    study_id: str | None = None,
    project_id: str | None = None,
    previous: list[ProtocolDecision] | None = None,
    analogues: list[AnalogueStudyEvidence] | None = None,
) -> tuple[DecisionContext, list[ProtocolDecision]]:
    ctx = build_context_from_package(
        package,
        study_id=study_id,
        project_id=project_id,
        analogues=analogues,
    )
    decisions = recompute_decisions(ctx, previous=previous)
    return ctx, decisions


def approve_decision(
    decision: ProtocolDecision,
    *,
    reviewer: str,
    selected_option: str,
    rationale: str,
    comment: str | None = None,
    project_to_study: bool = False,
) -> dict[str, Any]:
    """Expert approval. Does not mutate Study unless project_to_study explicitly True.

    Even then, this phase records a projection intent only — Study ORM mutation
    goes through existing ExpertDecision guards; we set study_mutated False unless
    a controlled projection hook confirms change.
    """
    if not reviewer or not str(reviewer).strip():
        raise ValueError("reviewer required")
    if not rationale or not str(rationale).strip():
        raise ValueError("rationale required")
    if decision.status == "BLOCKED" and (decision.blocking_reasons or decision.blocking_conflicts):
        raise ValueError("Cannot approve blocked decision with open dependency blockers")
    if decision.recommendation is None:
        raise ValueError("No recommendation to approve")

    action = {
        "action": "APPROVE",
        "reviewer": reviewer,
        "timestamp": _now(),
        "decision_id": decision.id,
        "selected_option": selected_option,
        "rationale": rationale,
        "comment": comment,
        "recommendation_id": decision.recommendation.id,
        "recommendation_preserved": True,
        "is_system_recommendation": False,
        "source_type": "EXPERT_DECISION",
    }
    decision.expert_actions.append(action)
    decision.selected_option = selected_option
    decision.status = "APPROVED"
    decision.expert_decision_id = f"ED-{uuid4().hex[:12]}"
    decision.updated_at = _now()
    # Preserve recommendation history — do not mutate historical recommendation object fields except link
    decision.study_mutated = False
    projection = None
    if project_to_study:
        # Controlled projection intent only — still no silent Study ORM write in this layer
        projection = {
            "domain": decision.domain,
            "selected_option": selected_option,
            "expert_decision_id": decision.expert_decision_id,
            "note": "Projection requires existing ExpertDecision apply path; Study not mutated here",
            "study_mutated": False,
        }
    return {
        "decision": decision.to_dict(),
        "action": action,
        "projection": projection,
        "study_mutated": False,
    }


def reject_decision(
    decision: ProtocolDecision,
    *,
    reviewer: str,
    rationale: str,
) -> dict[str, Any]:
    if not reviewer:
        raise ValueError("reviewer required")
    if not rationale:
        raise ValueError("rationale required")
    # Preserve recommendation in history
    if decision.recommendation and decision.recommendation not in decision.recommendation_history:
        decision.recommendation_history.append(decision.recommendation)
    action = {
        "action": "REJECT",
        "reviewer": reviewer,
        "timestamp": _now(),
        "decision_id": decision.id,
        "rationale": rationale,
        "recommendation_preserved": True,
    }
    decision.expert_actions.append(action)
    decision.status = "REJECTED"
    decision.updated_at = _now()
    decision.study_mutated = False
    return {"decision": decision.to_dict(), "action": action, "study_mutated": False}


def modify_decision(
    decision: ProtocolDecision,
    *,
    reviewer: str,
    selected_option: str,
    rationale: str,
) -> dict[str, Any]:
    if not reviewer or not rationale or not selected_option:
        raise ValueError("reviewer, selected_option, rationale required")
    original = decision.recommendation
    if original and original not in decision.recommendation_history:
        decision.recommendation_history.append(original)
    action = {
        "action": "MODIFY",
        "reviewer": reviewer,
        "timestamp": _now(),
        "decision_id": decision.id,
        "selected_option": selected_option,
        "rationale": rationale,
        "original_recommendation_id": original.id if original else None,
        "recommendation_preserved": True,
    }
    decision.expert_actions.append(action)
    decision.selected_option = selected_option
    decision.status = "APPROVED"
    decision.expert_decision_id = f"ED-{uuid4().hex[:12]}"
    decision.updated_at = _now()
    decision.study_mutated = False
    return {"decision": decision.to_dict(), "action": action, "study_mutated": False}


def invalidate_on_upstream_change(
    decisions: list[ProtocolDecision],
    *,
    changed_field: str,
) -> dict[str, Any]:
    """Mark only dependency-affected decisions SUPERSEDED (Phase 15.1)."""
    val_impact = validation_change_impact(changed_field.split(".")[0] if "." in changed_field else changed_field)
    content_impact = compute_content_change_impact(changed_field=changed_field)
    affected_domains = set(domains_affected_by_field(changed_field))

    superseded = []
    unchanged = []
    for d in decisions:
        if d.domain in affected_domains and d.status not in {"SUPERSEDED"}:
            if d.recommendation:
                d.recommendation.superseded = True
                if d.recommendation not in d.recommendation_history:
                    d.recommendation_history.append(d.recommendation)
            d.status = "SUPERSEDED"
            d.updated_at = _now()
            superseded.append(d.id)
        else:
            unchanged.append(d.domain)
    return {
        "changed_field": changed_field,
        "affected_domains": sorted(affected_domains),
        "unaffected_domains": sorted(set(unchanged) - affected_domains),
        "validation_impact": val_impact,
        "content_impact": content_impact.to_dict() if hasattr(content_impact, "to_dict") else content_impact,
        "superseded_decision_ids": superseded,
        "study_mutated": False,
        "requires_recompute": bool(superseded),
        "recompute_domains": sorted(affected_domains),
    }


def keep_current_value(
    decision: ProtocolDecision,
    *,
    reviewer: str,
    rationale: str,
    current_fact_evidence_id: str | None = None,
) -> dict[str, Any]:
    """Expert confirms CURRENT_STUDY_FACT without converting it to SYSTEM_RECOMMENDATION.

    Does not rewrite historical source evidence.
    """
    if not reviewer or not rationale:
        raise ValueError("reviewer and rationale required")
    # Find current study fact evidence — leave it unchanged
    fact_ids = [
        e.id
        for e in decision.evidence
        if e.decision_source_type == "CURRENT_STUDY_FACT"
        and (current_fact_evidence_id is None or e.id == current_fact_evidence_id)
    ]
    action = {
        "action": "KEEP_CURRENT_VALUE",
        "reviewer": reviewer,
        "timestamp": _now(),
        "decision_id": decision.id,
        "rationale": rationale,
        "referenced_current_fact_evidence_ids": fact_ids,
        "source_evidence_rewritten": False,
        "creates_system_recommendation": False,
        "source_type": "EXPERT_DECISION",
    }
    decision.expert_actions.append(action)
    decision.selected_option = decision.selected_option or (
        next(
            (e.option for e in decision.evidence if e.decision_source_type == "CURRENT_STUDY_FACT" and e.option),
            None,
        )
    )
    decision.status = "APPROVED"
    decision.expert_decision_id = f"ED-{uuid4().hex[:12]}"
    decision.updated_at = _now()
    decision.study_mutated = False
    # Do not mutate evidence excerpts / statuses
    return {
        "decision": decision.to_dict(),
        "action": action,
        "study_mutated": False,
        "source_evidence_rewritten": False,
    }


def ai_cannot_approve(decision: ProtocolDecision, *, actor: str = "AI") -> None:
    if str(actor).upper() in {"AI", "MOCKAI", "MOCK_AI"}:
        raise PermissionError("AI cannot approve a decision")


def ai_cannot_finalize_applicability(*, actor: str = "AI") -> None:
    if str(actor).upper() in {"AI", "MOCKAI", "MOCK_AI"}:
        raise PermissionError("AI cannot declare final applicability VERIFIED")

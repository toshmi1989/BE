"""Decision Center API — Phase 15.0 / 15.1.

Recommendations never mutate Study. Expert approve/reject/modify are auditable.
Dependency-aware blockers and evidence applicability endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.domain.decision_context import build_context_from_package
from app.domain.decision_dependency import dependencies_for_domain, is_decision_blocked
from app.domain.decision_engine import (
    ai_cannot_approve,
    approve_decision,
    invalidate_on_upstream_change,
    keep_current_value,
    modify_decision,
    recompute_decisions,
    recompute_from_package,
    reject_decision,
)
from app.domain.decision_models import AnalogueStudyEvidence
from app.domain.decision_store import (
    add_analogue,
    clear_decision_store,
    decision_center_summary,
    get_context,
    get_decision,
    list_analogues,
    list_decisions,
    put_context,
    put_decisions,
)
from app.domain.study_input_pipeline import load_real_fixture_package
from app.domain.study_input_store import get_package, put_package
from app.domain.workspace_authority import after_mutation, ensure_db_authoritative
from app.schemas.writer_phase28 import DecisionActionResponse, DecisionListResponse


router = APIRouter(prefix="/decision-center", tags=["decision-center"])


class RecomputeIn(BaseModel):
    package_id: str | None = None
    study_id: str | None = None
    project_id: str | None = None
    use_golden_fixture: bool = False
    domains: list[str] | None = None


class ExpertActionIn(BaseModel):
    reviewer: str
    rationale: str
    selected_option: str | None = None
    comment: str | None = None
    actor: str | None = None


class ModifyIn(BaseModel):
    reviewer: str
    selected_option: str
    rationale: str
    actor: str | None = None


class KeepCurrentIn(BaseModel):
    reviewer: str
    rationale: str
    current_fact_evidence_id: str | None = None
    actor: str | None = None


class InvalidateIn(BaseModel):
    changed_field: str
    study_id: str | None = None
    package_id: str | None = None


class AnalogueIn(BaseModel):
    study_reference: str
    population: str | None = None
    product: str | None = None
    dose: str | None = None
    design: str | None = None
    condition: str | None = None
    sampling: str | None = None
    relevance: str = "UNKNOWN"
    source_id: str | None = None
    claim: str | None = None
    review_status: str = "PROPOSED"


def _dec(decision_id: str):
    d = get_decision(decision_id)
    if d is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return d


@router.post("/studies/{study_id}/decisions/recompute")
def api_recompute(
    study_id: str,
    payload: RecomputeIn | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    payload = payload or RecomputeIn()
    if payload.use_golden_fixture or not payload.package_id:
        pkg = load_real_fixture_package(prefer_text_dump=False)
        pkg.study_id = study_id
        put_package(pkg)
    else:
        pkg = get_package(payload.package_id)
        if pkg is None:
            raise HTTPException(status_code=404, detail="Package not found")
    previous = list_decisions(study_id, package_id=pkg.package_id)
    analogues = list_analogues(study_id)
    ctx = build_context_from_package(
        pkg,
        study_id=study_id,
        project_id=payload.project_id,
        analogues=analogues,
    )
    decisions = recompute_decisions(ctx, previous=previous, domains=payload.domains)
    put_context(study_id, ctx, package_id=pkg.package_id)
    put_decisions(study_id, decisions, package_id=pkg.package_id)
    after_mutation(db, study_id)
    return {
        "study_id": study_id,
        "package_id": pkg.package_id,
        "decisions": [d.to_dict(for_ui=True) for d in decisions],
        "blocking_conflicts": ctx.critical_conflict_fields(),
        "recomputed_domains": payload.domains or sorted({d.domain for d in decisions}),
        "study_mutated": False,
    }


@router.get("/studies/{study_id}/decisions", response_model=DecisionListResponse)
def api_list(
    study_id: str,
    package_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    return decision_center_summary(study_id, package_id=package_id)


@router.get("/studies/{study_id}/decisions/{decision_id}", response_model=DecisionActionResponse)
def api_get(study_id: str, decision_id: str) -> dict[str, Any]:
    return _dec(decision_id).to_dict(for_ui=True)


@router.get("/studies/{study_id}/decisions/{decision_id}/evidence")
def api_evidence(study_id: str, decision_id: str) -> dict[str, Any]:
    d = _dec(decision_id)
    return {
        "decision_id": decision_id,
        "domain": d.domain,
        "domain_label": d.to_dict()["domain_label"],
        "evidence": [
            {
                **e.to_dict(),
                "verification_status": e.status,
                "applicability": e.applicability,
                "applicability_reason": e.applicability_reason,
                "decision_source_type": e.decision_source_type,
                "supports_contradicts": e.support_level,
            }
            for e in d.evidence
        ],
        "option_matrix": d.option_matrix,
        "study_mutated": False,
    }


@router.get("/studies/{study_id}/decisions/{decision_id}/dependencies")
def api_dependencies(study_id: str, decision_id: str) -> dict[str, Any]:
    d = _dec(decision_id)
    return {"decision_id": decision_id, "study_id": study_id, **dependencies_for_domain(d.domain)}


@router.get("/studies/{study_id}/decisions/{decision_id}/blockers")
def api_blockers(study_id: str, decision_id: str) -> dict[str, Any]:
    d = _dec(decision_id)
    ctx = get_context(study_id, package_id=d.package_id)
    if ctx is None:
        return {
            "decision_id": decision_id,
            "domain": d.domain,
            "blocked": d.status == "BLOCKED",
            "blocking_reasons": d.blocking_reasons,
            "non_blocking_issues": d.non_blocking_issues,
        }
    report = is_decision_blocked(d.domain, ctx)
    return {"decision_id": decision_id, "study_id": study_id, **report.to_dict()}


@router.get("/studies/{study_id}/decisions/{decision_id}/applicability")
def api_applicability(study_id: str, decision_id: str) -> dict[str, Any]:
    d = _dec(decision_id)
    return {
        "decision_id": decision_id,
        "domain": d.domain,
        "items": [
            {
                "evidence_id": e.id,
                "decision_id": d.id,
                "verification_status": e.status,
                "applicability": e.applicability,
                "applicability_reason": e.applicability_reason,
                "decision_source_type": e.decision_source_type,
                "support_level": e.support_level,
                "excerpt": e.excerpt,
            }
            for e in d.evidence
        ],
        "assessments": d.applicability_assessments,
        "note": "verification_status and applicability are independent",
    }


@router.post("/studies/{study_id}/decisions/{decision_id}/approve", response_model=DecisionActionResponse)
def api_approve(
    study_id: str,
    decision_id: str,
    payload: ExpertActionIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    if payload.actor:
        try:
            ai_cannot_approve(_dec(decision_id), actor=payload.actor)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    d = _dec(decision_id)
    opt = payload.selected_option or (d.recommendation.option if d.recommendation else None)
    if not opt:
        raise HTTPException(status_code=422, detail="selected_option required")
    try:
        out = approve_decision(
            d,
            reviewer=payload.reviewer,
            selected_option=opt,
            rationale=payload.rationale,
            comment=payload.comment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    after_mutation(db, study_id)
    return out


@router.post("/studies/{study_id}/decisions/{decision_id}/keep-current", response_model=DecisionActionResponse)
def api_keep_current(
    study_id: str,
    decision_id: str,
    payload: KeepCurrentIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    if payload.actor and str(payload.actor).upper() in {"AI", "MOCKAI", "MOCK_AI"}:
        raise HTTPException(status_code=403, detail="AI cannot approve/keep-current decisions")
    try:
        out = keep_current_value(
            _dec(decision_id),
            reviewer=payload.reviewer,
            rationale=payload.rationale,
            current_fact_evidence_id=payload.current_fact_evidence_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    after_mutation(db, study_id)
    return out


@router.post("/studies/{study_id}/decisions/{decision_id}/reject", response_model=DecisionActionResponse)
def api_reject(
    study_id: str,
    decision_id: str,
    payload: ExpertActionIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    if payload.actor and str(payload.actor).upper() in {"AI", "MOCKAI", "MOCK_AI"}:
        raise HTTPException(status_code=403, detail="AI cannot reject/approve decisions")
    try:
        out = reject_decision(_dec(decision_id), reviewer=payload.reviewer, rationale=payload.rationale)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    after_mutation(db, study_id)
    return out


@router.post("/studies/{study_id}/decisions/{decision_id}/modify", response_model=DecisionActionResponse)
def api_modify(
    study_id: str,
    decision_id: str,
    payload: ModifyIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    if payload.actor and str(payload.actor).upper() in {"AI", "MOCKAI", "MOCK_AI"}:
        raise HTTPException(status_code=403, detail="AI cannot modify decisions")
    try:
        out = modify_decision(
            _dec(decision_id),
            reviewer=payload.reviewer,
            selected_option=payload.selected_option,
            rationale=payload.rationale,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    after_mutation(db, study_id)
    return out


@router.post("/studies/{study_id}/decisions/invalidate")
def api_invalidate(
    study_id: str,
    payload: InvalidateIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    decisions = list_decisions(study_id, package_id=payload.package_id)
    result = invalidate_on_upstream_change(decisions, changed_field=payload.changed_field)
    put_decisions(study_id, decisions, package_id=payload.package_id)
    after_mutation(db, study_id)
    return result


@router.post("/studies/{study_id}/analogues", status_code=201)
def api_add_analogue(
    study_id: str,
    payload: AnalogueIn,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    an = AnalogueStudyEvidence(**payload.model_dump())
    add_analogue(study_id, an)
    after_mutation(db, study_id)
    return an.to_dict()


@router.get("/studies/{study_id}/analogues")
def api_list_analogues(study_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    ensure_db_authoritative(db, study_id)
    return [a.to_dict() for a in list_analogues(study_id)]


@router.post("/fixtures/updcb-real/recompute", status_code=201)
def api_golden_recompute(db: Session = Depends(get_db)) -> dict[str, Any]:
    clear_decision_store()
    pkg = load_real_fixture_package(prefer_text_dump=False)
    put_package(pkg)
    study_id = pkg.fixture_id or "UPDCB-02-BE-2026"
    pkg.study_id = study_id
    ctx, decisions = recompute_from_package(pkg, study_id=study_id)
    put_context(study_id, ctx, package_id=pkg.package_id)
    put_decisions(study_id, decisions, package_id=pkg.package_id)
    after_mutation(db, study_id)
    by_domain = {d.domain: d for d in decisions}
    return {
        "study_id": study_id,
        "package_id": pkg.package_id,
        "fixture_id": pkg.fixture_id,
        "decisions": [d.to_dict(for_ui=True) for d in decisions],
        "blocking_conflicts": ctx.critical_conflict_fields(),
        "dependency_aware_statuses": {dom: by_domain[dom].status for dom in by_domain},
        "study_mutated": False,
    }

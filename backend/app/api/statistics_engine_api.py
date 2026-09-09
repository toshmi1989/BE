"""Phase 15.5 / 28 — Statistics Engine API (study-scoped, DB-persisted)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.domain import statistics_review as review_svc
from app.domain.decision_store import get_context
from app.domain.exceptions import ValidationError
from app.domain.statistics_engine import (
    apply_expert_modifications,
    golden_updcb_context,
    invalidate_statistics_on_change,
    recompute_statistics_plan,
    ui_statistics_panel,
)
from app.domain.statistics_store import (
    get_plan,
    latest_plan,
    list_plans,
    plan_evidence_view,
    plan_parameters_view,
)
from app.domain.workspace_authority import after_mutation, ensure_db_authoritative
from app.domain.workspace_persistence import find_study_key_for_statistics
from app.schemas.writer_phase28 import StatisticsStudyResponse

router = APIRouter(tags=["statistics-engine"])


class RecomputeRequest(BaseModel):
    design: str | None = None
    parameters: list[str] | None = None
    confidence_level: float | None = None
    confidence_level_source: str | None = None
    acceptance_lower: float | None = None
    acceptance_upper: float | None = None
    acceptance_source: str | None = None
    acceptance_wording: str | None = None
    transformation: str | None = None
    transformation_source: str | None = None
    model: str | None = None
    model_source: str | None = None
    analysis_population: str | None = None
    analysis_population_source: str | None = None
    primary_be_parameters: list[str] | None = None
    primary_be_source: str | None = None
    use_golden_context: bool = False
    created_by: str | None = None
    ai_select_method: bool = False
    observed_gmr: float | None = None
    observed_ci: list[float] | None = None


class ReviewBody(BaseModel):
    reviewer: str
    comment: str = ""
    modifications: dict[str, Any] | None = None


def _ctx(study_id: str, use_golden: bool = False) -> dict[str, Any] | None:
    if use_golden:
        return golden_updcb_context()
    try:
        ctx = get_context(study_id)
        if ctx is None:
            return None
        return ctx.to_dict() if hasattr(ctx, "to_dict") else dict(ctx)  # type: ignore[arg-type]
    except Exception:
        return None


def _hydrate_plan(db: Session, plan_id: str):
    plan = get_plan(plan_id)
    if plan is not None:
        return plan
    study_key = find_study_key_for_statistics(db, plan_id)
    if study_key:
        ensure_db_authoritative(db, study_key)
        return get_plan(plan_id)
    return None


@router.get("/studies/{study_id}/statistics", response_model=StatisticsStudyResponse)
def get_statistics(study_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    plan = latest_plan(study_id)
    panel = ui_statistics_panel(study_id)
    return {
        "study_id": study_id,
        "latest": plan.to_dict() if plan else None,
        "panel": panel,
        "plans": [p.to_dict() for p in list_plans(study_id)],
        "study_mutated": False,
    }


@router.post("/studies/{study_id}/statistics/recompute")
def recompute(
    study_id: str,
    payload: RecomputeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    acc = None
    if payload.acceptance_lower is not None and payload.acceptance_upper is not None:
        acc = (payload.acceptance_lower, payload.acceptance_upper)
    try:
        plan = recompute_statistics_plan(
            study_id=study_id,
            context=_ctx(study_id, payload.use_golden_context),
            design=payload.design,
            parameters=payload.parameters,
            confidence_level=payload.confidence_level,
            confidence_level_source=payload.confidence_level_source,
            acceptance_interval=acc,
            acceptance_source=payload.acceptance_source,
            acceptance_wording=payload.acceptance_wording,
            transformation=payload.transformation,
            transformation_source=payload.transformation_source,
            model=payload.model,
            model_source=payload.model_source,
            analysis_population=payload.analysis_population,
            analysis_population_source=payload.analysis_population_source,
            primary_be_parameters=payload.primary_be_parameters,
            primary_be_source=payload.primary_be_source,
            created_by=payload.created_by,
            ai_select_method=payload.ai_select_method,
            observed_gmr=payload.observed_gmr,
            observed_ci=payload.observed_ci,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "field": e.field}) from e
    after_mutation(db, study_id)
    return plan.to_dict()


@router.get("/studies/{study_id}/statistics/scenarios")
def scenarios(study_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    plan = latest_plan(study_id)
    return {
        "study_id": study_id,
        "scenarios": [s.to_dict() for s in (plan.scenarios if plan else [])],
        "requires_expert_selection": bool(
            plan and any(s.status == "REQUIRES_EXPERT_SELECTION" for s in plan.scenarios)
        ),
    }


@router.get("/statistics/{plan_id}")
def get_one(plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    plan = _hydrate_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="StatisticsPlan not found")
    return plan.to_dict()


@router.get("/statistics/{plan_id}/parameters")
def get_params(plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    plan = _hydrate_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="StatisticsPlan not found")
    return plan_parameters_view(plan)


@router.get("/statistics/{plan_id}/evidence")
def get_evidence(plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    plan = _hydrate_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="StatisticsPlan not found")
    return plan_evidence_view(plan)


@router.post("/statistics/{plan_id}/request-review")
def request_review(plan_id: str, payload: ReviewBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    plan = _hydrate_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="StatisticsPlan not found")
    try:
        out = review_svc.request_review(plan_id, reviewer=payload.reviewer, comment=payload.comment)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "field": e.field}) from e
    after_mutation(db, plan.study_id)
    return out


@router.post("/statistics/{plan_id}/approve")
def approve(plan_id: str, payload: ReviewBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    plan = _hydrate_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="StatisticsPlan not found")
    try:
        out = review_svc.approve_plan(plan_id, reviewer=payload.reviewer, comment=payload.comment)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "field": e.field}) from e
    after_mutation(db, plan.study_id)
    return out


@router.post("/statistics/{plan_id}/reject")
def reject(plan_id: str, payload: ReviewBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    plan = _hydrate_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="StatisticsPlan not found")
    try:
        out = review_svc.reject_plan(plan_id, reviewer=payload.reviewer, comment=payload.comment)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "field": e.field}) from e
    after_mutation(db, plan.study_id)
    return out


@router.post("/statistics/{plan_id}/modify")
def modify(plan_id: str, payload: ReviewBody, db: Session = Depends(get_db)) -> dict[str, Any]:
    plan = _hydrate_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="StatisticsPlan not found")
    try:
        out = review_svc.modify_plan(
            plan_id,
            reviewer=payload.reviewer,
            modifications=payload.modifications or {},
            comment=payload.comment,
            recompute_fn=apply_expert_modifications,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "field": e.field}) from e
    after_mutation(db, plan.study_id)
    return out


@router.post("/studies/{study_id}/statistics/invalidate")
def invalidate(study_id: str, payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_db_authoritative(db, study_id)
    out = invalidate_statistics_on_change(
        study_id, changed_field=str(payload.get("changed_field") or "")
    )
    after_mutation(db, study_id)
    return out


@router.post("/decision-center/fixtures/updcb-real/statistics/recompute")
def golden_recompute(db: Session = Depends(get_db)) -> dict[str, Any]:
    study_id = "UPDCB-02-BE-2026"
    ensure_db_authoritative(db, study_id)
    plan = recompute_statistics_plan(
        study_id=study_id,
        context=golden_updcb_context(),
        created_by="golden-fixture",
    )
    after_mutation(db, study_id)
    return {
        "study_id": study_id,
        "fixture_id": "UPDCB-02-BE-2026-REAL-01",
        "plan": plan.to_dict(),
        "panel": ui_statistics_panel(study_id),
        "study_mutated": False,
    }

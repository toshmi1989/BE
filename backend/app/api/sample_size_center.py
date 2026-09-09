"""Phase 15.4 — Sample Size Engine API (study-scoped)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.decision_store import get_context
from app.domain.exceptions import ValidationError
from app.domain.sample_size_engine import calculate_sample_size_authoritative, ui_sample_size_panel
from app.domain.sample_size_store import (
    calculation_inputs_view,
    calculation_provenance_view,
    get_calculation,
    list_calculations,
)
from app.domain import sample_size_review as review_svc

router = APIRouter(tags=["sample-size"])


class CalculateRequest(BaseModel):
    design: str | None = None
    parameter: str | None = None
    parameters: list[str] | None = None
    expected_ratio: float | None = None
    expected_ratio_source: str | None = None
    alpha: float | None = None
    alpha_source: str | None = None
    power: float | None = None
    power_source: str | None = None
    dropout_percent: float | None = None
    dropout_source: str | None = None
    inflation_method: str | None = None
    be_lower: float | None = None
    be_upper: float | None = None
    be_limits_source: str | None = None
    cv_claim_id: str | None = None
    cv_claim_ids_by_parameter: dict[str, str] | None = None
    current_protocol_n: int | None = None
    current_protocol_n_source: str | None = None
    controlling_parameter: str | None = None
    decision_id: str | None = None
    created_by: str | None = None
    ai_authoritative: bool = False


class ReviewRequest(BaseModel):
    reviewer: str
    comment: str = ""
    decision: str | None = None
    project_to_study: bool = False


def _ctx(study_id: str) -> dict[str, Any] | None:
    try:
        ctx = get_context(study_id)
        return ctx.to_dict() if ctx is not None and hasattr(ctx, "to_dict") else ctx
    except Exception:
        return None


@router.post("/studies/{study_id}/sample-size/calculate")
def calculate(study_id: str, payload: CalculateRequest) -> dict[str, Any]:
    try:
        rec = calculate_sample_size_authoritative(
            study_id=study_id,
            design=payload.design,
            parameter=payload.parameter,
            parameters=payload.parameters,
            expected_ratio=payload.expected_ratio,
            expected_ratio_source=payload.expected_ratio_source,
            alpha=payload.alpha,
            alpha_source=payload.alpha_source,
            power=payload.power,
            power_source=payload.power_source,
            dropout_percent=payload.dropout_percent,
            dropout_source=payload.dropout_source,
            inflation_method=payload.inflation_method,
            be_lower=payload.be_lower,
            be_upper=payload.be_upper,
            be_limits_source=payload.be_limits_source,
            cv_claim_id=payload.cv_claim_id,
            cv_claim_ids_by_parameter=payload.cv_claim_ids_by_parameter,
            current_protocol_n=payload.current_protocol_n,
            current_protocol_n_source=payload.current_protocol_n_source,
            context=_ctx(study_id),
            controlling_parameter=payload.controlling_parameter,
            decision_id=payload.decision_id,
            created_by=payload.created_by,
            ai_authoritative=payload.ai_authoritative,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "field": e.field}) from e
    return rec.to_dict()


@router.get("/studies/{study_id}/sample-size/calculations")
def list_calcs(study_id: str) -> dict[str, Any]:
    rows = list_calculations(study_id)
    return {
        "study_id": study_id,
        "calculations": [r.to_dict() for r in rows],
        "count": len(rows),
    }


@router.get("/studies/{study_id}/sample-size/panel")
def sample_size_panel(study_id: str) -> dict[str, Any]:
    return ui_sample_size_panel(study_id, context=_ctx(study_id))


@router.get("/sample-size/calculations/{calculation_id}")
def get_calc(calculation_id: str) -> dict[str, Any]:
    rec = get_calculation(calculation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Calculation not found")
    return rec.to_dict()


@router.get("/sample-size/calculations/{calculation_id}/inputs")
def get_inputs(calculation_id: str) -> dict[str, Any]:
    rec = get_calculation(calculation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Calculation not found")
    return calculation_inputs_view(rec)


@router.get("/sample-size/calculations/{calculation_id}/provenance")
def get_provenance(calculation_id: str) -> dict[str, Any]:
    rec = get_calculation(calculation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Calculation not found")
    return calculation_provenance_view(rec)


@router.post("/sample-size/calculations/{calculation_id}/request-review")
def request_review(calculation_id: str, payload: ReviewRequest) -> dict[str, Any]:
    try:
        return review_svc.request_review(
            calculation_id, reviewer=payload.reviewer, comment=payload.comment
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "field": e.field}) from e


@router.post("/sample-size/calculations/{calculation_id}/approve")
def approve(calculation_id: str, payload: ReviewRequest) -> dict[str, Any]:
    if not payload.decision:
        raise HTTPException(status_code=400, detail="decision required")
    try:
        return review_svc.approve_calculation(
            calculation_id,
            reviewer=payload.reviewer,
            decision=payload.decision,
            comment=payload.comment,
            project_to_study=payload.project_to_study,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "field": e.field}) from e


@router.post("/sample-size/calculations/{calculation_id}/reject")
def reject(calculation_id: str, payload: ReviewRequest) -> dict[str, Any]:
    try:
        return review_svc.reject_calculation(
            calculation_id, reviewer=payload.reviewer, comment=payload.comment
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail={"message": str(e), "field": e.field}) from e

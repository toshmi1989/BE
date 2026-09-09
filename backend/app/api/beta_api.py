"""Phase 18 — Beta validation API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.domain.beta_observability import get_beta_run, list_beta_runs
from app.domain.beta_registry import case_summary, get_case, list_cases
from app.domain.beta_runner import evaluate_all, evaluate_case, writer_review_bundle
from app.domain.beta_registry import ERROR_TYPES

router = APIRouter(prefix="/beta", tags=["beta"])


class EvaluateIn(BaseModel):
    include_synthetic: bool = True


@router.get("/cases")
def beta_cases(origin: str | None = None) -> dict[str, Any]:
    return {"cases": list_cases(origin=origin), "summary": case_summary()}


@router.get("/cases/{case_id}")
def beta_case(case_id: str) -> dict[str, Any]:
    try:
        return get_case(case_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Case not found") from e


@router.post("/cases/{case_id}/evaluate")
def beta_evaluate(case_id: str) -> dict[str, Any]:
    try:
        return evaluate_case(case_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Case not found") from e


@router.post("/evaluate-all")
def beta_evaluate_all(payload: EvaluateIn | None = None) -> dict[str, Any]:
    payload = payload or EvaluateIn()
    return evaluate_all(include_synthetic=payload.include_synthetic)


@router.get("/error-taxonomy")
def error_taxonomy() -> dict[str, Any]:
    return {
        "types": list(ERROR_TYPES),
        "severity": ["P0 Critical", "P1 Major", "P2 Moderate", "P3 Minor"],
    }


@router.get("/runs")
def beta_runs() -> dict[str, Any]:
    return {"runs": list_beta_runs()}


@router.get("/runs/{workflow_id}")
def beta_run(workflow_id: str) -> dict[str, Any]:
    row = get_beta_run(workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    return row


@router.get("/studies/{study_id}/writer-review")
def writer_review(study_id: str, field: str | None = None) -> dict[str, Any]:
    return writer_review_bundle(study_id, field=field)

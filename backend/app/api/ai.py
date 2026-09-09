from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.phase7 import (
    AIClaimOut,
    AIClaimReviewRequest,
    AIExtractRequest,
    AIExtractResponse,
    AIRunOut,
    AIStatusOut,
)
from app.services import ai_extraction_service as ai

router = APIRouter(tags=["ai"])


@router.get("/ai/status", response_model=AIStatusOut)
def get_ai_status() -> AIStatusOut:
    return ai.ai_status()


@router.post("/projects/{project_id}/ai/extract", response_model=AIExtractResponse)
def extract(project_id: UUID, payload: AIExtractRequest, db: Session = Depends(get_db)) -> AIExtractResponse:
    return ai.run_extraction(db, project_id, payload)


@router.get("/projects/{project_id}/ai/runs", response_model=list[AIRunOut])
def list_runs(project_id: UUID, db: Session = Depends(get_db)) -> list[AIRunOut]:
    return ai.list_ai_runs(db, project_id)


@router.get("/projects/{project_id}/ai/proposed", response_model=list[AIClaimOut])
def list_proposed(project_id: UUID, db: Session = Depends(get_db)) -> list[AIClaimOut]:
    return ai.list_proposed_ai_claims(db, project_id)


@router.post("/projects/{project_id}/ai/claims/{claim_id}/review")
def review_claim(
    project_id: UUID,
    claim_id: UUID,
    payload: AIClaimReviewRequest,
    db: Session = Depends(get_db),
) -> dict:
    return ai.review_ai_claim(db, project_id, claim_id, payload)

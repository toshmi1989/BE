from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.domain.ai_runtime_settings import public_settings_view, update_runtime
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


class AISettingsUpdateIn(BaseModel):
    enabled: bool | None = None
    api_key: str | None = Field(default=None, description="OpenAI API key; never logged")
    clear_api_key: bool = False
    provider: str | None = Field(default="openai", description="openai | local | mock")
    model: str | None = Field(default="gpt-4o-mini")
    base_url: str | None = Field(default="https://api.openai.com/v1")


@router.get("/ai/status", response_model=AIStatusOut)
def get_ai_status() -> AIStatusOut:
    return ai.ai_status()


@router.get("/ai/settings")
def get_ai_settings() -> dict[str, Any]:
    view = public_settings_view()
    st = ai.ai_status()
    return {
        **view,
        "status": st.model_dump(),
    }


@router.put("/ai/settings")
def put_ai_settings(payload: AISettingsUpdateIn) -> dict[str, Any]:
    """Runtime AI config for the process. Assistive only; key stays in memory."""
    provider = (payload.provider or "openai").strip().lower()
    model = (payload.model or "gpt-4o-mini").strip() or "gpt-4o-mini"
    base_url = (payload.base_url or "https://api.openai.com/v1").strip()
    update_runtime(
        enabled=payload.enabled,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=payload.api_key,
        clear_api_key=payload.clear_api_key,
    )
    view = public_settings_view()
    st = ai.ai_status()
    return {
        **view,
        "status": st.model_dump(),
        "saved": True,
    }


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

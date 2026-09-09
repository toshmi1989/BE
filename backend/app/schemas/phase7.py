from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AIStatusOut(BaseModel):
    enabled: bool
    provider: str
    model: str | None = None
    available: bool
    detail: str | None = None


class AIExtractRequest(BaseModel):
    task_type: str  # EXTRACT_PK | EXTRACT_CV | EXTRACT_FOOD | ...
    query: str | None = None
    document_ids: list[UUID] | None = None
    limit_chunks: int = Field(default=12, ge=1, le=50)
    force_mock: bool = False


class AIClaimOut(BaseModel):
    claim_id: UUID | None = None
    evidence_id: UUID | None = None
    field_name: str
    value: str
    normalized_value: dict[str, Any] | None = None
    unit: str | None = None
    source_id: str
    document_id: str
    page: int | str
    chunk_id: str
    evidence_text: str
    confidence: float
    status: str
    origin: str = "AI_PROPOSED"
    model: str | None = None


class AIRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    research_case_id: UUID | None
    provider: str
    model: str | None
    task_type: str
    input_document_ids: list
    prompt_version: str
    schema_version: str
    started_at: datetime | None
    finished_at: datetime | None
    status: str
    token_usage: dict | None
    error: str | None
    output_checksum: str | None
    claim_ids: list
    chunk_ids: list
    created_at: datetime
    updated_at: datetime


class AIExtractResponse(BaseModel):
    run: AIRunOut
    claims: list[AIClaimOut]
    conflicts_detected: int = 0


class AIClaimReviewRequest(BaseModel):
    action: str  # verify | reject | edit_verify
    edited_value: str | None = None
    edited_normalized_value: dict[str, Any] | None = None
    analyte_id: UUID | None = None

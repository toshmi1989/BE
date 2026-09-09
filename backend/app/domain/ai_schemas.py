"""Structured AI extraction schemas — Pydantic only; free text rejected."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class AIClaimDraft(BaseModel):
    field_name: str
    value: str
    normalized_value: dict[str, Any] | None = None
    unit: str | None = None
    source_id: str
    document_id: str
    page: int | str
    chunk_id: str
    evidence_text: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: str = "PROPOSED"

    @field_validator("status")
    @classmethod
    def force_proposed(cls, v: str) -> str:
        # AI may never emit VERIFIED
        return "PROPOSED"

    @field_validator("evidence_text")
    @classmethod
    def non_empty_evidence(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("evidence_text required for grounding")
        return v.strip()

    @field_validator("source_id", "document_id", "chunk_id")
    @classmethod
    def non_empty_ids(cls, v: str) -> str:
        if not v or not str(v).strip():
            raise ValueError("grounding ids required")
        return str(v).strip()


class AIExtractionResult(BaseModel):
    claims: list[AIClaimDraft] = Field(default_factory=list)
    not_found: bool = False
    notes: str | None = None


class ChunkContext(BaseModel):
    source_id: str
    document_id: str
    page: int
    chunk_id: str
    text: str
    source_type: str | None = None


class AIProviderStatus(BaseModel):
    enabled: bool
    provider: str
    model: str | None = None
    available: bool
    detail: str | None = None

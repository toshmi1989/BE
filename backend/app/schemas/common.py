from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.constants import DEFAULT_ENTITY_STATUS, DEFAULT_ORIGIN
from app.domain.provenance import FieldStatus, Origin


class ProvenanceIn(BaseModel):
    status: FieldStatus | None = None
    origin: Origin | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_ids: list[str] | None = None
    extraction_method: str | None = None
    page_ref: str | None = None
    section_ref: str | None = None
    verified_by: str | None = None
    verified_at: datetime | None = None
    notes: str | None = None


class ProvenanceOut(BaseModel):
    status: str
    origin: str
    confidence: float | None = None
    source_ids: list[Any] = Field(default_factory=list)
    extraction_method: str | None = None
    page_ref: str | None = None
    section_ref: str | None = None
    verified_by: str | None = None
    verified_at: datetime | None = None
    notes: str | None = None


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def default_provenance_kwargs() -> dict[str, Any]:
    return {
        "status": DEFAULT_ENTITY_STATUS,
        "origin": DEFAULT_ORIGIN,
        "confidence": None,
        "source_ids": [],
        "extraction_method": None,
        "page_ref": None,
        "section_ref": None,
        "verified_by": None,
        "verified_at": None,
        "notes": None,
    }


def provenance_from_orm(obj: Any) -> ProvenanceOut:
    return ProvenanceOut(
        status=obj.status,
        origin=obj.origin,
        confidence=obj.confidence,
        source_ids=list(obj.source_ids or []),
        extraction_method=obj.extraction_method,
        page_ref=obj.page_ref,
        section_ref=obj.section_ref,
        verified_by=obj.verified_by,
        verified_at=obj.verified_at,
        notes=obj.notes,
    )


class EntityMeta(BaseModel):
    id: UUID
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut

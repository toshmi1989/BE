from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocxBuildRequest(BaseModel):
    mode: str = "DRAFT"  # DRAFT | REVIEW | FINAL
    ensure_protocol: bool = True  # build ProtocolDraft first if missing
    only_sections: list[str] | None = None  # Phase 12B.1 targeted section body replace


class GeneratedDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    protocol_draft_id: UUID | None
    mode: str
    status: str
    filename: str | None
    storage_key: str | None = None  # exposed as opaque key, not filesystem path
    checksum: str | None
    template_version: str | None
    protocol_version: str | None
    generator_version: str | None
    profile_version: str | None
    validation_report: dict | None
    blocking_reasons: list
    table_numbers: dict | None
    error: str | None
    built_at: datetime | None
    created_at: datetime
    updated_at: datetime


class DocxStatusOut(BaseModel):
    latest: GeneratedDocumentOut | None = None
    template_version: str
    generator_version: str
    profile_version: str


class DocxValidationOut(BaseModel):
    document_id: UUID | None = None
    status: str
    validation: dict[str, Any] = Field(default_factory=dict)
    blocking_reasons: list = Field(default_factory=list)

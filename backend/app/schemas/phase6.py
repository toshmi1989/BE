from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ResearchProfileIn(BaseModel):
    requested_product_name: str | None = None
    inn: str | None = None
    dosage: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    requested_subject_count: int | None = None
    country: str | None = None
    regulatory_jurisdiction: str | None = None
    sync_from_client_input: bool = True


class ResearchProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    requested_product_name: str | None
    inn: str | None
    dosage: str | None
    dosage_form: str | None
    route: str | None
    requested_subject_count: int | None
    country: str | None
    regulatory_jurisdiction: str | None
    search_profile: dict
    version: str
    created_at: datetime
    updated_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    source_id: UUID | None
    filename: str
    mime_type: str
    size: int
    checksum: str
    storage_path: str
    status: str
    ingest_warnings: list
    created_at: datetime
    updated_at: datetime


class DocumentPageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    page_number: int
    text: str


class DocumentChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_page_id: UUID
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int


class ResearchSearchRequest(BaseModel):
    query: str
    phrase: bool = False
    source_type: str | None = None
    document_id: UUID | None = None
    limit: int = 50


class SearchHitOut(BaseModel):
    source_id: str | None
    document_id: str
    page: int
    chunk_id: str
    score: float
    snippet: str


class ManualEvidenceRequest(BaseModel):
    source_id: str
    document_id: UUID | None = None
    page: int | str | None = None
    chunk_id: UUID | None = None
    field_code: str
    extracted_text: str
    evidence_type: str | None = None
    section: str | None = None
    auto_detect_conflicts: bool = True


class CompletenessOut(BaseModel):
    required_tasks: list[str]
    completed_tasks: list[str]
    blocked_tasks: list[str]
    missing_evidence: list[str]
    conflicts: int
    open_tasks: list[str]
    score: float
    notes: str
    version: str
    research_case_status: str | None = None


class EvidenceFieldDefinitionOut(BaseModel):
    code: str
    expected_type: str
    unit: str | None
    target_entity: str
    target_field: str
    evidence_type: str
    description: str | None = None

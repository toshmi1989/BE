from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProtocolSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    protocol_id: UUID
    section_code: str
    title: str
    order: int
    parent_section: str | None
    status: str
    generation_status: str
    content_blocks: list
    source_ids: list
    warnings: list
    template_key: str | None
    created_at: datetime
    updated_at: datetime


class ProtocolTableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    protocol_id: UUID
    section_code: str
    table_key: str
    title: str
    order: int
    columns: list
    rows: list
    source_ids: list
    status: str
    display_number: int | None
    created_at: datetime
    updated_at: datetime


class ProtocolReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    protocol_id: UUID
    source_section: str
    target_type: str
    target_id: str
    display_text: str | None


class ProtocolBuildReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    protocol_id: UUID
    generated_sections: list
    unresolved_fields: list
    blocking_issues: list
    warnings: list
    source_count: int
    calculated_values: list
    expert_verified_values: list
    extras: dict | None = None
    created_at: datetime
    updated_at: datetime


class ProtocolDraftOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    protocol_version: str
    template_version: str
    rules_version: str
    generator_version: str
    status: str
    canonical_fingerprint: str | None
    consistency_snapshot: dict | None
    created_at: datetime
    updated_at: datetime
    sections: list[ProtocolSectionOut] = Field(default_factory=list)
    tables: list[ProtocolTableOut] = Field(default_factory=list)
    references: list[ProtocolReferenceOut] = Field(default_factory=list)
    build_report: ProtocolBuildReportOut | None = None


class ProtocolBuildRequest(BaseModel):
    protocol_version: str = "1"
    force: bool = False  # rebuild even if exists


class ProtocolPreviewOut(BaseModel):
    """HTML-oriented tree for frontend preview."""

    protocol_id: UUID
    status: str
    tree: list[dict[str, Any]]
    tables: list[ProtocolTableOut]
    unresolved_fields: list[str]
    blocking_issues: list
    warnings: list

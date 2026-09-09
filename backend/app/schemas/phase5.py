from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ValidationIssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    category: str
    severity: str
    rule_id: str
    entity_type: str | None
    entity_id: str | None
    field: str | None
    message: str
    details: dict
    source_ids: list
    blocking: bool
    status: str
    created_at: datetime
    updated_at: datetime


class ValidationSummaryOut(BaseModel):
    critical: int
    errors: int
    warnings: int
    info: int
    blocking: bool
    total: int = 0


class ValidationRunOut(BaseModel):
    summary: ValidationSummaryOut
    issues: list[ValidationIssueOut]
    consistency_snapshot: dict[str, Any]
    canonical_snapshot: dict[str, Any]
    change_impact_example: dict[str, Any] | None = None


class ChangeImpactRequest(BaseModel):
    changed_entity: str


class ChangeImpactOut(BaseModel):
    changed: str
    normalized_node: str
    revalidate: list[str]
    protocol_generation_prerequisites_stale: bool
    graph_version: str


class ResearchCaseCreate(BaseModel):
    status: str = "NEW"
    client_input_id: UUID | None = None


class ResearchCaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    status: str
    client_input_id: UUID | None
    created_at: datetime
    updated_at: datetime


class ResearchTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    research_case_id: UUID
    task_type: str
    query_profile: dict
    status: str
    priority: int
    assigned_to: str | None
    result_count: int
    notes: str | None
    depends_on_tasks: list = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ResearchTaskCreate(BaseModel):
    task_type: str
    query_profile: dict[str, Any] = Field(default_factory=dict)
    status: str = "TODO"
    priority: int = 50
    assigned_to: str | None = None
    notes: str | None = None
    depends_on_tasks: list[str] = Field(default_factory=list)


class EvidenceClaimIn(BaseModel):
    field_name: str
    value: str | None = None
    normalized_value: dict[str, Any] | None = None
    unit: str | None = None
    confidence: float | None = None
    status: str = "PROPOSED"
    origin: str = "SOURCE_DERIVED"
    source_ids: list[str] = Field(default_factory=list)


class EvidenceCreate(BaseModel):
    source_id: str
    evidence_type: str
    claim: str | None = None
    extracted_text: str | None = None
    page: str | int | None = None
    section: str | None = None
    confidence: float | None = None
    verification_status: str = "UNVERIFIED"
    claims: list[EvidenceClaimIn] = Field(default_factory=list)


class EvidenceClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evidence_id: UUID
    field_name: str
    value: str | None
    normalized_value: dict | None
    unit: str | None
    confidence: float | None
    status: str
    origin: str
    source_ids: list
    created_at: datetime
    updated_at: datetime


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    research_case_id: UUID
    source_id: str
    evidence_type: str
    claim: str | None
    extracted_text: str | None
    page: str | None
    section: str | None
    confidence: float | None
    verification_status: str
    created_at: datetime
    updated_at: datetime
    claims: list[EvidenceClaimOut] = Field(default_factory=list)


class EvidenceConflictCreate(BaseModel):
    field_name: str
    evidence_ids: list[str]
    values: list[Any]
    severity: str = "WARNING"
    resolution: str | None = None


class EvidenceConflictResolve(BaseModel):
    resolution: str
    resolved_by: str | None = None


class EvidenceConflictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    research_case_id: UUID
    field_name: str
    evidence_ids: list
    values: list
    severity: str
    resolution: str | None
    resolved_by: str | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApplyVerifiedRequest(BaseModel):
    claim_ids: list[UUID]
    analyte_id: UUID | None = None


class ApplyVerifiedOut(BaseModel):
    applied: list[dict]
    skipped: list[dict]
    warnings: list[str]

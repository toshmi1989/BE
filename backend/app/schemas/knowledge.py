"""Phase 12A.1 — knowledge / expert-decision API schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None
    rule_code: str
    name: str
    domain: str
    description: str
    condition_expression: str | None
    action_definition: dict
    priority: int
    status: str
    requires_expert_confirmation: bool
    regulatory_basis_id: UUID | None
    source_ids: list
    evidence_claim_ids: list
    version: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime


class KnowledgeRuleCreate(BaseModel):
    project_id: UUID | None = None
    rule_code: str
    name: str
    domain: str
    description: str
    condition_expression: str | None = None
    action_definition: dict[str, Any] = Field(default_factory=dict)
    priority: int = 100
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    regulatory_basis_id: UUID | None = None
    source_ids: list[str] = Field(default_factory=list)
    evidence_claim_ids: list[str] = Field(default_factory=list)
    version: str = "1"


class KnowledgeRuleUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    description: str | None = None
    condition_expression: str | None = None
    action_definition: dict[str, Any] | None = None
    priority: int | None = None
    status: str | None = None
    requires_expert_confirmation: bool | None = None
    regulatory_basis_id: UUID | None = None
    source_ids: list[str] | None = None
    evidence_claim_ids: list[str] | None = None
    version: str | None = None
    reviewed_by: str | None = None
    rejection_reason: str | None = None


class ExpertDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    study_id: UUID | None
    decision_type: str
    target_entity_type: str
    target_entity_id: UUID | None
    proposed_value: dict
    final_value: dict | None
    rationale: str
    status: str
    decided_by: str | None
    decided_at: datetime | None
    evidence_claim_ids: list
    regulatory_basis_ids: list
    previous_decision_id: UUID | None
    version: str
    entity_version: int
    created_at: datetime
    updated_at: datetime


class ExpertDecisionCreate(BaseModel):
    project_id: UUID
    study_id: UUID | None = None
    decision_type: str
    target_entity_type: str
    target_entity_id: UUID | None = None
    proposed_value: dict[str, Any] = Field(default_factory=dict)
    final_value: dict[str, Any] | None = None
    rationale: str
    status: str = "PROPOSED"
    evidence_claim_ids: list[str] = Field(default_factory=list)
    regulatory_basis_ids: list[str] = Field(default_factory=list)
    previous_decision_id: UUID | None = None
    version: str = "1"


class DecisionActionBody(BaseModel):
    decided_by: str | None = None
    rationale: str | None = None


class KnowledgeGapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None
    domain: str
    question: str
    description: str | None
    importance: str
    blocking: bool
    status: str
    related_rule_id: str | None
    related_decision_type: str | None
    resolved_at: datetime | None
    resolved_by: str | None
    resolution: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime


class KnowledgeGapCreate(BaseModel):
    project_id: UUID | None = None
    domain: str
    question: str
    description: str | None = None
    importance: str = "MEDIUM"
    blocking: bool = False
    status: str = "OPEN"
    related_rule_id: str | None = None
    related_decision_type: str | None = None


class KnowledgeGapResolve(BaseModel):
    resolution: str
    resolved_by: str | None = None
    status: str = "RESOLVED"


class RegulatoryBasisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None
    title: str
    source_id: UUID | None
    document_identifier: str | None
    section_reference: str | None
    page_reference: str | None
    paragraph_reference: str | None
    jurisdiction: str | None
    effective_date: date | None
    status: str
    notes: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime


class RegulatoryBasisCreate(BaseModel):
    project_id: UUID | None = None
    title: str
    source_id: UUID | None = None
    document_identifier: str | None = None
    section_reference: str | None = None
    page_reference: str | None = None
    paragraph_reference: str | None = None
    jurisdiction: str | None = None
    effective_date: date | None = None
    status: str = "PROPOSED"
    notes: str | None = None


class ProposalOut(BaseModel):
    """Dict-friendly wrapper for domain proposal / evaluation results."""

    model_config = ConfigDict(extra="allow")

    status: str | None = None
    requires_expert_confirmation: bool | None = None
    knowledge_gaps: list[dict[str, Any]] = Field(default_factory=list)


class ProtocolQAFindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    code: str
    severity: str
    category: str
    message: str
    location: str | None
    expected: str | None
    actual: str | None
    related_canonical_field: str | None
    related_source: str | None
    blocking: bool
    remediation: str | None
    details: dict
    created_at: datetime
    updated_at: datetime


class ProtocolQARunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    status: str
    summary: dict
    findings: list[ProtocolQAFindingOut] = Field(default_factory=list)
    entity_version: int
    created_at: datetime
    updated_at: datetime


class ProtocolDiffItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    comparison_id: UUID
    section: str
    table_key: str | None
    paragraph_or_field: str
    previous_value: str
    current_value: str
    diff_type: str
    risk_level: str
    reason: str
    review_status: str
    created_at: datetime
    updated_at: datetime


class ProtocolComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    previous_protocol_id: str | None
    comparison_version: str
    compared_by: str | None
    status: str
    diff_items: list[ProtocolDiffItemOut] = Field(default_factory=list)
    entity_version: int
    created_at: datetime
    updated_at: datetime


class ProtocolDiffRequest(BaseModel):
    previous_map: dict[str, Any] = Field(default_factory=dict)
    current_map: dict[str, Any] = Field(default_factory=dict)
    previous_protocol_id: str | None = None
    compared_by: str | None = None
    persist: bool = True


class QARunRequest(BaseModel):
    canonical: dict[str, Any] = Field(default_factory=dict)
    displayed: dict[str, Any] | None = None
    document_text: str | None = None
    previous_identity: dict[str, Any] | None = None

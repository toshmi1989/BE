"""Phase 17 — Persistent workspace bags, snapshots, drafts, artifacts, audit, workflow."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class WorkspaceStateBag(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Serialized Phase 14–16 store bundle for a study_key (survives process restart)."""

    __tablename__ = "workspace_state_bags"
    __table_args__ = (UniqueConstraint("study_key", name="uq_workspace_state_study"),)

    study_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    package_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decisions_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    context_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sample_size_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    statistics_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    research_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    workspace_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)


class WorkspaceSnapshotRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable canonical study snapshot versions."""

    __tablename__ = "workspace_snapshots"
    __table_args__ = (UniqueConstraint("study_key", "version", name="uq_snapshot_study_version"),)

    snapshot_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    study_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    based_on_decision_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)


class WorkspaceDecisionRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Permanent expert decision row (recommendation ≠ APPROVED)."""

    __tablename__ = "workspace_decisions"
    __table_args__ = (UniqueConstraint("decision_id", "version", name="uq_ws_decision_ver"),)

    decision_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    study_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    selected_option: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    # PROPOSED | PENDING_REVIEW | APPROVED | REJECTED | SUPERSEDED
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class WorkspaceEvidenceClaimRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workspace_evidence_claims"
    __table_args__ = (UniqueConstraint("claim_key", name="uq_ws_claim_key"),)

    claim_key: Mapped[str] = mapped_column(String(128), nullable=False)
    study_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chunk: Mapped[str | None] = mapped_column(String(128), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    # PROPOSED | VERIFIED | REJECTED
    applicability: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claim_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class WorkspaceDocumentRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workspace_documents"
    __table_args__ = (UniqueConstraint("document_id", name="uq_ws_document_id"),)

    document_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    safe_storage_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, default="OTHER")
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    uploaded_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingestion_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UPLOADED")
    classification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)


class WorkspaceProtocolDraftRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable protocol draft versions for workspace (canonical path)."""

    __tablename__ = "workspace_protocol_drafts"
    __table_args__ = (UniqueConstraint("study_key", "version", name="uq_ws_protocol_ver"),)

    protocol_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    study_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="REVIEW")
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    preflight_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    based_on: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    sections_payload: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    preview_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)


class WorkspaceProtocolArtifact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Persistent generated DOCX artifact — download serves stored bytes, never rebuild."""

    __tablename__ = "workspace_protocol_artifacts"
    __table_args__ = (UniqueConstraint("artifact_id", name="uq_ws_artifact_id"),)

    artifact_id: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    study_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    generated_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision_set: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    statistics_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sample_size_version: Mapped[str | None] = mapped_column(String(64), nullable=True)


class WorkspaceAuditEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workspace_audit_events"

    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True, index=True)
    study_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    old_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    who: Mapped[str | None] = mapped_column(String(255), nullable=True)


class WorkspaceWorkflowRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workspace_workflow_runs"
    __table_args__ = (UniqueConstraint("workflow_id", name="uq_ws_workflow_id"),)

    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="INGESTING")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="RUNNING")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

"""Persisted ExpertDecision rows — Phase 12A.1 knowledge foundation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ExpertDecisionRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin):
    """Formal expert decision attached to a project (study_id optional linkage)."""

    __tablename__ = "expert_decisions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    study_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("studies.id", ondelete="SET NULL"), nullable=True
    )
    decision_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    proposed_value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    final_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    decided_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_claim_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    regulatory_basis_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    previous_decision_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("expert_decisions.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")

    project: Mapped[Project] = relationship("Project", back_populates="expert_decisions")
    previous_decision: Mapped[ExpertDecisionRecord | None] = relationship(
        "ExpertDecisionRecord",
        remote_side="ExpertDecisionRecord.id",
        foreign_keys=[previous_decision_id],
    )

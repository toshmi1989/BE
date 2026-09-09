"""Persisted KnowledgeRule rows — Phase 12A.1 knowledge foundation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.regulatory_basis import RegulatoryBasisRecord


class KnowledgeRuleRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin):
    """Project-scoped or global (project_id NULL) knowledge rule."""

    __tablename__ = "knowledge_rules"
    __table_args__ = (UniqueConstraint("rule_code", name="uq_knowledge_rules_rule_code"),)

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rule_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    condition_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_definition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    requires_expert_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    regulatory_basis_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("regulatory_bases.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_claim_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project | None] = relationship("Project", back_populates="knowledge_rules")
    regulatory_basis: Mapped[RegulatoryBasisRecord | None] = relationship(
        "RegulatoryBasisRecord", back_populates="knowledge_rules"
    )

"""Persisted RegulatoryBasis rows — Phase 12A.1 knowledge foundation."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.knowledge_rule import KnowledgeRuleRecord
    from app.models.project import Project


class RegulatoryBasisRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin):
    """Global or project-scoped regulatory citation / basis record."""

    __tablename__ = "regulatory_bases"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    document_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    section_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    paragraph_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project | None] = relationship("Project", back_populates="regulatory_bases")
    knowledge_rules: Mapped[list[KnowledgeRuleRecord]] = relationship(
        "KnowledgeRuleRecord", back_populates="regulatory_basis"
    )

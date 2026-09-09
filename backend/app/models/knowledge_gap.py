"""Persisted KnowledgeGap rows — Phase 12A.1 knowledge foundation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class KnowledgeGapRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin):
    """Open knowledge gap — system must not invent values when information is missing."""

    __tablename__ = "knowledge_gaps"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    domain: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance: Mapped[str] = mapped_column(String(32), nullable=False, default="MEDIUM")
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")
    related_rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    related_decision_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project | None] = relationship("Project", back_populates="knowledge_gaps")

"""Persisted ExpertRule rows — Phase 12A framework (catalog may be empty)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ExpertRuleRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin):
    """Project-scoped or global (project_id NULL) expert rule placeholder."""

    __tablename__ = "expert_rules"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    applies_to: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[str | None] = mapped_column(String(512), nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNVERIFIED")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project | None] = relationship("Project", back_populates="expert_rules")

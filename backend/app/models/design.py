from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.domain.constants import DEFAULT_DECISION_STATUS
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class Design(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    """Structured study design — single source of truth per project."""

    __tablename__ = "designs"
    __table_args__ = (UniqueConstraint("project_id", name="uq_designs_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    type: Mapped[str] = mapped_column(String(64), nullable=False)
    periods: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sequences: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    treatments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    randomization: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    blinding: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    food_condition: Mapped[str | None] = mapped_column(String(32), nullable=True)
    stage_configuration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DEFAULT_DECISION_STATUS
    )
    recommendation_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="design")

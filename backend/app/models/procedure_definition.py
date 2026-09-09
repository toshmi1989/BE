"""Persisted procedure definitions linked to a project (Phase 12A)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.procedure_schedule import ProcedureScheduleRecord


class ProcedureDefinitionRecord(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin
):
    __tablename__ = "procedure_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_procedure_definitions_project_code"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("procedure_schedules.id", ondelete="SET NULL"),
        nullable=True,
    )

    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relative_time_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    condition: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rule_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    project: Mapped[Project] = relationship("Project", back_populates="procedure_definitions")
    schedule: Mapped[ProcedureScheduleRecord | None] = relationship(
        "ProcedureScheduleRecord", back_populates="procedures"
    )

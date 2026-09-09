"""Persisted ProcedureSchedule header (Phase 12A)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.procedure_definition import ProcedureDefinitionRecord


class ProcedureScheduleRecord(
    Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin
):
    __tablename__ = "procedure_schedules"
    __table_args__ = (UniqueConstraint("project_id", name="uq_procedure_schedules_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    dependency_trace: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    composition_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="procedure_schedule")
    procedures: Mapped[list[ProcedureDefinitionRecord]] = relationship(
        "ProcedureDefinitionRecord",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )

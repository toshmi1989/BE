from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class SubjectPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    """Separate N fields — never collapse into one number."""

    __tablename__ = "subject_plans"
    __table_args__ = (UniqueConstraint("project_id", name="uq_subject_plans_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    target_evaluable_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_randomized_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reserve_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_screened_n: Mapped[int | None] = mapped_column(Integer, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="subjects")

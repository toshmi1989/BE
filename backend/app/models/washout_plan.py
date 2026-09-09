from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class WashoutPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "washout_plans"
    __table_args__ = (UniqueConstraint("project_id", name="uq_washout_plans_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    calculated_minimum: Mapped[float | None] = mapped_column(Float, nullable=True)
    selected_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(16), nullable=False, default="day")
    rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rule_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_washout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    project: Mapped[Project] = relationship("Project", back_populates="washout")

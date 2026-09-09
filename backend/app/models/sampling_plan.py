from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.design import Design
    from app.models.project import Project
    from app.models.sampling_point import SamplingPoint


class SamplingPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "sampling_plans"
    __table_args__ = (UniqueConstraint("project_id", name="uq_sampling_plans_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    design_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("designs.id", ondelete="SET NULL"), nullable=True
    )

    total_points_per_period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_observation_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    validation_issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    project: Mapped[Project] = relationship("Project", back_populates="sampling")
    design: Mapped[Design | None] = relationship("Design")
    points: Mapped[list[SamplingPoint]] = relationship(
        "SamplingPoint",
        back_populates="sampling_plan",
        cascade="all, delete-orphan",
        order_by="SamplingPoint.sequence_order",
    )

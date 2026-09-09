from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class BloodVolumeCalculation(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "blood_volume_calculations"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_blood_volume_calculations_project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    subjects: Mapped[int] = mapped_column(Integer, nullable=False)
    periods: Mapped[int] = mapped_column(Integer, nullable=False)
    sampling_points_per_period: Mapped[int] = mapped_column(Integer, nullable=False)
    blood_volume_per_pk_sample_ml: Mapped[float] = mapped_column(Float, nullable=False)
    screening_volume_ml: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    safety_laboratory_volume_ml: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    other_blood_volume_ml: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reserve_duplicate_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    pk_volume_ml: Mapped[float] = mapped_column(Float, nullable=False)
    screening_total_ml: Mapped[float] = mapped_column(Float, nullable=False)
    safety_total_ml: Mapped[float] = mapped_column(Float, nullable=False)
    other_total_ml: Mapped[float] = mapped_column(Float, nullable=False)
    total_volume_ml: Mapped[float] = mapped_column(Float, nullable=False)
    volume_per_subject_ml: Mapped[float] = mapped_column(Float, nullable=False)
    volume_per_period_ml: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    breakdown: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    sample_count: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    project: Mapped[Project] = relationship("Project", back_populates="blood_volume")

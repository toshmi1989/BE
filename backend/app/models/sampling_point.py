from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.sampling_plan import SamplingPlan


class SamplingPoint(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "sampling_points"

    sampling_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sampling_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    time_h: Mapped[float] = mapped_column(Float, nullable=False)
    time_min: Mapped[float] = mapped_column(Float, nullable=False)
    window_before_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    window_after_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    analyte_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    sampling_plan: Mapped[SamplingPlan] = relationship("SamplingPlan", back_populates="points")

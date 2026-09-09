from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.domain.constants import DEFAULT_DECISION_STATUS
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class FoodCondition(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "food_conditions"
    __table_args__ = (UniqueConstraint("project_id", name="uq_food_conditions_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    condition: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    meal_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    composition: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    meal_start_offset_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dose_after_meal_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    water_volume_ml: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DEFAULT_DECISION_STATUS
    )

    project: Mapped[Project] = relationship("Project", back_populates="food")

"""Persisted SafetyPlan (Phase 12A) — no clinical thresholds stored as defaults."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class SafetyPlanRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "safety_plans"
    __table_args__ = (UniqueConstraint("project_id", name="uq_safety_plans_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    physical_exam: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    vital_signs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ECG: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    laboratory_tests: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    AE: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    SAE: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pregnancy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    follow_up: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    safety_periods: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    static_verified_refs: Mapped[list] = mapped_column(
        JSON, nullable=False, default=lambda: ["SAFE.T13", "SAFE.T14", "SAFE.T15", "SAFE.T16"]
    )

    project: Mapped[Project] = relationship("Project", back_populates="safety_plan")

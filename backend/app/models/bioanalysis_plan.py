"""Persisted BioanalysisPlan (Phase 12A) — fields nullable; no template defaults."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class BioanalysisPlanRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "bioanalysis_plans"
    __table_args__ = (UniqueConstraint("project_id", name="uq_bioanalysis_plans_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    matrix: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tube_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    anticoagulant: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sample_volume_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    centrifugation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    centrifugation_temperature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    centrifugation_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    aliquot_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aliquot_volume_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    storage_temperature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_duration: Mapped[str | None] = mapped_column(String(64), nullable=True)
    shipment_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    analytical_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_preparation: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_standard: Mapped[str | None] = mapped_column(String(255), nullable=True)
    calibration_range: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lloq: Mapped[str | None] = mapped_column(String(128), nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    field_sources: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    project: Mapped[Project] = relationship("Project", back_populates="bioanalysis_plan")

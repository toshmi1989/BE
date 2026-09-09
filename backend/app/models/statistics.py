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


class CVPool(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "cv_pools"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    method: Mapped[str] = mapped_column(String(128), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    pooled_cv: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_interval: Mapped[list | None] = mapped_column(JSON, nullable=True)
    inputs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cv_study_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    mismatches: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    parameter: Mapped[str | None] = mapped_column(String(64), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="cv_pools")


class CVSelection(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "cv_selections"
    __table_args__ = (UniqueConstraint("project_id", name="uq_cv_selections_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    selected_cv: Mapped[float | None] = mapped_column(Float, nullable=True)
    cv_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="percent")
    selection_method: Mapped[str] = mapped_column(String(64), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_study_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    parameter: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analyte_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="cv_selection")


class StatisticalConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "statistical_configs"
    __table_args__ = (UniqueConstraint("project_id", name="uq_statistical_configs_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    alpha: Mapped[float] = mapped_column(Float, nullable=False)
    power: Mapped[float] = mapped_column(Float, nullable=False)
    be_lower: Mapped[float] = mapped_column(Float, nullable=False)
    be_upper: Mapped[float] = mapped_column(Float, nullable=False)
    expected_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    analysis_method: Mapped[str] = mapped_column(String(128), nullable=False)
    transformation: Mapped[str] = mapped_column(String(64), nullable=False)
    software: Mapped[str | None] = mapped_column(String(128), nullable=True)
    algorithm_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    defaults_source: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="statistical_config")


class SampleSizeCalculation(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "sample_size_calculations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    design_type: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_cv: Mapped[float | None] = mapped_column(Float, nullable=True)
    parameter: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evaluable_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    randomized_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    screened_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    method: Mapped[str] = mapped_column(String(128), nullable=False)
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    software_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    achieved_power: Mapped[float | None] = mapped_column(Float, nullable=True)
    inputs_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    reserve_formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="sample_size_calculations")


class SubjectReserveCalculation(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "subject_reserve_calculations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sample_size_calculation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sample_size_calculations.id", ondelete="SET NULL"),
        nullable=True,
    )
    evaluable_n: Mapped[int] = mapped_column(Integer, nullable=False)
    dropout_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reserve_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    screen_failure_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    randomized_n: Mapped[int] = mapped_column(Integer, nullable=False)
    screened_n: Mapped[int] = mapped_column(Integer, nullable=False)
    formula: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    rounding_rule_id: Mapped[str] = mapped_column(String(128), nullable=False)

    project: Mapped[Project] = relationship("Project", back_populates="subject_reserve_calculations")

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class CVStudy(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "cv_studies"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    study_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publication_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    analyte_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("analytes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parameter: Mapped[str] = mapped_column(String(64), nullable=False)
    design: Mapped[str | None] = mapped_column(String(64), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dose: Mapped[str | None] = mapped_column(String(128), nullable=True)
    n_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    n_be_analysis: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cv_value: Mapped[float] = mapped_column(Float, nullable=False)
    cv_unit: Mapped[str] = mapped_column(String(32), nullable=False, default="percent")
    cv_type: Mapped[str] = mapped_column(String(64), nullable=False, default="WITHIN_SUBJECT")
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    project: Mapped[Project] = relationship("Project", back_populates="cv_studies")

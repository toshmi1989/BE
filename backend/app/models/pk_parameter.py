from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.analyte import Analyte
    from app.models.project import Project


class PKParameter(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "pk_parameters"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analyte_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("analytes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    parameter_code: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    calculated_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # evidence items: {source_id, page, section, extracted_text, confidence, status}

    project: Mapped[Project] = relationship("Project", back_populates="pk_parameters")
    analyte: Mapped[Analyte] = relationship("Analyte", back_populates="pk_parameters")

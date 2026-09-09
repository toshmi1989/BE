from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.pk_parameter import PKParameter
    from app.models.project import Project


class Analyte(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "analytes"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False, default="PARENT")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    matrix: Mapped[str | None] = mapped_column(String(128), nullable=True)
    assay_method: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lloq: Mapped[float | None] = mapped_column(Float, nullable=True)
    uloq: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmax_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmax_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    tmax_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="h")
    half_life_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    half_life_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    half_life_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="h")
    pk_parameter_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    project: Mapped[Project] = relationship("Project", back_populates="analytes")
    pk_parameters: Mapped[list[PKParameter]] = relationship(
        "PKParameter", back_populates="analyte", cascade="all, delete-orphan"
    )

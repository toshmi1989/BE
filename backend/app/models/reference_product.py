from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ReferenceProduct(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "reference_products"
    __table_args__ = (UniqueConstraint("project_id", name="uq_reference_products_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    trade_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    registration_holder: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dosage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dosage_form: Mapped[str | None] = mapped_column(String(128), nullable=True)
    route: Mapped[str | None] = mapped_column(String(128), nullable=True)
    composition: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    storage_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    shelf_life: Mapped[str | None] = mapped_column(String(128), nullable=True)
    registration_status: Mapped[str | None] = mapped_column(String(128), nullable=True)
    purchased_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    batch_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    packaging: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="reference_product")

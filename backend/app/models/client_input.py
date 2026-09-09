from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ClientInput(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    """Minimal sponsor/client request — distinct from confirmed Product entity."""

    __tablename__ = "client_inputs"
    __table_args__ = (UniqueConstraint("project_id", name="uq_client_inputs_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    requested_product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dosage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dosage_form: Mapped[str | None] = mapped_column(String(128), nullable=True)
    route: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_subject_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="client_input")

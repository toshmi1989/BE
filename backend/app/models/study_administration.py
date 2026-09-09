from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class StudyAdministration(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "study_administration"
    __table_args__ = (UniqueConstraint("project_id", name="uq_study_administration_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    insurance_provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_policy: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    financing_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    financing_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_contacts: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="study_administration")

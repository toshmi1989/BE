from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.domain.constants import DEFAULT_STUDY_PHASE, DEFAULT_STUDY_STATUS
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.sponsor import Sponsor


class Study(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    __tablename__ = "studies"
    __table_args__ = (UniqueConstraint("project_id", name="uq_studies_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    sponsor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sponsors.id", ondelete="SET NULL"), nullable=True
    )

    protocol_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    version_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phase: Mapped[str] = mapped_column(String(64), nullable=False, default=DEFAULT_STUDY_PHASE)
    study_status: Mapped[str] = mapped_column(String(32), nullable=False, default=DEFAULT_STUDY_STATUS)

    project: Mapped[Project] = relationship("Project", back_populates="study")
    sponsor: Mapped[Sponsor | None] = relationship(
        "Sponsor", back_populates="studies", foreign_keys=[sponsor_id]
    )

"""Project-scoped study-party organization (CRO / site / ethics / insurance).

NOT the tenant Organization used for auth isolation.
Canonical tenant org lives in app.models.auth.Organization.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.sponsor import Sponsor


class StudyParty(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    """Party participating in a Project (protocol administration)."""

    __tablename__ = "organizations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False, default="OTHER")
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="organizations")
    sponsor_link: Mapped[Sponsor | None] = relationship(
        "Sponsor",
        back_populates="organization",
        uselist=False,
        foreign_keys="Sponsor.organization_id",
    )


# Backward-compatible name used by older Project APIs/tests
Organization = StudyParty

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ProjectVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Versioned snapshot of project aggregate for reproducible protocol generation."""

    __tablename__ = "project_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_project_versions_number"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    ruleset_version: Mapped[str] = mapped_column(String(32), nullable=False, default="0")
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    project: Mapped[Project] = relationship("Project", back_populates="versions")

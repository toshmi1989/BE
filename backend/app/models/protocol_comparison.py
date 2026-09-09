"""Previous-protocol comparison persistence — Phase 12A.1 knowledge foundation."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class PreviousProtocolComparisonRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin):
    """Comparison of current project state vs a previous protocol."""

    __tablename__ = "previous_protocol_comparisons"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_protocol_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    comparison_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1")
    compared_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")

    project: Mapped[Project] = relationship("Project", back_populates="protocol_comparisons")
    diff_items: Mapped[list[ProtocolDiffItemRecord]] = relationship(
        "ProtocolDiffItemRecord",
        back_populates="comparison",
        cascade="all, delete-orphan",
    )


class ProtocolDiffItemRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single diff row within a previous-protocol comparison."""

    __tablename__ = "protocol_diff_items"

    comparison_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("previous_protocol_comparisons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section: Mapped[str] = mapped_column(String(128), nullable=False)
    table_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    paragraph_or_field: Mapped[str] = mapped_column(String(255), nullable=False)
    previous_value: Mapped[str] = mapped_column(Text, nullable=False)
    current_value: Mapped[str] = mapped_column(Text, nullable=False)
    diff_type: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="OPEN")

    comparison: Mapped[PreviousProtocolComparisonRecord] = relationship(
        "PreviousProtocolComparisonRecord", back_populates="diff_items"
    )

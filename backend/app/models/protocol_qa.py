"""Protocol QA run / finding persistence — Phase 12A.1 knowledge foundation."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ProtocolQARunRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin):
    """One QA evaluation pass for a project (generated_at via created_at)."""

    __tablename__ = "protocol_qa_runs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    project: Mapped[Project] = relationship("Project", back_populates="protocol_qa_runs")
    findings: Mapped[list[ProtocolQAFindingRecord]] = relationship(
        "ProtocolQAFindingRecord",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class ProtocolQAFindingRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single finding within a Protocol QA run."""

    __tablename__ = "protocol_qa_findings"

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("protocol_qa_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_canonical_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    related_source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blocking: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remediation: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    run: Mapped[ProtocolQARunRecord] = relationship("ProtocolQARunRecord", back_populates="findings")

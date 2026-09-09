from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ResearchCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_cases"
    __table_args__ = (UniqueConstraint("project_id", name="uq_research_cases_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    client_input_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="research_case")
    tasks: Mapped[list[ResearchTask]] = relationship(
        "ResearchTask", back_populates="research_case", cascade="all, delete-orphan"
    )
    evidences: Mapped[list[Evidence]] = relationship(
        "Evidence", back_populates="research_case", cascade="all, delete-orphan"
    )
    conflicts: Mapped[list[EvidenceConflict]] = relationship(
        "EvidenceConflict", back_populates="research_case", cascade="all, delete-orphan"
    )


class ResearchTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_tasks"

    research_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    query_profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="TODO")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    assigned_to: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    depends_on_tasks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    research_case: Mapped[ResearchCase] = relationship("ResearchCase", back_populates="tasks")


class Evidence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidences"

    research_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    claim: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page: Mapped[str | None] = mapped_column(String(64), nullable=True)
    section: Mapped[str | None] = mapped_column(String(128), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="UNVERIFIED")

    research_case: Mapped[ResearchCase] = relationship("ResearchCase", back_populates="evidences")
    claims: Mapped[list[EvidenceClaim]] = relationship(
        "EvidenceClaim", back_populates="evidence", cascade="all, delete-orphan"
    )


class EvidenceClaim(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidence_claims"

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evidences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="SOURCE_DERIVED")
    source_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    evidence: Mapped[Evidence] = relationship("Evidence", back_populates="claims")


class EvidenceConflict(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidence_conflicts"

    research_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    values: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="WARNING")
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    research_case: Mapped[ResearchCase] = relationship("ResearchCase", back_populates="conflicts")

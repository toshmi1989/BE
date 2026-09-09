"""Protocol draft persistence — assembly only, no DOCX."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project


class ProtocolDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "protocol_drafts"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    protocol_version: Mapped[str] = mapped_column(String(64), nullable=False, default="1")
    template_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    canonical_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    consistency_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="protocol_drafts")
    sections: Mapped[list[ProtocolSection]] = relationship(
        "ProtocolSection",
        back_populates="protocol",
        cascade="all, delete-orphan",
        order_by="ProtocolSection.order",
    )
    tables: Mapped[list[ProtocolTable]] = relationship(
        "ProtocolTable",
        back_populates="protocol",
        cascade="all, delete-orphan",
        order_by="ProtocolTable.order",
    )
    references: Mapped[list[ProtocolReference]] = relationship(
        "ProtocolReference",
        back_populates="protocol",
        cascade="all, delete-orphan",
    )
    build_report: Mapped[ProtocolBuildReport | None] = relationship(
        "ProtocolBuildReport",
        back_populates="protocol",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ProtocolSection(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "protocol_sections"

    protocol_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("protocol_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_section: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    generation_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    content_blocks: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    template_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    protocol: Mapped[ProtocolDraft] = relationship("ProtocolDraft", back_populates="sections")


class ProtocolTable(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "protocol_tables"

    protocol_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("protocol_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_code: Mapped[str] = mapped_column(String(32), nullable=False)
    table_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    columns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="GENERATED")
    display_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    protocol: Mapped[ProtocolDraft] = relationship("ProtocolDraft", back_populates="tables")


class ProtocolReference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "protocol_references"

    protocol_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("protocol_drafts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_section: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)  # section|table|appendix|figure
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    display_text: Mapped[str | None] = mapped_column(String(255), nullable=True)

    protocol: Mapped[ProtocolDraft] = relationship("ProtocolDraft", back_populates="references")


class ProtocolBuildReport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "protocol_build_reports"

    protocol_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("protocol_drafts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    generated_sections: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    unresolved_fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    blocking_issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    calculated_values: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    expert_verified_values: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    extras: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    protocol: Mapped[ProtocolDraft] = relationship("ProtocolDraft", back_populates="build_report")

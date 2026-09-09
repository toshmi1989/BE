"""Generated DOCX document metadata — never overwrite prior versions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.protocol import ProtocolDraft


class GeneratedDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "generated_documents"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    protocol_draft_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("protocol_drafts.id", ondelete="SET NULL"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")
    # QUEUED | BUILDING | READY | BLOCKED | FAILED
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)  # relative key, not raw FS path to clients
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    protocol_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generator_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    profile_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    validation_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    blocking_reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    table_numbers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="generated_documents")
    protocol_draft: Mapped[ProtocolDraft | None] = relationship("ProtocolDraft")

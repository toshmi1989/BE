from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from app.domain.constants import DEFAULT_ENTITY_STATUS, DEFAULT_ORIGIN


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class VersionedMixin:
    """Optimistic / entity versioning hook for future ProjectVersion snapshots."""

    entity_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ProvenanceMixin:
    """Critical-field provenance attached to domain entities."""

    status: Mapped[str] = mapped_column(String(32), nullable=False, default=DEFAULT_ENTITY_STATUS)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default=DEFAULT_ORIGIN)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    extraction_method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    section_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

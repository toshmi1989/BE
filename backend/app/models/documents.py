from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.source import Source


class ResearchProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "research_profiles"
    __table_args__ = (UniqueConstraint("project_id", name="uq_research_profiles_project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    requested_product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dosage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dosage_form: Mapped[str | None] = mapped_column(String(128), nullable=True)
    route: Mapped[str | None] = mapped_column(String(128), nullable=True)
    requested_subject_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    regulatory_jurisdiction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    search_profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="SEARCH.PROFILE.v1")

    project: Mapped[Project] = relationship("Project", back_populates="research_profile")


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "documents"

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="UPLOADED")
    ingest_warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    project: Mapped[Project] = relationship("Project", back_populates="documents")
    source: Mapped[Source | None] = relationship("Source")
    pages: Mapped[list[DocumentPage]] = relationship(
        "DocumentPage", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentPage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_doc_page"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    document: Mapped[Document] = relationship("Document", back_populates="pages")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        "DocumentChunk", back_populates="page", cascade="all, delete-orphan"
    )


class DocumentChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_chunks"

    document_page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("document_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    page: Mapped[DocumentPage] = relationship("DocumentPage", back_populates="chunks")


class EvidenceFieldDefinitionRow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "evidence_field_definitions"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expected_type: Mapped[str] = mapped_column(String(32), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_entity: Mapped[str] = mapped_column(String(64), nullable=False)
    target_field: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

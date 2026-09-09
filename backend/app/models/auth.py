"""Phase 17.5 — Canonical tenant Organization (+ StudyParty for project roles).

Canonical tenancy model:
  Organization (table workspace_organizations)
    ├── OrgMembership / UserAccount
    └── WorkspaceStudy

Project study-party orgs (CRO/site/ethics) live as StudyParty
(table organizations, project-scoped) — not a second tenant model.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Canonical tenant organization (auth + workspace isolation)."""

    __tablename__ = "workspace_organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")

    memberships: Mapped[list["OrgMembership"]] = relationship(
        "OrgMembership", back_populates="organization", cascade="all, delete-orphan"
    )
    studies: Mapped[list["WorkspaceStudy"]] = relationship(
        "WorkspaceStudy", back_populates="organization", cascade="all, delete-orphan"
    )


# Backward-compatible alias (Phase 17 name)
WorkspaceOrganization = Organization


class UserAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_accounts"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")

    memberships: Mapped[list["OrgMembership"]] = relationship(
        "OrgMembership", back_populates="user", cascade="all, delete-orphan"
    )


class OrgMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "org_memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_membership"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspace_organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="VIEWER")

    organization: Mapped[Organization] = relationship("Organization", back_populates="memberships")
    user: Mapped[UserAccount] = relationship("UserAccount", back_populates="memberships")


class WorkspaceStudy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Canonical workspace study keyed by stable study_key."""

    __tablename__ = "workspace_studies"
    __table_args__ = (UniqueConstraint("organization_id", "study_key", name="uq_org_study_key"),)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("workspace_organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    study_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sponsor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dose: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(64), nullable=False, default="DRAFT")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True
    )

    organization: Mapped[Organization] = relationship("Organization", back_populates="studies")

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.db import Base
from app.models.mixins import ProvenanceMixin, TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.project import Project


class EligibilityCriterion(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin, ProvenanceMixin):
    """Single shared criterion — Protocol Engine will reuse this object later."""

    __tablename__ = "eligibility_criteria"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "category",
            "number",
            name="uq_eligibility_project_category_number",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    category: Mapped[str] = mapped_column(String(32), nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    project: Mapped[Project] = relationship("Project", back_populates="eligibility_criteria")

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.db import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SourceRankingConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "source_ranking_configs"

    version: Mapped[str] = mapped_column(String(64), nullable=False)
    rules: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

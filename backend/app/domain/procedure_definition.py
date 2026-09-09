"""ProcedureDefinition — structured procedure row (Phase 12A)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from app.domain.content_foundation_constants import PROCEDURE_CATEGORIES, PROCEDURE_STAGES


@dataclass
class ProcedureDefinition:
    code: str
    name: str
    category: str
    stage: str
    id: str | None = None
    period: int | None = None
    relative_time_min: float | None = None
    duration_min: float | None = None
    sequence_order: int = 0
    mandatory: bool = True
    condition: str | None = None
    source_ids: list[str] = field(default_factory=list)
    origin: str = "SOURCE_DERIVED"
    status: str = "PROPOSED"
    rule_ids: list[str] = field(default_factory=list)
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = str(uuid4())
        if self.category not in PROCEDURE_CATEGORIES:
            raise ValueError(f"Invalid procedure category: {self.category}")
        if self.stage not in PROCEDURE_STAGES:
            raise ValueError(f"Invalid procedure stage: {self.stage}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_procedure_definition(proc: ProcedureDefinition) -> list[str]:
    """Structural validation only — no clinical rules."""
    errors: list[str] = []
    if not proc.code:
        errors.append("code required")
    if not proc.name:
        errors.append("name required")
    if proc.category not in PROCEDURE_CATEGORIES:
        errors.append(f"category not in catalog: {proc.category}")
    if proc.stage not in PROCEDURE_STAGES:
        errors.append(f"stage not in catalog: {proc.stage}")
    if proc.relative_time_min is not None and proc.period is None and proc.stage.startswith("PERIOD"):
        errors.append("period recommended when relative_time_min set on PERIOD stage")
    return errors

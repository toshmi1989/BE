"""SampleProcessingDefinition — Phase 12A.2 technical shell (no medical defaults)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SampleProcessingDefinition:
    sample_type: str | None = None
    anticoagulant: str | None = None
    processing_steps: list[str] = field(default_factory=list)
    centrifugation: str | None = None
    aliquoting: str | None = None
    storage: str | None = None
    shipping: str | None = None
    stability: str | None = None
    source_ids: list[str] = field(default_factory=list)
    evidence_claim_ids: list[str] = field(default_factory=list)
    status: str = "UNRESOLVED"
    notes: str = "Empty shell — no universal anticoagulant/centrifugation/temperature defaults"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def unresolved_fields(self) -> list[str]:
        keys = (
            "sample_type",
            "anticoagulant",
            "centrifugation",
            "aliquoting",
            "storage",
            "shipping",
            "stability",
        )
        out = [k for k in keys if getattr(self, k) in (None, "")]
        if not self.processing_steps:
            out.append("processing_steps")
        return out


def empty_sample_processing() -> SampleProcessingDefinition:
    return SampleProcessingDefinition()

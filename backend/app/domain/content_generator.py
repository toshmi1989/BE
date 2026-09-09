"""ProtocolContentGenerator interface — Phase 12A.

Safe generators only for already-known / non-expert-dependent content.
Substantive medical wording deferred until expert interview.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.domain.content_provenance import (
    ContentProvenance,
    expert_required_provenance,
    merge_provenance_into_block,
    unresolved_provenance,
)
from app.domain.display_value_registry import find_raw_enums_in_text


@dataclass
class ContentGenerationResult:
    section_code: str
    blocks: list[dict[str, Any]] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    status: str = "DRAFT"
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_code": self.section_code,
            "blocks": self.blocks,
            "source_ids": self.source_ids,
            "unresolved": self.unresolved,
            "status": self.status,
            "notes": self.notes,
        }


class ProtocolContentGenerator(ABC):
    """Technical interface for section content generation."""

    @abstractmethod
    def generate(
        self,
        section_code: str,
        canonical_snapshot: dict[str, Any],
        evidence_context: dict[str, Any] | None = None,
    ) -> ContentGenerationResult:
        raise NotImplementedError


# Sections that already have deterministic known-data generators in assembly (safe to surface).
SAFE_KNOWN_SECTION_CODES: frozenset[str] = frozenset(
    {
        "SYNOPSIS",
        "1.1",
        "1.2",
        "1.3",
        "1.4",
        "1.5",
        "1.6",
        "1.7",
        "1.8",
        "1.9",
        "2.1.1",
        "2.1.2",
        "2.5",
        "2.6",
        "2.10",
        "2.11",
        "2.12",
        "4.4.2",
        "9.1",
        "9.2",
        "14",
        "15",
    }
)

# Substantive P2 sections awaiting expert / evidence — generator returns EXPERT_REQUIRED stub only.
EXPERT_DEFERRED_SECTION_CODES: frozenset[str] = frozenset(
    {
        "2.2",
        "2.3",
        "2.4",
        "2.7",
        "2.8",
        "4.6",
        "4.9",
        "6.1.9",
        "6.1.10",
        "6.2.2",
        "6.2.3",
        "7.3.1",
        "7.3.2",
        "7.3.3",
        "7.3.4",
        "8.3",
        "8.4",
        "8.5",
        "9.4",
        "9.5",
        "9.6",
        "9.7.3",
    }
)


class SafeKnownDataContentGenerator(ProtocolContentGenerator):
    """
    For SAFE_KNOWN sections: emit a short structural note from snapshot fields only.
    For EXPERT_DEFERRED: emit EXPERT_REQUIRED placeholder block (no invented wording).
    Does not replace ProtocolDraft assembly generators — technical interface for Phase 12+.
    """

    def generate(
        self,
        section_code: str,
        canonical_snapshot: dict[str, Any],
        evidence_context: dict[str, Any] | None = None,
    ) -> ContentGenerationResult:
        evidence_context = evidence_context or {}
        if section_code in EXPERT_DEFERRED_SECTION_CODES:
            prov = expert_required_provenance(
                notes=f"Section {section_code} deferred pending medical writer / expert rules"
            )
            block = merge_provenance_into_block(
                {
                    "type": "TEXT",
                    "text": f"{{{{EXPERT.SECTION_{section_code.replace('.', '_')}}}}}",
                    "unresolved": [f"{{{{EXPERT.SECTION_{section_code.replace('.', '_')}}}}}"],
                },
                prov,
            )
            return ContentGenerationResult(
                section_code=section_code,
                blocks=[block],
                unresolved=list(block.get("unresolved") or []),
                status="NEEDS_REVIEW",
                notes=prov.notes,
            )

        # Safe structural summary from snapshot
        lines: list[str] = []
        design = canonical_snapshot.get("design_type") or canonical_snapshot.get("design")
        food = canonical_snapshot.get("food_condition") or canonical_snapshot.get("food")
        eval_n = canonical_snapshot.get("evaluable_n")
        rand_n = canonical_snapshot.get("randomized_n")
        protocol = canonical_snapshot.get("protocol_number")
        if protocol:
            lines.append(f"Protocol: {protocol}")
        if design:
            lines.append(f"Design: {design}")
        if food:
            lines.append(f"Food: {food}")
        if eval_n is not None:
            lines.append(f"Evaluable N: {eval_n}")
        if rand_n is not None:
            lines.append(f"Randomized N: {rand_n}")

        if not lines:
            prov = unresolved_provenance("{{CONTENT.SNAPSHOT}}")
            block = merge_provenance_into_block(
                {"type": "TEXT", "text": "{{CONTENT.SNAPSHOT}}", "unresolved": ["{{CONTENT.SNAPSHOT}}"]},
                prov,
            )
            return ContentGenerationResult(
                section_code=section_code,
                blocks=[block],
                unresolved=["{{CONTENT.SNAPSHOT}}"],
                status="UNRESOLVED",
            )

        text = ". ".join(str(x) for x in lines) + "."
        raw = find_raw_enums_in_text(text)
        # Snapshot may still hold codes; callers should pass display-resolved values.
        prov = ContentProvenance(
            origin="SOURCE_DERIVED",
            status="PROPOSED" if not raw else "NEEDS_REVIEW",
            source_ids=tuple(str(s) for s in (evidence_context.get("source_ids") or [])),
            notes="Safe known-data summary only — not substantive medical wording",
        )
        block = merge_provenance_into_block({"type": "TEXT", "text": text}, prov)
        return ContentGenerationResult(
            section_code=section_code,
            blocks=[block],
            source_ids=list(prov.source_ids),
            status=prov.status,
            notes=prov.notes,
        )

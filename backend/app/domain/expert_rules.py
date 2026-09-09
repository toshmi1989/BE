"""ExpertRule framework — Phase 12A.

Catalog is intentionally empty of contested medical rules.
Verification statuses: UNVERIFIED | PROPOSED | VERIFIED | REJECTED.

Architecture note (Phase 12A.1-HARDENING):
- ExpertRule = Phase 12A content-generation hook (section/entity applies_to), catalog empty.
- KnowledgeRule = Phase 12A.1 authoritative expert-knowledge layer (seeded, API, proposals).
- Do NOT delete ExpertRule in this phase; deprecation plan tracked as KnowledgeGap.
- New medical/regulatory rules must go through KnowledgeRule + ExpertDecision, not ExpertRule.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExpertRule:
    rule_id: str
    name: str
    applies_to: tuple[str, ...]  # section codes, entity types, or field paths
    expression: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    version: str = "1"
    verification_status: str = "UNVERIFIED"  # UNVERIFIED|PROPOSED|VERIFIED|REJECTED
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["applies_to"] = list(self.applies_to)
        return d

    def is_usable_for_generation(self) -> bool:
        """Only VERIFIED expert rules may drive substantive wording (future Phase)."""
        return self.verification_status == "VERIFIED"


# Framework placeholders only — no invented clinical parameters.
# Prefer KnowledgeRule for Phase 12A.1+ knowledge; keep this catalog empty.
EXPERT_RULE_CATALOG: tuple[ExpertRule, ...] = ()


def list_expert_rules(*, verification_status: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for r in EXPERT_RULE_CATALOG:
        if verification_status and r.verification_status != verification_status:
            continue
        rows.append(r.to_dict())
    return rows


def get_expert_rule(rule_id: str) -> ExpertRule | None:
    for r in EXPERT_RULE_CATALOG:
        if r.rule_id == rule_id:
            return r
    return None


def register_expert_rule_for_tests(rule: ExpertRule) -> tuple[ExpertRule, ...]:
    """Test helper — returns a new catalog tuple; does not mutate production catalog."""
    return EXPERT_RULE_CATALOG + (rule,)

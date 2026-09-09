"""Knowledge / ExpertDecision status transition guards — Phase 12A.1 hardening.

No medical logic. Enforces safe status machines and VERIFIED provenance.
"""

from __future__ import annotations

from typing import Any

# KnowledgeRule: REJECTED must not silently become VERIFIED.
KNOWLEDGE_RULE_TRANSITIONS: dict[str, frozenset[str]] = {
    "PROPOSED": frozenset({"PROPOSED", "VERIFIED", "UNVERIFIED", "REJECTED"}),
    "UNVERIFIED": frozenset({"UNVERIFIED", "PROPOSED", "REJECTED"}),
    "VERIFIED": frozenset({"VERIFIED", "PROPOSED", "REJECTED"}),
    "REJECTED": frozenset({"REJECTED", "PROPOSED"}),  # reopen only → PROPOSED
}

# ExpertDecision create must start PROPOSED; approve/reject own guards elsewhere.
EXPERT_DECISION_CREATE_STATUSES = frozenset({"PROPOSED"})


def assert_knowledge_rule_transition(current: str, new: str) -> None:
    from app.domain.exceptions import ValidationError

    allowed = KNOWLEDGE_RULE_TRANSITIONS.get(current)
    if allowed is None:
        raise ValidationError(f"Unknown current status: {current}", field="status")
    if new not in allowed:
        raise ValidationError(
            f"Illegal KnowledgeRule status transition {current} → {new}",
            field="status",
        )


def has_verified_provenance(
    *,
    regulatory_basis_id: Any = None,
    evidence_claim_ids: list | None = None,
    source_ids: list | None = None,
) -> bool:
    """VERIFIED requires regulatory basis and/or evidence claims and/or source ids."""
    if regulatory_basis_id is not None:
        return True
    if evidence_claim_ids:
        return True
    if source_ids:
        return True
    return False


def assert_verified_provenance(
    *,
    regulatory_basis_id: Any = None,
    evidence_claim_ids: list | None = None,
    source_ids: list | None = None,
) -> None:
    from app.domain.exceptions import ValidationError

    if not has_verified_provenance(
        regulatory_basis_id=regulatory_basis_id,
        evidence_claim_ids=evidence_claim_ids,
        source_ids=source_ids,
    ):
        raise ValidationError(
            "VERIFIED KnowledgeRule requires regulatory_basis_id or evidence_claim_ids or source_ids",
            field="status",
        )

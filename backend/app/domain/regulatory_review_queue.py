"""RegulatoryReviewQueue — Phase 13.1.

Approve/reject claims or rule candidates. Does NOT mutate Study.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.regulatory_source_classes import REVIEW_ITEM_STATUSES


@dataclass
class RegulatoryReviewItem:
    item_id: str
    item_type: str  # claim | conflict | rule_candidate | regulatory_basis | interpretation
    claim_id: str | None = None
    conflict_id: str | None = None
    rule_code: str | None = None
    regulatory_basis_id: str | None = None
    proposed_interpretation: str | None = None
    status: str = "PENDING"
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RegulatoryReviewQueue:
    queue_id: str
    items: list[RegulatoryReviewItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"queue_id": self.queue_id, "items": [i.to_dict() for i in self.items]}

    def pending(self) -> list[RegulatoryReviewItem]:
        return [i for i in self.items if i.status == "PENDING"]


def enqueue_claim_review(
    queue: RegulatoryReviewQueue,
    *,
    item_id: str,
    claim_id: str,
    proposed_interpretation: str | None = None,
    payload: dict | None = None,
) -> RegulatoryReviewItem:
    item = RegulatoryReviewItem(
        item_id=item_id,
        item_type="claim",
        claim_id=claim_id,
        proposed_interpretation=proposed_interpretation,
        status="PENDING",
        payload=dict(payload or {}),
    )
    queue.items.append(item)
    return item


def enqueue_rule_candidate(
    queue: RegulatoryReviewQueue,
    *,
    item_id: str,
    rule_code: str,
    claim_id: str | None = None,
    regulatory_basis_id: str | None = None,
    payload: dict | None = None,
) -> RegulatoryReviewItem:
    item = RegulatoryReviewItem(
        item_id=item_id,
        item_type="rule_candidate",
        rule_code=rule_code,
        claim_id=claim_id,
        regulatory_basis_id=regulatory_basis_id,
        status="PENDING",
        payload=dict(payload or {}),
    )
    queue.items.append(item)
    return item


def set_review_status(item: RegulatoryReviewItem, status: str) -> RegulatoryReviewItem:
    if status not in REVIEW_ITEM_STATUSES:
        raise ValueError(f"Invalid review status: {status}")
    item.status = status
    return item


def approve_review_item(item: RegulatoryReviewItem) -> dict[str, Any]:
    """Approve review item. Returns action result — does NOT mutate Study."""
    set_review_status(item, "APPROVED")
    return {
        "item_id": item.item_id,
        "status": "APPROVED",
        "study_mutated": False,
        "canonical_mutated": False,
        "message": "Approved for knowledge/evidence layer only — Study unchanged",
    }


def reject_review_item(item: RegulatoryReviewItem) -> dict[str, Any]:
    set_review_status(item, "REJECTED")
    return {
        "item_id": item.item_id,
        "status": "REJECTED",
        "study_mutated": False,
        "canonical_mutated": False,
    }

"""Decision 85 verification pipeline orchestration — Phase 13.3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.decision85_claims import (
    FIRST_BATCH_KEYS,
    build_decision85_claims,
    import_decision85_source,
    interview_conflicts_for_decision85,
    knowledge_gaps_decision85,
    rule_candidates_from_verified,
)
from app.domain.regulatory_coverage import build_regulatory_coverage_report
from app.domain.regulatory_review_queue import RegulatoryReviewQueue, enqueue_claim_review
from app.domain.regulatory_source_slots import refresh_slots
from app.domain.regulatory_verify import verify_claim_explicit


def run_decision85_verification_pipeline(
    *,
    root: Path | None = None,
    project_id: str | None = None,
    verify_first_batch: bool = False,
    reviewer: str | None = None,
    canonical_study: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Import Decision 85 → claims → conflicts → optional explicit first-batch verify.

    Never mutates Study. Rule candidates stay PROPOSED.
    """
    study_before = dict(canonical_study) if canonical_study else None
    imported = import_decision85_source(root=root, project_id=project_id)
    if imported.get("status") == "MISSING":
        return {
            **imported,
            "verified_claims": [],
            "proposed_claims": [],
            "conflicts": [],
            "rule_candidates": [],
            "coverage": {},
            "study_mutated": False,
            "rules_auto_verified": 0,
        }

    claims = list(imported.get("claim_objects") or [])
    if not claims and imported.get("source_version"):
        claims = build_decision85_claims(
            source_version_id=str(imported["source_version"]["version_id"]),
            root=root,
        )

    queue = RegulatoryReviewQueue(queue_id="decision85-review")
    for c in claims:
        enqueue_claim_review(queue, item_id=f"REV-{c.claim_id}", claim_id=c.claim_id, payload=c.to_dict())

    verified = []
    if verify_first_batch:
        if not reviewer:
            raise ValueError("reviewer required to verify first batch")
        for c in claims:
            key = c.claim_id.replace("D85-", "").rsplit("-P", 1)[0]
            if key in FIRST_BATCH_KEYS or (c.notes and "first_batch=true" in c.notes):
                verified.append(verify_claim_explicit(c, reviewer=reviewer))
            else:
                verified.append(c)
        claims = verified

    conflicts = interview_conflicts_for_decision85(claims)
    gaps = knowledge_gaps_decision85(imported)
    candidates = rule_candidates_from_verified(claims)

    claim_dicts = [c.to_dict() for c in claims]
    coverage = build_regulatory_coverage_report(
        report_id="COV-D85",
        package_status="PARTIAL",
        sources=[
            {
                "source_id": "SRC-DECISION85",
                "ingestion_status": "OK",
                "source_class": "EEC_REGULATORY",
                "title": "Decision 85",
                "domains": ["REFERENCE", "DESIGN", "FOOD", "SAMPLING", "WASHOUT", "ANALYTE", "PK", "STATISTICS"],
            }
        ],
        claims=claim_dicts,
        conflicts=[c.to_dict() for c in conflicts],
        review_items=queue.to_dict()["items"],
        knowledge_gaps=gaps,
        knowledge_rules=[{"rule_code": r.get("rule_code"), "status": r.get("status")} for r in candidates],
    )

    study_after = dict(canonical_study) if canonical_study else None
    study_mutated = study_before != study_after if study_before is not None else False

    return {
        "status": imported.get("status"),
        "source_version": imported.get("source_version"),
        "amendments": imported.get("amendments"),
        "amendment_metadata_certainty": imported.get("amendment_metadata_certainty"),
        "page_provenance": imported.get("page_provenance"),
        "claims": claim_dicts,
        "verified_claims": [c.to_dict() for c in claims if c.verification_status == "VERIFIED"],
        "proposed_claims": [
            c.to_dict()
            for c in claims
            if c.verification_status in {"UNVERIFIED", "EXTRACTED", "REVIEW_REQUIRED"}
        ],
        "rejected_claims": [c.to_dict() for c in claims if c.verification_status == "REJECTED"],
        "conflicts": [c.to_dict() for c in conflicts],
        "knowledge_gaps": gaps,
        "rule_candidates": candidates,
        "review_queue": queue.to_dict(),
        "slots": [s.to_dict() for s in refresh_slots(base=root, project_id=project_id)],
        "coverage": coverage.to_dict(),
        "study_mutated": study_mutated,
        "rules_auto_verified": 0,
        "auto_verified": False,
        "first_batch_keys": list(FIRST_BATCH_KEYS),
    }

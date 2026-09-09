"""Evidence usability for decisions — Phase 15.2.

Separate from verification and applicability.
"""

from __future__ import annotations

from app.domain.research_evidence_models import ResearchClaim


def compute_usability(claim: ResearchClaim, *, decision_domain: str | None = None) -> str:
    """Deterministic usability. LOW/NOT_APPLICABLE cannot unblock critical decisions."""
    if claim.verification_status == "REJECTED":
        return "NOT_USABLE_FOR_DECISION"
    if claim.applicability == "NOT_APPLICABLE":
        return "NOT_USABLE_FOR_DECISION"
    if claim.applicability == "LOW":
        return "NOT_USABLE_FOR_DECISION"
    if claim.verification_status != "VERIFIED":
        return "REQUIRES_REVIEW"
    if claim.applicability == "UNKNOWN":
        return "REQUIRES_REVIEW"
    if decision_domain and claim.decision_domains and decision_domain not in claim.decision_domains:
        return "NOT_USABLE_FOR_DECISION"
    if claim.applicability in {"DIRECT", "HIGH", "MODERATE"} and claim.verification_status == "VERIFIED":
        return "USABLE_FOR_DECISION"
    return "REQUIRES_REVIEW"


def apply_usability(claim: ResearchClaim, *, decision_domain: str | None = None) -> ResearchClaim:
    claim.usability = compute_usability(claim, decision_domain=decision_domain)
    if claim.measurement:
        claim.measurement = {**claim.measurement, "usability": claim.usability}
    if claim.cvintra:
        claim.cvintra = {**claim.cvintra, "usability": claim.usability}
    return claim


def can_unblock_decision(claim: ResearchClaim, *, domain: str) -> bool:
    """LOW applicability evidence cannot silently unblock a critical decision."""
    if claim.usability != "USABLE_FOR_DECISION":
        return False
    if claim.applicability in {"LOW", "NOT_APPLICABLE", "UNKNOWN"}:
        return False
    if claim.verification_status != "VERIFIED":
        return False
    if claim.decision_domains and domain not in claim.decision_domains:
        return False
    return True

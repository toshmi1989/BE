"""Regulatory evidence claims & provenance — Phase 13.1.

Does not auto-verify. Does not mutate Study / Design / Sampling / PK / Safety.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.regulatory_source_classes import (
    CLAIM_KINDS,
    CONFIDENCE_LEVELS,
    SOURCE_VERIFICATION_STATUSES,
    is_interview_class,
)


@dataclass
class EvidenceProvenance:
    source_id: str
    document_id: str | None = None
    source_version: str = "1"
    page: int | str | None = None
    section: str | None = None
    paragraph_or_chunk: str | None = None
    quoted_text: str | None = None
    extraction_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_complete_for_regulatory(self) -> bool:
        """Regulatory claims require source + some location + exact text."""
        return bool(self.source_id and self.quoted_text and (self.page is not None or self.section or self.paragraph_or_chunk))


@dataclass
class RegulatoryEvidenceClaim:
    claim_id: str
    claim_kind: str
    domain: str
    field_name: str | None
    raw_extract: str | None
    normalized_claim: str | None
    confidence: str = "LOW"
    verification_status: str = "UNVERIFIED"
    provenance: EvidenceProvenance | None = None
    source_class: str | None = None
    related_rule_codes: list[str] = field(default_factory=list)
    related_study_fields: list[str] = field(default_factory=list)
    regulatory_basis_id: str | None = None
    source_version_id: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def is_interview_claim(self) -> bool:
        return self.claim_kind == "EXPERT_INTERVIEW_CLAIM" or is_interview_class(str(self.source_class or ""))

    def is_regulatory_claim(self) -> bool:
        return self.claim_kind == "REGULATORY_CLAIM" and not self.is_interview_claim()


def build_claim(
    *,
    claim_id: str,
    claim_kind: str,
    domain: str,
    field_name: str | None = None,
    raw_extract: str | None = None,
    normalized_claim: str | None = None,
    confidence: str = "LOW",
    verification_status: str = "UNVERIFIED",
    provenance: EvidenceProvenance | None = None,
    source_class: str | None = None,
    related_rule_codes: list[str] | None = None,
    related_study_fields: list[str] | None = None,
    source_version_id: str | None = None,
    allow_verified: bool = False,
) -> RegulatoryEvidenceClaim:
    if claim_kind not in CLAIM_KINDS:
        raise ValueError(f"Invalid claim_kind: {claim_kind}")
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "LOW"
    if verification_status not in SOURCE_VERIFICATION_STATUSES:
        verification_status = "UNVERIFIED"
    # HARD RULE: never auto-verify unless allow_verified=True (explicit review workflow only)
    if verification_status == "VERIFIED" and not allow_verified:
        raise ValueError("VERIFIED requires allow_verified=True from explicit review workflow")
    sv_id = source_version_id or (provenance.document_id if provenance else None)
    return RegulatoryEvidenceClaim(
        claim_id=claim_id,
        claim_kind=claim_kind,
        domain=domain,
        field_name=field_name,
        raw_extract=raw_extract,
        normalized_claim=normalized_claim,
        confidence=confidence,
        verification_status=verification_status,
        provenance=provenance,
        source_class=source_class,
        related_rule_codes=list(related_rule_codes or []),
        related_study_fields=list(related_study_fields or []),
        source_version_id=sv_id,
    )


def explicitly_verify_claim(claim: RegulatoryEvidenceClaim, *, reviewer: str) -> RegulatoryEvidenceClaim:
    """Explicit verification only. Does not mutate Study."""
    if claim.is_regulatory_claim():
        if claim.provenance is None or not claim.provenance.is_complete_for_regulatory():
            raise ValueError("Regulatory claim requires complete page/section/text provenance to verify")
    claim.verification_status = "VERIFIED"
    claim.notes = (claim.notes or "") + f" | verified_by={reviewer}"
    return claim


def confidence_does_not_imply_verification(confidence: str, verification_status: str) -> bool:
    """Invariant helper for tests."""
    if confidence == "HIGH" and verification_status != "VERIFIED":
        return True
    return verification_status != "VERIFIED" or confidence in CONFIDENCE_LEVELS


@dataclass
class ProposedRegulatoryBasis:
    basis_id: str
    source_id: str
    document_identifier: str | None
    section: str | None
    page: int | str | None
    paragraph: str | None
    claim_id: str | None
    status: str = "UNVERIFIED"  # UNVERIFIED | PROPOSED | VERIFIED

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def link_claim_to_basis(claim: RegulatoryEvidenceClaim, basis: ProposedRegulatoryBasis) -> RegulatoryEvidenceClaim:
    claim.regulatory_basis_id = basis.basis_id
    if claim.verification_status == "UNVERIFIED" and basis.status != "VERIFIED":
        claim.verification_status = "REVIEW_REQUIRED"
    return claim


def detect_stale_evidence(
    *,
    claim: RegulatoryEvidenceClaim,
    current_source_version: str,
) -> dict[str, Any] | None:
    if not claim.provenance:
        return {
            "code": "EVIDENCE.STALE_OR_MISSING_PROVENANCE",
            "claim_id": claim.claim_id,
            "message": "Missing provenance",
        }
    if str(claim.provenance.source_version) != str(current_source_version):
        return {
            "code": "EVIDENCE.STALE_SOURCE_VERSION",
            "claim_id": claim.claim_id,
            "claim_version": claim.provenance.source_version,
            "current_version": current_source_version,
        }
    return None

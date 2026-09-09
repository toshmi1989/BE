"""Claim verification guards & import→claim pipeline — Phase 13.2.

VERIFIED only via explicit human review with complete provenance.
Never mutates Study. Rule candidates stay PROPOSED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.domain.regulatory_claims import (
    EvidenceProvenance,
    ProposedRegulatoryBasis,
    RegulatoryEvidenceClaim,
    build_claim,
    link_claim_to_basis,
)
from app.domain.regulatory_review_queue import (
    RegulatoryReviewQueue,
    enqueue_claim_review,
    enqueue_rule_candidate,
)
from app.domain.regulatory_source_classes import is_interview_class
from app.domain.regulatory_source_version import ImportResult, SourceVersion


class VerifyGuardError(Exception):
    """Raised when VERIFIED is requested without required fields — map to HTTP 422."""

    def __init__(self, message: str, *, field: str | None = None, code: str = "VERIFY_GUARD"):
        super().__init__(message)
        self.field = field
        self.code = code


@dataclass
class ReviewAuditEntry:
    claim_id: str
    action: str  # start_review|approve|reject|verify
    reviewer: str
    timestamp: str
    notes: str | None = None
    previous_status: str | None = None
    new_status: str | None = None
    study_mutated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_AUDIT: list[ReviewAuditEntry] = []


def review_audit_trail() -> list[dict[str, Any]]:
    return [e.to_dict() for e in _AUDIT]


def clear_review_audit() -> None:
    _AUDIT.clear()


def validate_verify_payload(claim: RegulatoryEvidenceClaim | dict, *, reviewer: str | None) -> None:
    """Server-side guard: reject incomplete VERIFIED transitions."""
    if isinstance(claim, dict):
        kind = str(claim.get("claim_kind") or "")
        source_class = claim.get("source_class")
        prov = claim.get("provenance") or {}
        normalized = claim.get("normalized_claim")
        excerpt = (prov.get("quoted_text") if isinstance(prov, dict) else None) or claim.get("raw_extract")
        source_id = (prov.get("source_id") if isinstance(prov, dict) else None) or claim.get("source_id")
        page = prov.get("page") if isinstance(prov, dict) else None
        source_version = prov.get("source_version") if isinstance(prov, dict) else None
        version_id = claim.get("source_version_id") or (
            prov.get("document_id") if isinstance(prov, dict) else None
        )
    else:
        kind = claim.claim_kind
        source_class = claim.source_class
        prov = claim.provenance
        normalized = claim.normalized_claim
        excerpt = (prov.quoted_text if prov else None) or claim.raw_extract
        source_id = prov.source_id if prov else None
        page = prov.page if prov else None
        source_version = prov.source_version if prov else None
        version_id = claim.source_version_id or (prov.document_id if prov else None)

    if not reviewer or not str(reviewer).strip():
        raise VerifyGuardError("reviewer required for verification", field="reviewer")
    if is_interview_class(str(source_class or "")) or kind == "EXPERT_INTERVIEW_CLAIM":
        raise VerifyGuardError(
            "EXPERT_INTERVIEW claims cannot become regulatory VERIFIED",
            field="source_class",
            code="INTERVIEW_NOT_REGULATORY",
        )
    if not source_id:
        raise VerifyGuardError("source missing", field="source_id")
    if not version_id and not source_version:
        raise VerifyGuardError("source version missing", field="source_version_id")
    # Page required for REGULATORY_CLAIM and for RAW_EXTRACT from page-based imports when verifying as regulatory evidence
    if page is None and kind in {"REGULATORY_CLAIM", "RAW_EXTRACT", "NORMALIZED_CLAIM"}:
        # Web-archive / Decision 85: page may be UNAVAILABLE if section + chunk + excerpt exist
        if isinstance(claim, dict):
            prov_d = claim.get("provenance") or {}
            section = prov_d.get("section") if isinstance(prov_d, dict) else None
            chunk = prov_d.get("paragraph_or_chunk") if isinstance(prov_d, dict) else None
        else:
            section = prov.section if prov else None
            chunk = prov.paragraph_or_chunk if prov else None
        if not (section and chunk and excerpt):
            raise VerifyGuardError("page missing for page-based source", field="page")
    if not excerpt or not str(excerpt).strip():
        raise VerifyGuardError("exact excerpt missing", field="exact_excerpt")
    if not normalized or not str(normalized).strip():
        raise VerifyGuardError("normalized claim missing", field="normalized_claim")


def verify_claim_explicit(
    claim: RegulatoryEvidenceClaim,
    *,
    reviewer: str,
    review_timestamp: str | None = None,
    notes: str | None = None,
) -> RegulatoryEvidenceClaim:
    """Explicit human verification. Does not mutate Study. Does not verify KnowledgeRules."""
    validate_verify_payload(claim, reviewer=reviewer)
    ts = review_timestamp or datetime.now(timezone.utc).isoformat()
    prev = claim.verification_status
    claim.verification_status = "VERIFIED"
    claim.reviewed_by = reviewer
    claim.reviewed_at = ts
    claim.notes = (claim.notes or "") + f" | verified_by={reviewer} at={ts}"
    if notes:
        claim.notes += f" | {notes}"
    _AUDIT.append(
        ReviewAuditEntry(
            claim_id=claim.claim_id,
            action="verify",
            reviewer=reviewer,
            timestamp=ts,
            notes=notes,
            previous_status=prev,
            new_status="VERIFIED",
            study_mutated=False,
        )
    )
    return claim


def reject_claim_explicit(
    claim: RegulatoryEvidenceClaim,
    *,
    reviewer: str,
    notes: str | None = None,
) -> RegulatoryEvidenceClaim:
    if not reviewer:
        raise VerifyGuardError("reviewer required", field="reviewer")
    prev = claim.verification_status
    claim.verification_status = "REJECTED"
    ts = datetime.now(timezone.utc).isoformat()
    claim.notes = (claim.notes or "") + f" | rejected_by={reviewer} at={ts}"
    _AUDIT.append(
        ReviewAuditEntry(
            claim_id=claim.claim_id,
            action="reject",
            reviewer=reviewer,
            timestamp=ts,
            notes=notes,
            previous_status=prev,
            new_status="REJECTED",
            study_mutated=False,
        )
    )
    return claim


def create_rule_candidate_from_claim(
    claim: RegulatoryEvidenceClaim,
    *,
    rule_code: str,
) -> dict[str, Any]:
    """Verified claim MAY spawn KnowledgeRule candidate — always PROPOSED."""
    return {
        "rule_code": rule_code,
        "status": "PROPOSED",
        "requires_expert_confirmation": True,
        "source_claim_id": claim.claim_id,
        "claim_verification_status": claim.verification_status,
        "study_mutated": False,
        "message": "Rule candidate PROPOSED — not VERIFIED; Study unchanged",
    }


def claims_from_import(
    result: ImportResult,
    *,
    domain: str = "REPORTING",
    field_name: str | None = None,
    normalized_claim: str | None = None,
    max_excerpt: int = 800,
) -> list[RegulatoryEvidenceClaim]:
    """Build RAW_EXTRACT / optional NORMALIZED claims from import pages. Status EXTRACTED/REVIEW_REQUIRED."""
    if not result.source_version:
        return []
    sv = result.source_version
    claims: list[RegulatoryEvidenceClaim] = []
    if sv.technical_fixture:
        # Technical fixture: RAW_EXTRACT only — never REGULATORY_CLAIM auto
        kind = "RAW_EXTRACT"
        source_class = "OTHER"
    else:
        kind = "RAW_EXTRACT"
        source_class = sv.source_class

    for page in result.pages[:5]:
        text = str(page.get("text") or "").strip()
        if not text:
            continue
        excerpt = text[:max_excerpt]
        page_no = page.get("page_number")
        claim_id = f"CLM-{sv.version_id}-P{page_no}"
        status = "REVIEW_REQUIRED" if sv.extraction_quality in {"POOR", "FAILED", "FAIR"} else "EXTRACTED"
        # Always provide a focused normalized form for review (not a medical assertion)
        norm = normalized_claim if page_no == 1 and normalized_claim else f"Technical extract page {page_no}"
        claims.append(
            build_claim(
                claim_id=claim_id,
                claim_kind=kind,
                domain=domain,
                field_name=field_name,
                raw_extract=excerpt,
                normalized_claim=norm,
                confidence="LOW" if sv.extraction_quality != "GOOD" else "MEDIUM",
                verification_status=status,
                source_class=source_class,
                source_version_id=sv.version_id,
                provenance=EvidenceProvenance(
                    source_id=sv.source_id,
                    document_id=sv.version_id,
                    source_version=sv.version_id,
                    page=page_no,  # human-facing 1-based
                    paragraph_or_chunk=f"page-{page_no}",
                    quoted_text=excerpt,
                    extraction_method=sv.extraction_version,
                ),
            )
        )
    for c in claims:
        if sv.technical_fixture:
            c.notes = (c.notes or "") + " | TECHNICAL_FIXTURE_ONLY"
    return claims


def basis_from_source_version(
    sv: SourceVersion,
    *,
    claim_id: str | None = None,
    section: str | None = None,
    page: int | str | None = None,
) -> ProposedRegulatoryBasis:
    return ProposedRegulatoryBasis(
        basis_id=f"RB-{sv.version_id}",
        source_id=sv.source_id,
        document_identifier=sv.document_identifier,
        section=section,
        page=page,
        paragraph=None,
        claim_id=claim_id,
        status="UNVERIFIED",
    )


def enqueue_import_for_review(
    queue: RegulatoryReviewQueue,
    claims: list[RegulatoryEvidenceClaim],
) -> None:
    for c in claims:
        enqueue_claim_review(
            queue,
            item_id=f"REV-{c.claim_id}",
            claim_id=c.claim_id,
            payload=c.to_dict(),
        )

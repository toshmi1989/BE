"""Helpers to build synthetic verified CVintra claims for Phase 15.4 tests."""

from __future__ import annotations

from app.domain.research_evidence_models import ResearchClaim
from app.domain.research_usability import apply_usability


def make_verified_cvintra_claim(
    *,
    study_id: str,
    cv_value: float,
    pk_parameter: str = "Cmax",
    applicability: str = "HIGH",
    variability_type: str = "WITHIN_SUBJECT",
    verification_status: str = "VERIFIED",
    source_result_id: str = "synth-src-1",
    claim_text: str | None = None,
) -> ResearchClaim:
    """Synthetic verified evidence — not fabricated literature attribution."""
    c = ResearchClaim(
        claim_text=claim_text or f"Synthetic CVintra {pk_parameter}={cv_value}%",
        excerpt=f"CV={cv_value}% ({pk_parameter})",
        source_result_id=source_result_id,
        field_path="cv_intra",
        value=cv_value,
        unit="%",
        study_id=study_id,
        verification_status=verification_status,
        applicability=applicability,
        cvintra={
            "CV_value": cv_value,
            "CV_unit": "%",
            "PK_parameter": pk_parameter,
            "variability_type": variability_type,
            "verification_status": verification_status,
            "applicability": applicability,
        },
        decision_domains=["STATISTICS", "SAMPLE_SIZE"],
    )
    apply_usability(c, decision_domain="STATISTICS")
    return c

"""Phase 30 — applicability must not silently transfer across formulations."""

from __future__ import annotations

from app.domain.research_evidence_engine import verify_claim
from app.domain.research_evidence_models import ResearchClaim
from app.domain.research_evidence_store import clear_research_evidence_store, put_claim
from app.domain.research_usability import apply_usability, can_unblock_decision


def setup_function():
    clear_research_evidence_store()


def test_ir_tmax_not_auto_applicable_to_pr_without_review():
    """Immediate-release Tmax must not silently unblock prolonged-release decisions."""
    c = ResearchClaim(
        claim_text="Tmax IR 1 h",
        field_path="pk.expected_tmax",
        value="1",
        unit="ч",
        excerpt="Immediate-release tablet Tmax approximately 1 h",
        location="lit:1",
        source_id="LIT-IR",
        extraction_method="AI",
        confidence="HIGH",
        applicability="UNKNOWN",
        study_id="UPDCB-02-BE-2026",
        measurement={
            "parameter": "Tmax",
            "dosage_form": "immediate-release",
            "parameter_context": "IR formulation",
        },
    )
    apply_usability(c)
    put_claim(c)
    assert c.verification_status == "PROPOSED"
    assert can_unblock_decision(c, domain="DESIGN") is False

    # Even after verify, LOW / NOT_APPLICABLE must not unblock
    verified = verify_claim(
        c.id,
        reviewer="expert",
        applicability="NOT_APPLICABLE",
        applicability_reason="IR Tmax not applicable to prolonged-release 15 mg",
    )
    assert verified.applicability == "NOT_APPLICABLE"
    assert can_unblock_decision(verified, domain="DESIGN") is False


def test_direct_applicability_after_expert_review():
    c = ResearchClaim(
        claim_text="Tmax PR 2-4 h",
        field_path="pk.expected_tmax",
        value="2-4",
        unit="ч",
        excerpt="Prolonged-release upadacitinib Tmax 2-4 h",
        location="smpc:pk",
        source_id="SMPC",
        extraction_method="DETERMINISTIC",
        study_id="UPDCB-02-BE-2026",
    )
    apply_usability(c)
    put_claim(c)
    v = verify_claim(
        c.id,
        reviewer="expert",
        applicability="DIRECT",
        applicability_reason="Same substance, prolonged-release, matching strength context",
    )
    assert v.applicability == "DIRECT"
    assert can_unblock_decision(v, domain="DESIGN") is True

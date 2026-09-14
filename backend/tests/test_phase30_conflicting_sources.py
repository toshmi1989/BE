"""Phase 30 — conflicting sources must not auto-resolve."""

from __future__ import annotations

from app.domain.research_conflicts import assert_no_average, detect_numeric_conflicts
from app.domain.research_evidence_models import ResearchClaim
from app.domain.research_evidence_store import clear_research_evidence_store, put_claim, put_conflict
from app.domain.research_usability import apply_usability


def setup_function():
    clear_research_evidence_store()


def test_conflicting_tmax_creates_open_conflict():
    a = ResearchClaim(
        claim_text="Tmax 2 h",
        field_path="pk.expected_tmax",
        value=2.0,
        unit="ч",
        excerpt="Tmax 2 h",
        location="a",
        source_id="A",
        study_id="S1",
    )
    b = ResearchClaim(
        claim_text="Tmax 4 h",
        field_path="pk.expected_tmax",
        value=4.0,
        unit="ч",
        excerpt="Tmax 4 h",
        location="b",
        source_id="B",
        study_id="S1",
    )
    apply_usability(a)
    apply_usability(b)
    put_claim(a)
    put_claim(b)
    conflicts = detect_numeric_conflicts([a, b], field_path="pk.expected_tmax", study_id="S1")
    assert conflicts
    assert conflicts[0].status == "OPEN"
    put_conflict(conflicts[0])
    assert_no_average(conflicts[0])
    # Both remain PROPOSED — no silent pick
    assert a.verification_status == "PROPOSED"
    assert b.verification_status == "PROPOSED"


def test_false_positive_wrong_product_stays_proposed():
    wrong = ResearchClaim(
        claim_text="Bosutinib Tmax",
        field_path="pk.expected_tmax",
        value="4-6",
        excerpt="Bosutinib Tmax 4-6 h",
        location="wrong",
        source_id="BOSU",
        extraction_method="AI",
        confidence="HIGH",
        study_id="UPDCB-02-BE-2026",
    )
    apply_usability(wrong)
    put_claim(wrong)
    assert wrong.verification_status == "PROPOSED"
    assert wrong.verification_status != "VERIFIED"

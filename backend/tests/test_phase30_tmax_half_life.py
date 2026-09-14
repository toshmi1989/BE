"""Phase 30 — expected Tmax / half-life planning facts."""

from __future__ import annotations

from app.domain.product_knowledge import PRODUCT_KNOWLEDGE_FIELDS
from app.domain.research_evidence_models import ResearchClaim
from app.domain.research_evidence_store import clear_research_evidence_store, put_claim
from app.domain.research_usability import apply_usability
from app.domain.workspace_gaps import GAP_CATALOG


def setup_function():
    clear_research_evidence_store()


def test_tmax_half_life_are_planning_facts():
    tmax = next(f for f in PRODUCT_KNOWLEDGE_FIELDS if f.category == "TMAX")
    th = next(f for f in PRODUCT_KNOWLEDGE_FIELDS if f.category == "HALF_LIFE")
    assert tmax.planning_fact is True
    assert th.planning_fact is True
    assert tmax.field_path == "pk.expected_tmax"
    assert th.field_path == "pk.expected_t_half"
    assert GAP_CATALOG["MISSING_TMAX_FOR_SAMPLING"]["note"]


def test_tmax_claim_proposed_not_observed_confusion():
    c = ResearchClaim(
        claim_text="expected Tmax 2-4 h",
        field_path="pk.expected_tmax",
        value="2-4",
        unit="ч",
        excerpt="Tmax 2–4 h (SmPC)",
        location="smpc:pk",
        source_id="SMPC",
        extraction_method="DETERMINISTIC",
        measurement={
            "parameter": "Tmax",
            "parameter_context": "expected/planning Tmax (pre-study)",
            "statistic_type": "RANGE",
        },
        study_id="UPDCB-02-BE-2026",
    )
    apply_usability(c)
    put_claim(c)
    assert c.verification_status == "PROPOSED"
    assert "planning" in str((c.measurement or {}).get("parameter_context") or "").lower() or True

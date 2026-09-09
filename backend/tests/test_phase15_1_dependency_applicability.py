"""Phase 15.1 — Decision dependency & evidence applicability hardening.

≥80 meaningful tests. No Phase 16. No Sample Size/Statistics engines.
No automatic medical decisions. No Study mutation from recommendations.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.decision_applicability import (
    EvidenceApplicability,
    apply_ai_applicability_proposal,
    assess_analogue_applicability,
    assess_regulatory_applicability,
    classify_decision_input_source,
    stale_on_source_version_change,
)
from app.domain.decision_context import build_context_from_package
from app.domain.decision_dependency import (
    DECISION_DEPENDENCY_REGISTRY,
    dependencies_for_domain,
    domains_affected_by_field,
    is_decision_blocked,
    registry_for,
)
from app.domain.decision_engine import (
    ai_cannot_approve,
    ai_cannot_finalize_applicability,
    invalidate_on_upstream_change,
    keep_current_value,
    recompute_decisions,
    recompute_from_package,
)
from app.domain.decision_matrix import evidence, make_recommendation
from app.domain.decision_models import ProtocolDecision
from app.domain.decision_store import clear_decision_store, put_context, put_decisions
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.study_input_pipeline import load_real_fixture_package
from app.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture
def golden():
    clear_decision_store()
    pkg = load_real_fixture_package(prefer_text_dump=False)
    ctx, decisions = recompute_from_package(pkg, study_id="UPDCB-02-BE-2026")
    return pkg, ctx, decisions


def _by(decisions):
    return {d.domain: d for d in decisions}


# ---------------------------------------------------------------------------
# A. Dependency registry
# ---------------------------------------------------------------------------


def test_a01_registry_has_core_and_statistics_domains():
    assert {
        "DESIGN",
        "FOOD",
        "WASHOUT",
        "SAMPLING",
        "ANALYTE_PK",
        "STATISTICS",
    }.issubset(set(DECISION_DEPENDENCY_REGISTRY))
    # Sample size remains a separate engine (Phase 15.4), not a ProtocolDecision domain
    assert "SAMPLE_SIZE" not in DECISION_DEPENDENCY_REGISTRY


def test_a02_design_blocks_on_dose():
    assert "reference_product.dose" in registry_for("DESIGN")["blocking_conflict_fields"]


def test_a03_food_does_not_block_on_dose():
    assert "reference_product.dose" not in registry_for("FOOD")["blocking_conflict_fields"]


def test_a04_washout_does_not_block_on_dose():
    assert "reference_product.dose" not in registry_for("WASHOUT")["blocking_conflict_fields"]


def test_a05_sampling_does_not_block_on_dose():
    assert "reference_product.dose" not in registry_for("SAMPLING")["blocking_conflict_fields"]


def test_a06_washout_blocks_on_half_life_gap():
    assert "MISSING_HALF_LIFE_FOR_WASHOUT" in registry_for("WASHOUT")["blocking_gap_codes"]


def test_a07_sampling_blocks_on_tmax():
    assert "MISSING_TMAX_FOR_SAMPLING" in registry_for("SAMPLING")["blocking_gap_codes"]


def test_a08_sampling_registers_half_life():
    assert "MISSING_HALF_LIFE_FOR_WASHOUT" in registry_for("SAMPLING")["blocking_gap_codes"]


def test_a09_cvintra_non_blocking_for_design():
    assert "MISSING_CVINTRA" in registry_for("DESIGN")["non_blocking_gap_codes"]


def test_a10_meal_non_blocking_for_food():
    assert "MISSING_MEAL_COMPOSITION" in registry_for("FOOD")["non_blocking_gap_codes"]


def test_a11_analyte_dose_non_blocking():
    assert "reference_product.dose" in registry_for("ANALYTE_PK").get(
        "non_blocking_conflict_fields", ()
    )


def test_a12_dependencies_for_domain_shape():
    d = dependencies_for_domain("DESIGN")
    assert d["domain"] == "DESIGN"
    assert "blocking_conflict_fields" in d
    assert "context_fields" in d


def test_a13_unknown_domain_raises():
    with pytest.raises(KeyError):
        registry_for("SAMPLE_SIZE")


# ---------------------------------------------------------------------------
# B. Dependency resolution / change impact
# ---------------------------------------------------------------------------


def test_b01_t_half_affects_washout_sampling():
    assert domains_affected_by_field("t_half") == ["WASHOUT", "SAMPLING"]


def test_b02_tmax_affects_sampling_only():
    assert domains_affected_by_field("tmax") == ["SAMPLING"]


def test_b03_dose_affects_design_only():
    assert domains_affected_by_field("reference_product.dose") == ["DESIGN"]


def test_b04_food_condition_affects_food():
    assert "FOOD" in domains_affected_by_field("food.condition")


def test_b05_analyte_affects_analyte_pk():
    assert "ANALYTE_PK" in domains_affected_by_field("bioanalysis.analyte")


def test_b06_t_half_does_not_affect_food():
    assert "FOOD" not in domains_affected_by_field("pk.t_half")


def test_b07_dose_does_not_affect_washout():
    assert "WASHOUT" not in domains_affected_by_field("reference_product.dose")


# ---------------------------------------------------------------------------
# C. Decision blocking
# ---------------------------------------------------------------------------


def test_c01_design_blocked_by_dose(golden):
    report = is_decision_blocked("DESIGN", golden[1])
    assert report.blocked is True
    assert any("DOSE" in b.blocking_reason_code for b in report.blocking_reasons)


def test_c02_food_not_blocked_by_dose(golden):
    report = is_decision_blocked("FOOD", golden[1])
    assert report.blocked is False


def test_c03_washout_blocked_by_half_life(golden):
    report = is_decision_blocked("WASHOUT", golden[1])
    assert report.blocked is True
    assert any(b.blocking_reason_code == "MISSING_HALF_LIFE_FOR_WASHOUT" for b in report.blocking_reasons)


def test_c04_washout_not_blocked_by_dose(golden):
    report = is_decision_blocked("WASHOUT", golden[1])
    assert not any(
        b.field_path == "reference_product.dose" and b.kind == "CONFLICT" and not str(b.blocking_reason_code).startswith("UNRELATED")
        for b in report.blocking_reasons
    )


def test_c05_sampling_blocked_by_tmax(golden):
    report = is_decision_blocked("SAMPLING", golden[1])
    assert report.blocked is True
    assert any(b.blocking_reason_code == "MISSING_TMAX_FOR_SAMPLING" for b in report.blocking_reasons)


def test_c06_sampling_blocked_by_half_life(golden):
    report = is_decision_blocked("SAMPLING", golden[1])
    assert any(b.blocking_reason_code == "MISSING_HALF_LIFE_FOR_WASHOUT" for b in report.blocking_reasons)


def test_c07_analyte_not_blocked_by_dose(golden):
    report = is_decision_blocked("ANALYTE_PK", golden[1])
    assert report.blocked is False


def test_c08_engine_statuses_match_graph(golden):
    by = _by(golden[2])
    assert by["DESIGN"].status == "BLOCKED"
    assert by["FOOD"].status == "REVIEW_REQUIRED"
    assert by["WASHOUT"].status == "BLOCKED"
    assert by["SAMPLING"].status == "BLOCKED"
    assert by["ANALYTE_PK"].status == "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# D. Non-blocking issues
# ---------------------------------------------------------------------------


def test_d01_design_cvintra_non_blocking(golden):
    report = is_decision_blocked("DESIGN", golden[1])
    assert any(b.blocking_reason_code == "MISSING_CVINTRA" for b in report.non_blocking_issues)


def test_d02_food_meal_non_blocking(golden):
    report = is_decision_blocked("FOOD", golden[1])
    assert any(b.blocking_reason_code == "MISSING_MEAL_COMPOSITION" for b in report.non_blocking_issues)


def test_d03_washout_lists_unrelated_dose(golden):
    report = is_decision_blocked("WASHOUT", golden[1])
    assert any(
        b.field_path == "reference_product.dose" for b in report.non_blocking_issues
    )


def test_d04_food_card_does_not_list_dose_as_blocker(golden):
    food = _by(golden[2])["FOOD"]
    blocker_fps = [b.get("field_path") for b in food.blocking_reasons]
    assert "reference_product.dose" not in blocker_fps


def test_d05_ui_separates_blocking_vs_non(golden):
    design = _by(golden[2])["DESIGN"].to_dict(for_ui=True)
    assert "blocking_why" in design["display"]
    assert "non_blocking_why" in design["display"]


# ---------------------------------------------------------------------------
# E. Current fact classification
# ---------------------------------------------------------------------------


def test_e01_structured_fact_is_current_study_fact():
    assert classify_decision_input_source(evidence_type="STRUCTURED_STUDY_FACT") == "CURRENT_STUDY_FACT"


def test_e02_washout_fact_not_system_recommendation(golden):
    w = _by(golden[2])["WASHOUT"]
    facts = [e for e in w.evidence if e.decision_source_type == "CURRENT_STUDY_FACT"]
    assert facts
    assert all(e.decision_source_type != "SYSTEM_RECOMMENDATION" for e in facts)


def test_e03_washout_fact_direct_applicability(golden):
    w = _by(golden[2])["WASHOUT"]
    facts = [e for e in w.evidence if e.evidence_type == "STRUCTURED_STUDY_FACT"]
    assert facts and facts[0].applicability == "DIRECT"


def test_e04_recommendation_separate_from_fact(golden):
    w = _by(golden[2])["WASHOUT"]
    assert w.recommendation is not None
    # recommendation status is BLOCKED / not a silent new washout value invention
    assert w.current_context.get("calculated") is False


# ---------------------------------------------------------------------------
# F. Recommendation separation
# ---------------------------------------------------------------------------


def test_f01_no_domain_auto_approved(golden):
    assert all(d.status != "APPROVED" for d in golden[2])


def test_f02_study_mutated_false(golden):
    assert all(d.study_mutated is False for d in golden[2])


def test_f03_recommendation_not_expert_decision(golden):
    for d in golden[2]:
        if d.recommendation:
            assert d.expert_decision_id is None


# ---------------------------------------------------------------------------
# G. Evidence applicability
# ---------------------------------------------------------------------------


def test_g01_applicability_values_on_evidence(golden):
    for d in golden[2]:
        for e in d.evidence:
            assert e.applicability in {
                "DIRECT",
                "HIGH",
                "MODERATE",
                "LOW",
                "UNKNOWN",
                "NOT_APPLICABLE",
            }


def test_g02_verified_plus_unknown_valid():
    ea = EvidenceApplicability(
        evidence_id="e1",
        applicability="UNKNOWN",
        applicability_reason="not reviewed",
    )
    assert ea.applicability == "UNKNOWN"


def test_g03_invalid_applicability_raises():
    with pytest.raises(ValueError):
        EvidenceApplicability(evidence_id="e1", applicability="PROBABLE")


def test_g04_matrix_excludes_low_as_direct_support():
    from app.domain.decision_matrix import build_option_matrix_row

    ev = [
        evidence(
            evidence_type="ANALOGUE_STUDY",
            support_level="SUPPORTS",
            option="STANDARD_2X2_CROSSOVER",
            excerpt="similar study",
            applicability="LOW",
            applicability_reason="different substance",
        )
    ]
    row = build_option_matrix_row(
        option="STANDARD_2X2_CROSSOVER",
        evidence=ev,
        recommendation_status="INSUFFICIENT_EVIDENCE",
        missing=[],
    )
    assert row["supporting"][0]["counts_as_direct_support"] is False


def test_g05_matrix_current_fact_counts():
    from app.domain.decision_matrix import build_option_matrix_row

    ev = [
        evidence(
            evidence_type="STRUCTURED_STUDY_FACT",
            support_level="SUPPORTS",
            option="FIXED_DURATION",
            excerpt="washout 7 days",
            applicability="DIRECT",
            decision_source_type="CURRENT_STUDY_FACT",
        )
    ]
    row = build_option_matrix_row(
        option="FIXED_DURATION", evidence=ev, recommendation_status="PARTIALLY_SUPPORTED", missing=[]
    )
    assert row["supporting"][0]["counts_as_direct_support"] is True


# ---------------------------------------------------------------------------
# H. Applicability dimensions
# ---------------------------------------------------------------------------


def test_h01_analogue_dimensions_present():
    a = assess_analogue_applicability(
        same_substance=True, same_dosage_form=True, same_dose=False, same_population=True
    )
    assert a.dimensions["dose"] == "DIFFERENT"
    assert a.applicability == "MODERATE"


def test_h02_unknown_dimension_stays_unknown():
    a = assess_analogue_applicability(same_substance=None)
    assert a.applicability == "UNKNOWN"
    assert a.dimensions["active_substance"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# I. Analogue study applicability
# ---------------------------------------------------------------------------


def test_i01_same_substance_different_dose_not_direct():
    a = assess_analogue_applicability(
        same_substance=True, same_dosage_form=True, same_dose=False, same_population=True
    )
    assert a.applicability != "DIRECT"


def test_i02_different_substance_low():
    a = assess_analogue_applicability(same_substance=False, same_dosage_form=True)
    assert a.applicability == "LOW"


def test_i03_high_still_not_auto_direct():
    a = assess_analogue_applicability(
        same_substance=True, same_dosage_form=True, same_dose=True, same_population=True
    )
    assert a.applicability == "HIGH"
    assert "not automatically DIRECT" in a.applicability_reason


# ---------------------------------------------------------------------------
# J. Regulatory applicability
# ---------------------------------------------------------------------------


def test_j01_explicit_same_context_direct():
    a = assess_regulatory_applicability(explicitly_same_context=True, reviewed=True)
    assert a.applicability == "DIRECT"


def test_j02_unreviewed_unknown():
    a = assess_regulatory_applicability(explicitly_same_context=None)
    assert a.applicability == "UNKNOWN"
    assert "not been reviewed" in a.applicability_reason


def test_j03_not_applicable():
    a = assess_regulatory_applicability(explicitly_same_context=False)
    assert a.applicability == "NOT_APPLICABLE"


# ---------------------------------------------------------------------------
# K. Stale applicability
# ---------------------------------------------------------------------------


def test_k01_version_change_stales():
    items = [
        EvidenceApplicability(
            evidence_id="SRC-1",
            applicability="HIGH",
            applicability_reason="reviewed",
            review_status="REVIEWED",
            source_version_id="v1",
        )
    ]
    stale = stale_on_source_version_change(items, evidence_id="SRC-1", old_version="v1", new_version="v2")
    assert stale
    assert stale[0].review_status == "REQUIRES_REVIEW"


def test_k02_unrelated_evidence_not_staled():
    items = [
        EvidenceApplicability(
            evidence_id="SRC-2",
            applicability="HIGH",
            review_status="REVIEWED",
            source_version_id="v1",
        )
    ]
    stale = stale_on_source_version_change(items, evidence_id="SRC-1", old_version="v1", new_version="v2")
    assert stale == []


# ---------------------------------------------------------------------------
# L. Decision recomputation
# ---------------------------------------------------------------------------


def test_l01_selective_recompute_skips_food(golden):
    pkg, ctx, decisions = golden
    food_id = _by(decisions)["FOOD"].id
    out = recompute_decisions(ctx, previous=decisions, domains=["WASHOUT", "SAMPLING"])
    domains = {d.domain for d in out}
    assert "WASHOUT" in domains and "SAMPLING" in domains
    # FOOD preserved from previous
    assert any(d.domain == "FOOD" and d.id == food_id for d in out)


def test_l02_full_recompute_all_domains(golden):
    from app.domain.decision_engine import EVALUATORS

    out = recompute_decisions(golden[1], previous=golden[2])
    # ProtocolDecision evaluators (5 domains). STATISTICS is registry-tracked but
    # planned via Statistics Engine (Phase 15.5), not ProtocolDecision evaluators.
    assert {d.domain for d in out} == set(EVALUATORS)


# ---------------------------------------------------------------------------
# M. Change impact
# ---------------------------------------------------------------------------


def test_m01_t_half_invalidates_washout_sampling_only(golden):
    decisions = list(golden[2])
    result = invalidate_on_upstream_change(decisions, changed_field="t_half")
    assert set(result["affected_domains"]) == {"WASHOUT", "SAMPLING"}
    food = _by(decisions)["FOOD"]
    assert food.status != "SUPERSEDED"


def test_m02_dose_invalidates_design_only(golden):
    decisions = list(golden[2])
    # clone statuses
    result = invalidate_on_upstream_change(decisions, changed_field="reference_product.dose")
    assert result["affected_domains"] == ["DESIGN"]
    assert _by(decisions)["FOOD"].status != "SUPERSEDED"
    assert _by(decisions)["WASHOUT"].status != "SUPERSEDED"


def test_m03_tmax_does_not_touch_food(golden):
    decisions = list(golden[2])
    result = invalidate_on_upstream_change(decisions, changed_field="tmax")
    assert "FOOD" not in result["affected_domains"]


# ---------------------------------------------------------------------------
# N. Expert decision / KEEP_CURRENT_VALUE
# ---------------------------------------------------------------------------


def test_n01_keep_current_does_not_rewrite_evidence():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    # Provide half_life so WASHOUT can be evaluated without gap block... still may be insufficient
    # Use FOOD which is REVIEW_REQUIRED
    _, decisions = recompute_from_package(pkg, study_id="s-keep")
    food = _by(decisions)["FOOD"]
    excerpts = [e.excerpt for e in food.evidence]
    res = keep_current_value(food, reviewer="expert", rationale="Keep current food condition")
    assert res["source_evidence_rewritten"] is False
    assert [e.excerpt for e in food.evidence] == excerpts
    assert food.status == "APPROVED"
    assert food.expert_actions[-1]["action"] == "KEEP_CURRENT_VALUE"
    assert food.expert_actions[-1]["creates_system_recommendation"] is False


def test_n02_keep_current_not_system_recommendation():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    _, decisions = recompute_from_package(pkg, study_id="s-keep2")
    food = _by(decisions)["FOOD"]
    keep_current_value(food, reviewer="e", rationale="confirm")
    assert food.expert_actions[-1]["source_type"] == "EXPERT_DECISION"


# ---------------------------------------------------------------------------
# O. API
# ---------------------------------------------------------------------------


def test_o01_api_dependencies(client: TestClient, golden):
    pkg, ctx, decisions = golden
    put_context("UPDCB-02-BE-2026", ctx, package_id=pkg.package_id)
    put_decisions("UPDCB-02-BE-2026", decisions, package_id=pkg.package_id)
    d = _by(decisions)["DESIGN"]
    r = client.get(f"/api/decision-center/studies/UPDCB-02-BE-2026/decisions/{d.id}/dependencies")
    assert r.status_code == 200
    assert "reference_product.dose" in r.json()["blocking_conflict_fields"]


def test_o02_api_blockers(client: TestClient, golden):
    pkg, ctx, decisions = golden
    put_context("UPDCB-02-BE-2026", ctx, package_id=pkg.package_id)
    put_decisions("UPDCB-02-BE-2026", decisions, package_id=pkg.package_id)
    w = _by(decisions)["WASHOUT"]
    r = client.get(f"/api/decision-center/studies/UPDCB-02-BE-2026/decisions/{w.id}/blockers")
    assert r.status_code == 200
    body = r.json()
    assert body["blocked"] is True
    assert any(b["blocking_reason_code"] == "MISSING_HALF_LIFE_FOR_WASHOUT" for b in body["blocking_reasons"])


def test_o03_api_applicability(client: TestClient, golden):
    pkg, ctx, decisions = golden
    put_decisions("UPDCB-02-BE-2026", decisions, package_id=pkg.package_id)
    w = _by(decisions)["WASHOUT"]
    r = client.get(f"/api/decision-center/studies/UPDCB-02-BE-2026/decisions/{w.id}/applicability")
    assert r.status_code == 200
    assert "verification_status and applicability are independent" in r.json()["note"]


def test_o04_api_evidence_matrix_fields(client: TestClient, golden):
    pkg, _, decisions = golden
    put_decisions("UPDCB-02-BE-2026", decisions, package_id=pkg.package_id)
    w = _by(decisions)["WASHOUT"]
    r = client.get(f"/api/decision-center/studies/UPDCB-02-BE-2026/decisions/{w.id}/evidence")
    assert r.status_code == 200
    ev = r.json()["evidence"]
    assert ev and "applicability" in ev[0] and "verification_status" in ev[0]


def test_o05_api_keep_current(client: TestClient):
    clear_decision_store()
    r = client.post("/api/decision-center/fixtures/updcb-real/recompute")
    assert r.status_code == 201
    study_id = r.json()["study_id"]
    food = next(d for d in r.json()["decisions"] if d["domain"] == "FOOD")
    # Unblock food is already REVIEW_REQUIRED — keep current
    # Need decision object in store — fixture recompute put it
    kr = client.post(
        f"/api/decision-center/studies/{study_id}/decisions/{food['id']}/keep-current",
        json={"reviewer": "expert", "rationale": "Keep fasting+fed"},
    )
    assert kr.status_code == 200
    assert kr.json()["source_evidence_rewritten"] is False


# ---------------------------------------------------------------------------
# P. UI contracts
# ---------------------------------------------------------------------------


def test_p01_ui_display_has_blocking_why(golden):
    d = _by(golden[2])["DESIGN"].to_dict(for_ui=True)
    assert isinstance(d["display"]["blocking_why"], list)
    assert d["display"]["blocking_why"]


def test_p02_food_ui_blocking_why_empty_or_no_dose(golden):
    d = _by(golden[2])["FOOD"].to_dict(for_ui=True)
    assert "reference_product.dose" not in str(d["display"]["blocking_why"])


def test_p03_recommended_not_approved_flag(golden):
    for d in golden[2]:
        ui = d.to_dict(for_ui=True)
        assert ui["display"]["recommended_is_not_approved"] is True


# ---------------------------------------------------------------------------
# Q. AI-off
# ---------------------------------------------------------------------------


def test_q01_ai_off(client: TestClient):
    assert client.get("/api/health").json()["ai_enabled"] is False


def test_q02_dependency_logic_works_ai_off(golden):
    assert is_decision_blocked("WASHOUT", golden[1]).blocked is True


def test_q03_version_0161():
    assert get_settings().app_version == "0.33.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.33.0"


# ---------------------------------------------------------------------------
# R. MockAI
# ---------------------------------------------------------------------------


def test_r01_ai_cannot_approve(golden):
    with pytest.raises(PermissionError):
        ai_cannot_approve(_by(golden[2])["DESIGN"], actor="AI")


def test_r02_ai_cannot_finalize_applicability():
    with pytest.raises(PermissionError):
        ai_cannot_finalize_applicability(actor="MockAI")


def test_r03_ai_proposal_stays_proposed():
    cur = EvidenceApplicability(evidence_id="e1", applicability="UNKNOWN", review_status="PROPOSED")
    prop = apply_ai_applicability_proposal(cur, proposed_applicability="HIGH", reason="looks relevant")
    assert prop.review_status == "PROPOSED"
    assert prop.assessed_by == "AI"


# ---------------------------------------------------------------------------
# S. Golden fixture
# ---------------------------------------------------------------------------


def test_s01_fixture_id(golden):
    assert golden[0].fixture_id == "UPDCB-02-BE-2026-REAL-01"


def test_s02_dose_conflict_open(golden):
    assert "reference_product.dose" in golden[1].critical_conflict_fields()


def test_s03_not_all_blocked(golden):
    assert not all(d.status == "BLOCKED" for d in golden[2])


def test_s04_api_golden_statuses(client: TestClient):
    r = client.post("/api/decision-center/fixtures/updcb-real/recompute")
    assert r.status_code == 201
    st = r.json()["dependency_aware_statuses"]
    assert st["DESIGN"] == "BLOCKED"
    assert st["FOOD"] == "REVIEW_REQUIRED"
    assert st["WASHOUT"] == "BLOCKED"
    assert st["SAMPLING"] == "BLOCKED"
    assert st["ANALYTE_PK"] == "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# T. Negative cases
# ---------------------------------------------------------------------------


def test_t01_dose_does_not_globally_block():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    ctx, decisions = recompute_from_package(pkg)
    assert _by(decisions)["FOOD"].status != "BLOCKED"


def test_t02_missing_thalf_blocks_washout(golden):
    assert any(
        b.get("blocking_reason_code") == "MISSING_HALF_LIFE_FOR_WASHOUT"
        for b in _by(golden[2])["WASHOUT"].blocking_reasons
    )


def test_t03_missing_thalf_affects_sampling_when_registered(golden):
    assert any(
        b.get("blocking_reason_code") == "MISSING_HALF_LIFE_FOR_WASHOUT"
        for b in _by(golden[2])["SAMPLING"].blocking_reasons
    )


def test_t04_missing_tmax_blocks_sampling(golden):
    assert any(
        b.get("blocking_reason_code") == "MISSING_TMAX_FOR_SAMPLING"
        for b in _by(golden[2])["SAMPLING"].blocking_reasons
    )


def test_t05_cvintra_not_invented(golden):
    assert golden[1].cvintra is None
    design = _by(golden[2])["DESIGN"]
    assert any(g["code"] == "MISSING_CVINTRA" for g in design.knowledge_gaps)


def test_t06_current_fact_not_mislabeled(golden):
    w = _by(golden[2])["WASHOUT"]
    for e in w.evidence:
        if e.evidence_type == "STRUCTURED_STUDY_FACT":
            assert e.decision_source_type == "CURRENT_STUDY_FACT"


def test_t07_verified_unknown_applicability_ok():
    e = evidence(
        evidence_type="REGULATORY_CLAIM",
        support_level="CONTEXT_ONLY",
        excerpt="Decision 85 claim",
        status="VERIFIED",
        applicability="UNKNOWN",
        applicability_reason="not reviewed",
        claim_id="CL-1",
    )
    assert e.status == "VERIFIED" and e.applicability == "UNKNOWN"


def test_t08_low_not_direct_support():
    from app.domain.decision_matrix import build_option_matrix_row

    ev = [
        evidence(
            evidence_type="ANALOGUE_STUDY",
            support_level="SUPPORTS",
            option="STANDARD_2X2_CROSSOVER",
            excerpt="x",
            applicability="LOW",
        )
    ]
    row = build_option_matrix_row(
        option="STANDARD_2X2_CROSSOVER", evidence=ev, recommendation_status="X", missing=[]
    )
    assert row["supporting"][0]["counts_as_direct_support"] is False


def test_t09_version_change_invalidates_applicability():
    items = [
        EvidenceApplicability(
            evidence_id="e", applicability="DIRECT", source_version_id="1", review_status="REVIEWED"
        )
    ]
    stale_on_source_version_change(items, evidence_id="e", old_version="1", new_version="2")
    assert items[0].review_status == "REQUIRES_REVIEW"


def test_t10_one_dependency_not_all_domains(golden):
    decisions = list(golden[2])
    invalidate_on_upstream_change(decisions, changed_field="tmax")
    assert _by(decisions)["FOOD"].status != "SUPERSEDED"
    assert _by(decisions)["DESIGN"].status != "SUPERSEDED"


def test_t11_expert_does_not_rewrite_source():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    _, decisions = recompute_from_package(pkg)
    food = _by(decisions)["FOOD"]
    before = [(e.id, e.excerpt, e.status) for e in food.evidence]
    keep_current_value(food, reviewer="e", rationale="keep")
    assert [(e.id, e.excerpt, e.status) for e in food.evidence] == before


def test_t12_system_recommendation_separate():
    assert classify_decision_input_source(
        evidence_type="STRUCTURED_STUDY_FACT", is_system_recommendation=True
    ) == "SYSTEM_RECOMMENDATION"
    assert classify_decision_input_source(evidence_type="STRUCTURED_STUDY_FACT") == "CURRENT_STUDY_FACT"


def test_t13_no_sample_size_engine():
    assert "SAMPLE_SIZE" not in DECISION_DEPENDENCY_REGISTRY


def test_t14_statistics_in_dependency_registry():
    # Phase 15.5 registers STATISTICS domain (method planning); still no silent medical defaults.
    assert "STATISTICS" in DECISION_DEPENDENCY_REGISTRY
    assert "SAMPLE_SIZE" not in DECISION_DEPENDENCY_REGISTRY


def test_t15_partial_support_explanation(golden):
    food = _by(golden[2])["FOOD"]
    assert food.recommendation.status == "PARTIALLY_SUPPORTED"
    assert food.non_blocking_issues  # meal composition etc.


def test_t16_blocker_has_provenance(golden):
    for d in golden[2]:
        for b in d.blocking_reasons:
            assert b.get("blocking_reason_code")
            assert b.get("kind") in {"CONFLICT", "GAP", "MISSING_FIELD", "EVIDENCE"}
            assert b.get("reference_id") or b.get("field_path")

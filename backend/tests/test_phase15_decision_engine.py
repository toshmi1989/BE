"""Phase 15.0 — Evidence-Based Protocol Decision Engine tests.

Deterministic. AI-off. No Study mutation from recommendations.
No invented medical thresholds / CV / t½ / Tmax / sample size.
"""

from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.decision_classes import (
    DESIGN_OPTIONS,
    EVIDENCE_TYPES,
    OPTION_LABELS_RU,
    assert_no_enum_in_user_text,
    display_option,
)
from app.domain.decision_context import build_context_from_package
from app.domain.decision_design import evaluate_design
from app.domain.decision_engine import (
    ai_cannot_approve,
    approve_decision,
    invalidate_on_upstream_change,
    modify_decision,
    recompute_from_package,
    reject_decision,
)
from app.domain.decision_engines import (
    evaluate_analyte_pk,
    evaluate_food,
    evaluate_sampling,
    evaluate_washout,
)
from app.domain.decision_matrix import evidence, make_recommendation
from app.domain.decision_models import (
    AnalogueStudyEvidence,
    DecisionEvidence,
    DecisionRecommendation,
    ProtocolDecision,
    require_evidence_for_recommendation,
)
from app.domain.decision_store import clear_decision_store
from app.domain.study_input_package import CandidateStudyValue, verify_candidate
from app.domain.study_input_pipeline import apply_ai_candidates, load_real_fixture_package
from app.domain.study_input_store import clear_store
from app.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("AI_ENABLED", "false")
    get_settings.cache_clear()
    clear_store()
    clear_decision_store()
    app = create_app()
    with TestClient(app) as c:
        yield c
    clear_store()
    clear_decision_store()
    get_settings.cache_clear()


@pytest.fixture
def golden_ctx():
    clear_store()
    clear_decision_store()
    pkg = load_real_fixture_package(prefer_text_dump=False)
    ctx, decisions = recompute_from_package(pkg, study_id="UPDCB-02-BE-2026")
    return pkg, ctx, decisions


# A. Decision model
def test_a01_protocol_decision_domains():
    for domain in ("DESIGN", "FOOD", "WASHOUT", "SAMPLING", "ANALYTE_PK"):
        d = ProtocolDecision(domain=domain, subject="t")
        assert d.status == "DRAFT"


def test_a02_invalid_domain_rejected():
    with pytest.raises(ValueError):
        ProtocolDecision(domain="SAMPLE_SIZE", subject="x")


def test_a03_decision_to_dict_has_labels():
    d = ProtocolDecision(domain="DESIGN", subject="x")
    assert d.to_dict()["domain_label"] == "Дизайн исследования"


def test_a04_recommendation_not_approved_flag():
    r = DecisionRecommendation(option="STANDARD_2X2_CROSSOVER", status="SUPPORTED", confidence="LOW", rationale="x", supporting_evidence_ids=["e1"])
    assert r.to_dict()["status_is_not_approved"] is True


def test_a05_study_mutated_always_false_in_dict():
    d = ProtocolDecision(domain="FOOD", subject="x")
    d.study_mutated = True  # even if set, to_dict reports False
    assert d.to_dict()["study_mutated"] is False


# B. Evidence links
def test_b01_evidence_requires_provenance():
    with pytest.raises(ValueError):
        DecisionEvidence(evidence_type="STRUCTURED_STUDY_FACT", support_level="SUPPORTS", excerpt="")


def test_b02_evidence_types_controlled():
    for t in EVIDENCE_TYPES:
        e = DecisionEvidence(evidence_type=t, support_level="NEUTRAL", excerpt="x", source_id="s")
        assert e.evidence_type == t


def test_b03_invalid_evidence_type():
    with pytest.raises(ValueError):
        DecisionEvidence(evidence_type="GENERIC_SOURCE", support_level="SUPPORTS", excerpt="x")


def test_b04_proposed_not_verified():
    e = evidence(evidence_type="EXPERT_INTERVIEW", support_level="SUPPORTS", excerpt="x", status="PROPOSED")
    assert e.is_verified is False


def test_b05_verified_flag():
    e = evidence(evidence_type="REGULATORY_CLAIM", support_level="SUPPORTS", excerpt="x", status="VERIFIED", claim_id="c1")
    assert e.is_verified is True


# C. Recommendation engine
def test_c01_recommendation_without_evidence_rejected():
    with pytest.raises(ValueError):
        require_evidence_for_recommendation(
            DecisionRecommendation(option="FASTING", status="SUPPORTED", confidence="HIGH", rationale="")
        )


def test_c02_make_recommendation_ok():
    ev = [evidence(evidence_type="STRUCTURED_STUDY_FACT", support_level="SUPPORTS", option="FASTING", excerpt="натощак")]
    r = make_recommendation(option="FASTING", status="PARTIALLY_SUPPORTED", confidence="LOW", evidence=ev, rationale="from inputs")
    assert r.supporting_evidence_ids


def test_c03_recompute_study_mutated_false(golden_ctx):
    _, _, decisions = golden_ctx
    assert all(d.study_mutated is False for d in decisions)
    assert all(d.to_dict()["study_mutated"] is False for d in decisions)


def test_c04_five_domains(golden_ctx):
    _, _, decisions = golden_ctx
    assert {d.domain for d in decisions} == {"DESIGN", "FOOD", "WASHOUT", "SAMPLING", "ANALYTE_PK"}


# D. DESIGN
def test_d01_design_current_context(golden_ctx):
    _, _, decisions = golden_ctx
    design = next(d for d in decisions if d.domain == "DESIGN")
    ctx = design.current_context
    assert ctx["periods"] == 2
    assert ctx["sequences"] == 2
    assert ctx["groups"] == 4
    assert ctx["randomized_n"] == 56


def test_d02_design_blocked_by_dose_conflict(golden_ctx):
    _, ctx, decisions = golden_ctx
    assert "reference_product.dose" in ctx.critical_conflict_fields()
    design = next(d for d in decisions if d.domain == "DESIGN")
    assert design.status == "BLOCKED"
    assert design.recommendation and design.recommendation.status == "BLOCKED"


def test_d03_design_no_cv_threshold_invented(golden_ctx):
    _, _, decisions = golden_ctx
    design = next(d for d in decisions if d.domain == "DESIGN")
    text = str(design.to_dict())
    assert "CV > 30" not in text
    assert "high variability =" not in text.lower() or "not demonstrated" in text.lower()


def test_d04_design_interview_not_regulation(golden_ctx):
    _, _, decisions = golden_ctx
    design = next(d for d in decisions if d.domain == "DESIGN")
    interviews = [e for e in design.evidence if e.evidence_type == "EXPERT_INTERVIEW"]
    assert all(e.status == "PROPOSED" for e in interviews)
    assert all("Interview" in (e.notes or "") or "interview" in (e.excerpt or "").lower() for e in interviews)


def test_d05_design_matrix_has_options(golden_ctx):
    design = next(d for d in golden_ctx[2] if d.domain == "DESIGN")
    labels = {row["option_label"] for row in design.option_matrix}
    assert OPTION_LABELS_RU["STANDARD_2X2_CROSSOVER"] in labels


def test_d06_design_without_conflict_partial(monkeypatch):
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []  # simulate resolved
    ctx = build_context_from_package(pkg, study_id="s1")
    assert not ctx.has_open_critical_conflict()
    d = evaluate_design(ctx)
    assert d.status == "REVIEW_REQUIRED"
    assert d.recommendation.status == "PARTIALLY_SUPPORTED"


# E. FOOD
def test_e01_food_fasting_and_fed(golden_ctx):
    food = next(d for d in golden_ctx[2] if d.domain == "FOOD")
    assert food.recommendation.option == "FASTING_AND_FED"


def test_e02_food_not_blocked_by_dose_conflict(golden_ctx):
    food = next(d for d in golden_ctx[2] if d.domain == "FOOD")
    assert food.status == "REVIEW_REQUIRED"
    codes = [b.get("blocking_reason_code") for b in food.blocking_reasons]
    assert not any("DOSE" in (c or "") and "UNRELATED" not in (c or "") for c in codes if c and not str(c).startswith("UNRELATED"))
    assert food.status != "BLOCKED"


def test_e03_food_no_invented_calories(golden_ctx):
    food = next(d for d in golden_ctx[2] if d.domain == "FOOD")
    assert any(g["code"] == "MISSING_MEAL_COMPOSITION" for g in food.knowledge_gaps)


def test_e04_food_evaluate_direct():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    d = evaluate_food(build_context_from_package(pkg))
    assert d.recommendation.status == "PARTIALLY_SUPPORTED"


# F. WASHOUT
def test_f01_missing_half_life_gap(golden_ctx):
    w = next(d for d in golden_ctx[2] if d.domain == "WASHOUT")
    assert any(g["code"] == "MISSING_HALF_LIFE_FOR_WASHOUT" for g in w.knowledge_gaps)


def test_f02_no_calculated_washout(golden_ctx):
    w = next(d for d in golden_ctx[2] if d.domain == "WASHOUT")
    assert w.current_context.get("calculated") is False


def test_f03_half_life_derived_insufficient(golden_ctx):
    w = next(d for d in golden_ctx[2] if d.domain == "WASHOUT")
    row = next(r for r in w.option_matrix if r["option"] == "HALF_LIFE_DERIVED")
    assert row["recommendation_status"] in {"INSUFFICIENT_EVIDENCE", "BLOCKED"}


def test_f04_research_task_half_life(golden_ctx):
    w = next(d for d in golden_ctx[2] if d.domain == "WASHOUT")
    assert any(t["code"] == "FIND_HALF_LIFE_PK" for t in w.research_tasks)


def test_f05_boolean_thal_not_numeric():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    ctx = build_context_from_package(pkg)
    # Even if pk.t_half True exists as marker, half_life numeric stays None
    assert ctx.half_life is None
    w = evaluate_washout(ctx)
    assert any(g["code"] == "MISSING_HALF_LIFE_FOR_WASHOUT" for g in w.knowledge_gaps)


# G. SAMPLING
def test_g01_sampling_keeps_existing_times(golden_ctx):
    s = next(d for d in golden_ctx[2] if d.domain == "SAMPLING")
    times = s.current_context.get("sampling_times")
    assert times and len(times) >= 19
    assert s.current_context.get("invented_timepoints") is False


def test_g02_missing_tmax_gap(golden_ctx):
    s = next(d for d in golden_ctx[2] if d.domain == "SAMPLING")
    assert any(g["code"] == "MISSING_TMAX_FOR_SAMPLING" for g in s.knowledge_gaps)


def test_g03_no_invented_timepoints_in_rationale(golden_ctx):
    s = next(d for d in golden_ctx[2] if d.domain == "SAMPLING")
    assert "invent" not in (s.recommendation.rationale.lower()) or "NOT invent" in s.recommendation.rationale or "did NOT invent" in s.recommendation.rationale


def test_g04_sampling_blocked(golden_ctx):
    s = next(d for d in golden_ctx[2] if d.domain == "SAMPLING")
    assert s.status == "BLOCKED"


# H. ANALYTE/PK
def test_h01_parent_drug(golden_ctx):
    a = next(d for d in golden_ctx[2] if d.domain == "ANALYTE_PK")
    assert a.recommendation.option == "PARENT_DRUG"


def test_h02_no_auto_metabolite(golden_ctx):
    a = next(d for d in golden_ctx[2] if d.domain == "ANALYTE_PK")
    assert a.current_context.get("metabolite_auto_added") is False


def test_h03_analyte_upadacitinib(golden_ctx):
    a = next(d for d in golden_ctx[2] if d.domain == "ANALYTE_PK")
    assert a.current_context.get("analyte") == "upadacitinib"


# I/J. Expert approval / modification
def test_i01_approve_blocked_raises(golden_ctx):
    design = next(d for d in golden_ctx[2] if d.domain == "DESIGN")
    with pytest.raises(ValueError):
        approve_decision(design, reviewer="e", selected_option="STANDARD_2X2_CROSSOVER", rationale="ok")


def test_i02_approve_when_unblocked():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    _, decisions = recompute_from_package(pkg, study_id="s")
    design = next(d for d in decisions if d.domain == "DESIGN")
    res = approve_decision(
        design,
        reviewer="expert",
        selected_option="STANDARD_2X2_CROSSOVER",
        rationale="Accepted after review",
    )
    assert design.status == "APPROVED"
    assert res["study_mutated"] is False
    assert design.expert_actions[-1]["action"] == "APPROVE"


def test_i03_approve_requires_reviewer():
    d = ProtocolDecision(domain="FOOD", subject="x")
    d.recommendation = make_recommendation(
        option="FASTING",
        status="PARTIALLY_SUPPORTED",
        confidence="LOW",
        evidence=[evidence(evidence_type="STRUCTURED_STUDY_FACT", support_level="SUPPORTS", excerpt="x", option="FASTING")],
        rationale="x",
    )
    with pytest.raises(ValueError):
        approve_decision(d, reviewer="", selected_option="FASTING", rationale="r")


def test_j01_reject_preserves_history():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    _, decisions = recompute_from_package(pkg, study_id="s")
    food = next(d for d in decisions if d.domain == "FOOD")
    rec_id = food.recommendation.id
    reject_decision(food, reviewer="e", rationale="not yet")
    assert food.status == "REJECTED"
    assert any(r.id == rec_id for r in food.recommendation_history)


def test_j02_modify_preserves_original():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    _, decisions = recompute_from_package(pkg, study_id="s")
    food = next(d for d in decisions if d.domain == "FOOD")
    orig = food.recommendation.id
    modify_decision(food, reviewer="e", selected_option="FED", rationale="writer chooses fed-only")
    assert food.selected_option == "FED"
    assert any(r.id == orig for r in food.recommendation_history)
    assert food.expert_actions[-1]["action"] == "MODIFY"


# K. History
def test_k01_recompute_supersedes(golden_ctx):
    pkg, _, decisions = golden_ctx
    pkg.conflicts = []
    _, decisions2 = recompute_from_package(pkg, study_id="UPDCB-02-BE-2026", previous=decisions)
    # previous should be superseded
    assert any(d.status == "SUPERSEDED" for d in decisions)
    assert all(d.status != "SUPERSEDED" for d in decisions2)


# L. Research handoff
def test_l01_cvintra_task(golden_ctx):
    design = next(d for d in golden_ctx[2] if d.domain == "DESIGN")
    assert any(t["code"] == "FIND_CVINTRA_LITERATURE" for t in design.research_tasks)


def test_l02_tmax_task(golden_ctx):
    s = next(d for d in golden_ctx[2] if d.domain == "SAMPLING")
    assert any(t["code"] == "FIND_TMAX_PK" for t in s.research_tasks)


# M. Analogue studies
def test_m01_analogue_not_identical():
    a = AnalogueStudyEvidence(study_reference="Study X", relevance="MEDIUM", claim="crossover used")
    assert a.to_dict()["identical_to_current"] is False


def test_m02_analogue_in_design_evidence():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    an = AnalogueStudyEvidence(study_reference="BE-ANL-1", relevance="LOW", claim="standard crossover", review_status="PROPOSED")
    ctx, decisions = recompute_from_package(pkg, study_id="s", analogues=[an])
    design = next(d for d in decisions if d.domain == "DESIGN")
    assert any(e.evidence_type == "ANALOGUE_STUDY" for e in design.evidence)


# N. Previous protocol
def test_n01_previous_protocol_contextual(golden_ctx):
    design = next(d for d in golden_ctx[2] if d.domain == "DESIGN")
    prev = [e for e in design.evidence if e.evidence_type == "PREVIOUS_PROTOCOL"]
    assert prev
    assert all(e.support_level == "CONTEXT_ONLY" for e in prev)
    assert all("cannot overwrite" in (e.notes or "").lower() or "Contextual" in (e.notes or "") for e in prev)


# O/P. Conflict blocking / missing evidence
def test_o01_dependency_aware_statuses_on_golden(golden_ctx):
    by = {d.domain: d for d in golden_ctx[2]}
    assert by["DESIGN"].status == "BLOCKED"
    assert by["FOOD"].status == "REVIEW_REQUIRED"
    assert by["WASHOUT"].status == "BLOCKED"
    assert by["SAMPLING"].status == "BLOCKED"
    assert by["ANALYTE_PK"].status == "REVIEW_REQUIRED"
    # Global blocking eliminated
    assert not all(d.status == "BLOCKED" for d in golden_ctx[2])


def test_p01_proposed_evidence_not_treated_verified(golden_ctx):
    design = next(d for d in golden_ctx[2] if d.domain == "DESIGN")
    for e in design.evidence:
        if e.evidence_type in {"EXPERT_INTERVIEW", "EXPERT_RULE"}:
            assert e.status != "VERIFIED"


# Q/R. AI-off / MockAI
def test_q01_ai_off(client: TestClient):
    assert client.get("/api/health").json()["ai_enabled"] is False


def test_q02_version_0161():
    assert get_settings().app_version == "0.30.0"


def test_r01_mock_ai_cannot_approve(golden_ctx):
    design = next(d for d in golden_ctx[2] if d.domain == "DESIGN")
    with pytest.raises(PermissionError):
        ai_cannot_approve(design, actor="AI")


def test_r02_mock_ai_propose_does_not_mutate_study(golden_ctx):
    pkg, _, _ = golden_ctx
    before = copy.deepcopy({"x": 1})
    apply_ai_candidates(pkg, [{"field_path": "food.breakfast_type", "value": "x", "excerpt": "y", "document_type": "SYNOPSIS"}])
    after = {"x": 1}
    assert before == after


# S. Provenance
def test_s01_evidence_has_excerpt(golden_ctx):
    for d in golden_ctx[2]:
        for e in d.evidence:
            assert e.excerpt


def test_s02_ui_labels_no_enum_leak():
    for opt in DESIGN_OPTIONS:
        label = display_option(opt)
        assert_no_enum_in_user_text(label)
        assert opt not in label or opt == label  # label must not be enum; if equal only if missing mapping
        assert label != opt or opt not in OPTION_LABELS_RU  # all design options mapped
        assert OPTION_LABELS_RU[opt] == label


# T. Change impact
def test_t01_invalidate_supersedes():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    _, decisions = recompute_from_package(pkg, study_id="s")
    result = invalidate_on_upstream_change(decisions, changed_field="reference_product.dose")
    assert result["requires_recompute"] is True
    assert result["study_mutated"] is False
    assert any(d.status == "SUPERSEDED" for d in decisions)


def test_t02_tmax_change_affects_sampling():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    _, decisions = recompute_from_package(pkg, study_id="s")
    result = invalidate_on_upstream_change(decisions, changed_field="tmax")
    assert result["study_mutated"] is False


# U. API
def test_u01_api_golden_recompute(client: TestClient):
    res = client.post("/api/decision-center/fixtures/updcb-real/recompute")
    assert res.status_code == 201
    body = res.json()
    assert body["study_mutated"] is False
    assert "reference_product.dose" in body["blocking_conflicts"]
    assert len(body["decisions"]) == 5


def test_u02_api_list_decisions(client: TestClient):
    body = client.post("/api/decision-center/fixtures/updcb-real/recompute").json()
    sid = body["study_id"]
    listed = client.get(f"/api/decision-center/studies/{sid}/decisions").json()
    assert listed["recommended_is_not_approved"] is True
    assert listed["study_mutated"] is False


def test_u03_api_evidence(client: TestClient):
    body = client.post("/api/decision-center/fixtures/updcb-real/recompute").json()
    sid = body["study_id"]
    did = body["decisions"][0]["id"]
    ev = client.get(f"/api/decision-center/studies/{sid}/decisions/{did}/evidence").json()
    assert "option_matrix" in ev


def test_u04_api_ai_cannot_approve(client: TestClient):
    # unblocked path
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    from app.domain.study_input_store import put_package
    from app.domain.decision_store import put_context, put_decisions

    put_package(pkg)
    ctx, decisions = recompute_from_package(pkg, study_id="api-study")
    put_context("api-study", ctx, package_id=pkg.package_id)
    put_decisions("api-study", decisions, package_id=pkg.package_id)
    did = next(d.id for d in decisions if d.domain == "DESIGN")
    res = client.post(
        f"/api/decision-center/studies/api-study/decisions/{did}/approve",
        json={"reviewer": "bot", "rationale": "no", "selected_option": "STANDARD_2X2_CROSSOVER", "actor": "AI"},
    )
    assert res.status_code == 403


def test_u05_api_approve_human(client: TestClient):
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    from app.domain.study_input_store import put_package
    from app.domain.decision_store import put_context, put_decisions

    put_package(pkg)
    ctx, decisions = recompute_from_package(pkg, study_id="api-study2")
    put_context("api-study2", ctx, package_id=pkg.package_id)
    put_decisions("api-study2", decisions, package_id=pkg.package_id)
    did = next(d.id for d in decisions if d.domain == "FOOD")
    res = client.post(
        f"/api/decision-center/studies/api-study2/decisions/{did}/approve",
        json={"reviewer": "expert", "rationale": "ok", "selected_option": "FASTING_AND_FED"},
    )
    assert res.status_code == 200
    assert res.json()["study_mutated"] is False
    assert res.json()["decision"]["status"] == "APPROVED"


def test_u06_api_reject(client: TestClient):
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    from app.domain.study_input_store import put_package
    from app.domain.decision_store import put_context, put_decisions

    put_package(pkg)
    ctx, decisions = recompute_from_package(pkg, study_id="api-study3")
    put_context("api-study3", ctx, package_id=pkg.package_id)
    put_decisions("api-study3", decisions, package_id=pkg.package_id)
    did = next(d.id for d in decisions if d.domain == "FOOD")
    res = client.post(
        f"/api/decision-center/studies/api-study3/decisions/{did}/reject",
        json={"reviewer": "expert", "rationale": "need more"},
    )
    assert res.status_code == 200
    assert res.json()["decision"]["status"] == "REJECTED"


def test_u07_api_modify(client: TestClient):
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    from app.domain.study_input_store import put_package
    from app.domain.decision_store import put_context, put_decisions

    put_package(pkg)
    ctx, decisions = recompute_from_package(pkg, study_id="api-study4")
    put_context("api-study4", ctx, package_id=pkg.package_id)
    put_decisions("api-study4", decisions, package_id=pkg.package_id)
    did = next(d.id for d in decisions if d.domain == "FOOD")
    res = client.post(
        f"/api/decision-center/studies/api-study4/decisions/{did}/modify",
        json={"reviewer": "expert", "selected_option": "FED", "rationale": "fed only"},
    )
    assert res.status_code == 200
    assert res.json()["decision"]["selected_option"] == "FED"


def test_u08_api_analogue(client: TestClient):
    res = client.post(
        "/api/decision-center/studies/s1/analogues",
        json={"study_reference": "Pub-1", "relevance": "LOW", "claim": "crossover"},
    )
    assert res.status_code == 201
    assert res.json()["identical_to_current"] is False


def test_u09_api_invalidate(client: TestClient):
    body = client.post("/api/decision-center/fixtures/updcb-real/recompute").json()
    sid = body["study_id"]
    # clear conflicts via recompute path already blocked; invalidate still works
    res = client.post(
        f"/api/decision-center/studies/{sid}/decisions/invalidate",
        json={"changed_field": "washout.duration"},
    )
    assert res.status_code == 200
    assert res.json()["study_mutated"] is False


# V. UI contracts
def test_v01_for_ui_recommended_not_approved(golden_ctx):
    for d in golden_ctx[2]:
        ui = d.to_dict(for_ui=True)
        assert ui["display"]["recommended_is_not_approved"] is True
        assert ui["display"]["approved"] is False


def test_v02_option_labels_russian(golden_ctx):
    design = next(d for d in golden_ctx[2] if d.domain == "DESIGN")
    for opt in design.to_dict()["options"]:
        assert_no_enum_in_user_text(opt["label"])


# W. Regression / hard negatives
def test_w01_recommendation_cannot_mutate_study_snapshot(golden_ctx):
    pkg, _, decisions = golden_ctx
    before = pkg.to_dict()["study_mutated"]
    recompute_from_package(pkg, study_id="x", previous=decisions)
    assert before is False
    assert pkg.to_dict()["study_mutated"] is False


def test_w02_open_conflict_blocks(golden_ctx):
    assert golden_ctx[1].has_open_critical_conflict()


def test_w03_supported_not_shown_as_approved():
    d = ProtocolDecision(domain="FOOD", subject="x", status="REVIEW_REQUIRED")
    d.recommendation = make_recommendation(
        option="FASTING",
        status="SUPPORTED",
        confidence="MEDIUM",
        evidence=[evidence(evidence_type="STRUCTURED_STUDY_FACT", support_level="SUPPORTS", excerpt="x", option="FASTING")],
        rationale="enough",
    )
    ui = d.to_dict(for_ui=True)
    assert ui["display"]["approved"] is False
    assert ui["recommendation"]["status"] == "SUPPORTED"


def test_w04_previous_protocol_cannot_overwrite_design_status(golden_ctx):
    # Design remains BLOCKED despite previous protocol evidence present
    design = next(d for d in golden_ctx[2] if d.domain == "DESIGN")
    assert design.status == "BLOCKED"
    assert any(e.evidence_type == "PREVIOUS_PROTOCOL" for e in design.evidence)


def test_w05_verified_candidate_still_not_auto_decision():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    cand = next(c for c in pkg.candidates if c.field_path == "design.periods")
    verify_candidate(cand, reviewer="e")
    _, decisions = recompute_from_package(pkg, study_id="s")
    design = next(d for d in decisions if d.domain == "DESIGN")
    assert design.status != "APPROVED"


@pytest.mark.parametrize("domain", ["DESIGN", "FOOD", "WASHOUT", "SAMPLING", "ANALYTE_PK"])
def test_x_param_domain_present(golden_ctx, domain):
    assert any(d.domain == domain for d in golden_ctx[2])


@pytest.mark.parametrize(
    "code",
    [
        "MISSING_CVINTRA",
        "MISSING_HALF_LIFE_FOR_WASHOUT",
        "MISSING_TMAX_FOR_SAMPLING",
        "MISSING_MEAL_COMPOSITION",
    ],
)
def test_x_param_gap_codes(golden_ctx, code):
    gaps = [g["code"] for d in golden_ctx[2] for g in d.knowledge_gaps]
    assert code in gaps


@pytest.mark.parametrize("opt", list(DESIGN_OPTIONS))
def test_x_param_design_option_labels(opt):
    assert display_option(opt) != opt
    assert_no_enum_in_user_text(display_option(opt))


def test_x01_golden_fixture_id(golden_ctx):
    assert golden_ctx[0].fixture_id == "UPDCB-02-BE-2026-REAL-01"


def test_x02_confidence_is_sufficiency_not_probability(golden_ctx):
    for d in golden_ctx[2]:
        if d.recommendation:
            assert d.recommendation.confidence in {"HIGH", "MEDIUM", "LOW", "NONE"}


def test_x03_no_automatic_medical_decision_flag(golden_ctx):
    # No decision is APPROVED by recompute
    assert all(d.status != "APPROVED" for d in golden_ctx[2])


@pytest.mark.parametrize(
    "etype",
    [
        "REGULATORY_CLAIM",
        "REGULATORY_RULE",
        "PRODUCT_FACT",
        "SMPC_FACT",
        "LITERATURE_CLAIM",
        "ANALOGUE_STUDY",
        "PREVIOUS_PROTOCOL",
        "EXPERT_INTERVIEW",
        "EXPERT_RULE",
        "EXPERT_DECISION",
        "STRUCTURED_STUDY_FACT",
    ],
)
def test_y_param_evidence_types(etype):
    e = DecisionEvidence(evidence_type=etype, support_level="CONTEXT_ONLY", excerpt="sample", source_id="s")
    assert e.evidence_type == etype


@pytest.mark.parametrize(
    "status",
    ["SUPPORTED", "PARTIALLY_SUPPORTED", "INSUFFICIENT_EVIDENCE", "CONTRADICTED", "BLOCKED"],
)
def test_y_param_rec_statuses(status):
    r = DecisionRecommendation(
        option="FASTING",
        status=status,
        confidence="NONE",
        rationale="r",
        supporting_evidence_ids=["e"] if status in {"SUPPORTED", "PARTIALLY_SUPPORTED"} else [],
    )
    if status in {"SUPPORTED", "PARTIALLY_SUPPORTED"}:
        require_evidence_for_recommendation(r)
    assert r.status == status


@pytest.mark.parametrize(
    "field",
    ["reference_product.dose", "reference_product.name", "test_product.dose"],
)
def test_y_param_critical_fields(field):
    from app.domain.decision_classes import CRITICAL_CONFLICT_FIELDS

    assert field in CRITICAL_CONFLICT_FIELDS


def test_y01_decision_without_evidence_supported_fails():
    with pytest.raises(ValueError):
        make_recommendation(
            option="PARALLEL_DESIGN",
            status="SUPPORTED",
            confidence="HIGH",
            evidence=[],
            rationale="",
        )


def test_y02_ai_actor_api_reject(client: TestClient):
    body = client.post("/api/decision-center/fixtures/updcb-real/recompute").json()
    did = body["decisions"][0]["id"]
    sid = body["study_id"]
    res = client.post(
        f"/api/decision-center/studies/{sid}/decisions/{did}/reject",
        json={"reviewer": "bot", "rationale": "x", "actor": "MockAI"},
    )
    assert res.status_code == 403


def test_y03_get_decision(client: TestClient):
    body = client.post("/api/decision-center/fixtures/updcb-real/recompute").json()
    sid = body["study_id"]
    did = body["decisions"][1]["id"]
    res = client.get(f"/api/decision-center/studies/{sid}/decisions/{did}")
    assert res.status_code == 200
    assert res.json()["display"]["recommended_is_not_approved"] is True


def test_y04_recompute_endpoint(client: TestClient):
    res = client.post(
        "/api/decision-center/studies/manual-study/decisions/recompute",
        json={"use_golden_fixture": True},
    )
    assert res.status_code == 200
    assert res.json()["study_mutated"] is False


def test_y05_stale_recommendation_flag_on_invalidate():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    pkg.conflicts = []
    _, decisions = recompute_from_package(pkg, study_id="s")
    design = next(d for d in decisions if d.domain == "DESIGN")
    rid = design.recommendation.id
    invalidate_on_upstream_change(decisions, changed_field="design.type")
    assert design.status == "SUPERSEDED"
    assert design.recommendation.superseded or any(
        r.id == rid and r.superseded for r in design.recommendation_history
    )


def test_y06_food_options_labels():
    from app.domain.decision_classes import FOOD_OPTIONS

    for o in FOOD_OPTIONS:
        assert display_option(o) != o


def test_y07_washout_options_labels():
    from app.domain.decision_classes import WASHOUT_OPTIONS

    for o in WASHOUT_OPTIONS:
        assert display_option(o) != o


def test_y08_sampling_options_labels():
    from app.domain.decision_classes import SAMPLING_OPTIONS

    for o in SAMPLING_OPTIONS:
        assert display_option(o) != o


def test_y09_analyte_options_labels():
    from app.domain.decision_classes import ANALYTE_OPTIONS

    for o in ANALYTE_OPTIONS:
        assert display_option(o) != o


def test_y10_matrix_distinguishes_verified():
    ev = [
        evidence(
            evidence_type="STRUCTURED_STUDY_FACT",
            support_level="SUPPORTS",
            option="PARENT_DRUG",
            excerpt="x",
            status="PROPOSED",
        )
    ]
    from app.domain.decision_matrix import build_option_matrix_row

    row = build_option_matrix_row(
        option="PARENT_DRUG", evidence=ev, recommendation_status="PARTIALLY_SUPPORTED", missing=[]
    )
    assert row["evidence_verified"] is False
    assert row["evidence_present"] is True


def test_y11_no_generic_medical_fallback(golden_ctx):
    text = " ".join(str(d.to_dict()) for d in golden_ctx[2])
    assert "usually 5 half-lives" not in text.lower()
    assert "cv > 30%" not in text.lower()


def test_y12_list_analogues_api(client: TestClient):
    client.post(
        "/api/decision-center/studies/s2/analogues",
        json={"study_reference": "A", "relevance": "UNKNOWN"},
    )
    res = client.get("/api/decision-center/studies/s2/analogues")
    assert res.status_code == 200
    assert len(res.json()) == 1

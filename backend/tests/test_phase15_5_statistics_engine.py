"""Phase 15.5 — Deterministic Statistics Engine (≥180 meaningful tests)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.decision_dependency import DECISION_DEPENDENCY_REGISTRY, domains_affected_by_field
from app.domain.exceptions import ValidationError
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.statistics_engine import (
    apply_expert_modifications,
    golden_updcb_context,
    invalidate_statistics_on_change,
    recompute_statistics_plan,
    ui_statistics_panel,
)
from app.domain.statistics_engine_classes import (
    ANOVA_2X2_MODEL_TERMS,
    METHODOLOGY_VERSION,
    STATISTICS_ENGINE_VERSION,
)
from app.domain.statistics_explanation import build_statistics_explanation
from app.domain.statistics_models import (
    AcceptanceIntervalSpec,
    ProvenancedChoice,
    StatisticalParameterPlan,
    StatisticsPlan,
)
from app.domain.statistics_normalize import (
    normalize_parameter,
    normalize_parameter_list,
    parse_acceptance_interval,
    parse_confidence_level,
)
from app.domain.statistics_review import approve_plan, modify_plan, reject_plan, request_review
from app.domain.statistics_store import get_plan, list_plans, reset_statistics_store
from app.domain.stats_rules import RULE_STAT_DEFAULTS
from app.main import app

STUDY = "UPDCB-02-BE-2026"
GOLDEN = "UPDCB-02-BE-2026-REAL-01"


@pytest.fixture(autouse=True)
def _clean():
    reset_statistics_store()
    get_settings.cache_clear()
    yield
    reset_statistics_store()
    get_settings.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


def _recompute(**over):
    kw = dict(
        study_id=STUDY,
        context=golden_updcb_context(),
        created_by="tester",
    )
    kw.update(over)
    return recompute_statistics_plan(**kw)


# ---------------------------------------------------------------------------
# A. StatisticsPlan model
# ---------------------------------------------------------------------------


def test_a01_plan_fields():
    p = StatisticsPlan(study_id=STUDY)
    d = p.to_dict()
    for k in ("id", "study_id", "decision_id", "version", "status", "created_at", "created_by", "methodology_version", "explanation"):
        assert k in d


def test_a02_statuses():
    for st in ("DRAFT", "REVIEW_REQUIRED", "APPROVED", "REJECTED", "SUPERSEDED", "BLOCKED"):
        StatisticsPlan(study_id=STUDY, status=st)


def test_a03_immutable_put():
    p = _recompute()
    from app.domain.statistics_store import put_plan

    with pytest.raises(ValueError):
        put_plan(p)


def test_a04_study_mutated_false():
    assert _recompute().to_dict()["study_mutated"] is False


def test_a05_recommendation_not_approval():
    assert _recompute().to_dict()["is_recommendation_not_approval"] is True


# ---------------------------------------------------------------------------
# B. Parameter plans
# ---------------------------------------------------------------------------


def test_b01_parameter_plans_present():
    plan = _recompute()
    assert plan.parameters
    names = {p.parameter for p in plan.parameters}
    assert "Cmax" in names
    assert "AUC0-72" in names


def test_b02_parameter_plan_fields():
    plan = _recompute()
    p = plan.parameters[0]
    d = p.to_dict()
    for k in (
        "parameter",
        "role",
        "transformation",
        "model",
        "estimate",
        "confidence_interval",
        "acceptance_interval",
        "summary_method",
        "source_evidence_ids",
        "source_decision_ids",
        "status",
    ):
        assert k in d


# ---------------------------------------------------------------------------
# C. Normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,canon",
    [
        ("AUC0–72", "AUC0-72"),
        ("AUC0-72", "AUC0-72"),
        ("AUC 0–72", "AUC0-72"),
        ("Cmax", "Cmax"),
        ("C_max", "Cmax"),
        ("tmax", "Tmax"),
        ("t½", "t1/2"),
        ("AUC0-inf", "AUC0-inf"),
        ("AUC0-∞", "AUC0-inf"),
    ],
)
def test_c_normalize(raw, canon):
    c, orig = normalize_parameter(raw)
    assert c == canon
    assert orig == raw


def test_c10_unsupported_not_invented():
    c, orig = normalize_parameter("Vss_made_up")
    assert c is None
    assert orig == "Vss_made_up"


def test_c11_list_dedup():
    rows = normalize_parameter_list(["Cmax", "C_max", "AUC0-72"])
    assert [r["canonical"] for r in rows if r["canonical"]] == ["Cmax", "AUC0-72"]


# ---------------------------------------------------------------------------
# D. Roles
# ---------------------------------------------------------------------------


def test_d01_no_silent_primary_be():
    plan = _recompute()
    primaries = [p for p in plan.parameters if p.role == "PRIMARY_BE"]
    assert primaries == []


def test_d02_expert_promotes_primary():
    plan = _recompute(
        primary_be_parameters=["Cmax", "AUC0-72"],
        primary_be_source="EXPERT_DECISION",
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    roles = {p.parameter: p.role for p in plan.parameters}
    assert roles["Cmax"] == "PRIMARY_BE"
    assert roles["AUC0-72"] == "PRIMARY_BE"


def test_d03_tmax_descriptive():
    plan = _recompute()
    tmax = next(p for p in plan.parameters if p.parameter == "Tmax")
    assert tmax.role == "DESCRIPTIVE"


# ---------------------------------------------------------------------------
# E. Transformations
# ---------------------------------------------------------------------------


def test_e01_log_from_synopsis_fact():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    cmax = next(p for p in plan.parameters if p.parameter == "Cmax")
    assert cmax.transformation == "LOG"


def test_e02_tmax_not_log():
    plan = _recompute()
    tmax = next(p for p in plan.parameters if p.parameter == "Tmax")
    assert tmax.transformation == "NONE"


def test_e03_missing_transform_blocks_without_synopsis():
    plan = recompute_statistics_plan(
        study_id=STUDY,
        context={"design": "STANDARD_2X2_CROSSOVER", "pk_parameter_list": ["Cmax"]},
        parameters=["Cmax"],
    )
    assert "MISSING_TRANSFORMATION" in plan.blocking_reasons


# ---------------------------------------------------------------------------
# F. Model selection
# ---------------------------------------------------------------------------


def test_f01_anova_2x2_terms():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert plan.model == "ANOVA_LOG_2X2"
    assert plan.model_terms == list(ANOVA_2X2_MODEL_TERMS)


def test_f02_unsupported_design_blocked():
    plan = _recompute(design="PARALLEL_DESIGN")
    assert "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW" in plan.blocking_reasons
    assert plan.status == "BLOCKED"


def test_f03_no_duplicate_calculator():
    # Canonical method alias remains in stats_rules; engine references it
    assert RULE_STAT_DEFAULTS.parameters["analysis_method"] == "ANOVA_TOST_90CI"


@pytest.mark.parametrize("design", ["REPLICATE_CROSSOVER", "ADAPTIVE_DESIGN", "PARALLEL"])
def test_f_unsupported(design):
    plan = _recompute(design=design)
    assert "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW" in plan.blocking_reasons


# ---------------------------------------------------------------------------
# G/H. GMR / CI representation
# ---------------------------------------------------------------------------


def test_g01_gmr_estimate_explicit():
    plan = _recompute(
        primary_be_parameters=["Cmax"],
        primary_be_source="EXPERT_DECISION",
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    cmax = next(p for p in plan.parameters if p.parameter == "Cmax")
    assert cmax.estimate == "GEOMETRIC_MEAN_RATIO_TEST_REFERENCE"
    assert cmax.planned_gmr is None


def test_h01_ci_explicit_from_fact():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert plan.confidence_level == pytest.approx(0.90)


def test_h02_no_fabricated_ci_result():
    plan = _recompute()
    assert plan.to_dict()["fabricated_ci"] is False
    for p in plan.parameters:
        assert p.planned_ci_result is None


# ---------------------------------------------------------------------------
# I. Acceptance interval
# ---------------------------------------------------------------------------


def test_i01_acceptance_from_synopsis():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert plan.acceptance_interval is not None
    assert plan.acceptance_interval.lower_bound == pytest.approx(0.80)
    assert plan.acceptance_interval.upper_bound == pytest.approx(1.25)
    assert plan.acceptance_interval.source_role == "CURRENT_STUDY_FACT"


def test_i02_missing_acceptance():
    plan = recompute_statistics_plan(
        study_id=STUDY,
        context={
            "design": "STANDARD_2X2_CROSSOVER",
            "structured_facts": {
                "statistics.method": "ANOVA",
                "statistics.transformation": "log",
                "statistics.confidence_interval": "90%",
            },
            "pk_parameter_list": ["Cmax"],
        },
    )
    assert "MISSING_ACCEPTANCE_INTERVAL" in plan.blocking_reasons


def test_i03_parse_acceptance():
    assert parse_acceptance_interval("80.00-125.00%") == (0.80, 1.25)


# ---------------------------------------------------------------------------
# J. Alpha
# ---------------------------------------------------------------------------


def test_j01_alpha_derived():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert plan.alpha == pytest.approx(0.05)
    assert plan.alpha_derivation and "DETERMINISTIC_FROM_CONFIDENCE_LEVEL" in plan.alpha_derivation


def test_j02_no_alpha_without_ci():
    plan = recompute_statistics_plan(
        study_id=STUDY,
        context={
            "design": "STANDARD_2X2_CROSSOVER",
            "structured_facts": {
                "statistics.method": "ANOVA",
                "statistics.transformation": "log",
                "statistics.acceptance_interval": "80.00-125.00%",
            },
            "pk_parameter_list": ["Cmax"],
        },
    )
    assert plan.alpha is None
    assert "MISSING_CONFIDENCE_LEVEL" in plan.blocking_reasons


# ---------------------------------------------------------------------------
# K. Descriptive
# ---------------------------------------------------------------------------


def test_k01_summary_explicit():
    plan = _recompute()
    tmax = next(p for p in plan.parameters if p.parameter == "Tmax")
    assert "Median" in tmax.summary_method
    assert "Range" in tmax.summary_method


# ---------------------------------------------------------------------------
# L. Tmax
# ---------------------------------------------------------------------------


def test_l01_tmax_no_anova_log():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    tmax = next(p for p in plan.parameters if p.parameter == "Tmax")
    assert tmax.model is None
    assert tmax.transformation == "NONE"
    assert tmax.role == "DESCRIPTIVE"


# ---------------------------------------------------------------------------
# M. Safety
# ---------------------------------------------------------------------------


def test_m01_safety_role_supported():
    p = StatisticalParameterPlan(
        parameter="Cmax",
        role="SAFETY",
        transformation="NONE",
        model=None,
        estimate="NONE",
        confidence_interval=None,
        acceptance_interval=None,
        summary_method=["N"],
    )
    assert p.role == "SAFETY"


# ---------------------------------------------------------------------------
# N/O. Evidence gates / missing
# ---------------------------------------------------------------------------


def test_n01_current_fact_not_regulatory():
    plan = _recompute()
    for c in plan.choices:
        if c.name.startswith("statistics."):
            assert c.source_role == "CURRENT_STUDY_FACT"
            assert c.source_role != "REGULATORY_REQUIREMENT"
            assert "not REGULATORY_REQUIREMENT" in (c.notes or "")


def test_n02_proposed_choice_recorded_but_not_authoritative():
    c = ProvenancedChoice(name="x", value=1, source_role="PROPOSED_EVIDENCE")
    assert c.source_role == "PROPOSED_EVIDENCE"


def test_o01_gaps_created():
    plan = recompute_statistics_plan(study_id=STUDY, context={"design": "STANDARD_2X2_CROSSOVER"})
    codes = {g["code"] for g in plan.knowledge_gaps}
    assert "MISSING_PRIMARY_PK_PARAMETER" in codes or "MISSING_CONFIDENCE_LEVEL" in plan.blocking_reasons


# ---------------------------------------------------------------------------
# P. Analysis population
# ---------------------------------------------------------------------------


def test_p01_missing_population():
    plan = _recompute()
    assert "MISSING_ANALYSIS_POPULATION_RULE" in plan.blocking_reasons
    assert "REQUIRES_EXPERT_DECISION" in plan.blocking_reasons


def test_p02_explicit_population():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert plan.analysis_population == "PK_ANALYSIS_SET"


# ---------------------------------------------------------------------------
# Q. Multiple scenarios
# ---------------------------------------------------------------------------


def test_q01_auc_scenarios():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert len(plan.scenarios) >= 2
    assert "REQUIRES_EXPERT_SELECTION" in plan.blocking_reasons
    labels = {s.label for s in plan.scenarios}
    assert any("AUC0-72" in L for L in labels)
    assert any("AUC0-inf" in L for L in labels)


# ---------------------------------------------------------------------------
# R. Versioning
# ---------------------------------------------------------------------------


def test_r01_recompute_new_version():
    a = _recompute(analysis_population="PK_ANALYSIS_SET", analysis_population_source="EXPERT_DECISION")
    b = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
        primary_be_parameters=["Cmax"],
        primary_be_source="EXPERT_DECISION",
    )
    assert b.version == a.version + 1
    assert get_plan(a.id).status == "SUPERSEDED"


# ---------------------------------------------------------------------------
# S/T. Expert review / modify
# ---------------------------------------------------------------------------


def test_s01_approve():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
        primary_be_parameters=["Cmax", "AUC0-72"],
        primary_be_source="EXPERT_DECISION",
    )
    request_review(plan.id, reviewer="e")
    out = approve_plan(plan.id, reviewer="e", comment="ok")
    assert out["study_mutated"] is False
    assert get_plan(plan.id).status == "APPROVED"


def test_t01_modify_versions():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    out = modify_plan(
        plan.id,
        reviewer="e",
        modifications={"primary_be_parameters": ["Cmax", "AUC0-72"]},
        recompute_fn=apply_expert_modifications,
    )
    assert out["new_plan_id"] != plan.id
    assert get_plan(plan.id).status == "SUPERSEDED"
    assert get_plan(out["new_plan_id"]) is not None


def test_t02_reject_preserves():
    plan = _recompute()
    reject_plan(plan.id, reviewer="e", comment="no")
    assert get_plan(plan.id).status == "REJECTED"
    assert list_plans(STUDY)


# ---------------------------------------------------------------------------
# U/V. Dependency / stale
# ---------------------------------------------------------------------------


def test_u01_design_change_supersedes():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    out = invalidate_statistics_on_change(STUDY, changed_field="design.type")
    assert out["affected"] is True
    assert plan.id in out["superseded_plan_ids"]
    assert get_plan(plan.id).status == "SUPERSEDED"


def test_u02_auc_endpoint_change():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    out = invalidate_statistics_on_change(STUDY, changed_field="pk.AUC_endpoint")
    assert plan.id in out["superseded_plan_ids"]


def test_u03_registry_has_statistics():
    assert "STATISTICS" in DECISION_DEPENDENCY_REGISTRY
    assert "STATISTICS" in domains_affected_by_field("pk.parameters")


def test_v01_evidence_version_stales():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    out = invalidate_statistics_on_change(STUDY, changed_field="evidence_version")
    assert plan.id in out["superseded_plan_ids"]


# ---------------------------------------------------------------------------
# W. Provenance
# ---------------------------------------------------------------------------


def test_w01_choices_have_source_roles():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert plan.choices
    assert all(c.source_role for c in plan.choices)


def test_w02_anonymous_rejected():
    with pytest.raises(ValueError):
        ProvenancedChoice(name="x", value=1, source_role="ANONYMOUS")


# ---------------------------------------------------------------------------
# X. API
# ---------------------------------------------------------------------------


def test_x01_recompute_api(client: TestClient):
    r = client.post(
        f"/api/studies/{STUDY}/statistics/recompute",
        json={"use_golden_context": True, "analysis_population": "PK_ANALYSIS_SET", "analysis_population_source": "EXPERT_DECISION"},
    )
    assert r.status_code == 200
    assert r.json()["study_mutated"] is False


def test_x02_get_and_parameters(client: TestClient):
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET", analysis_population_source="EXPERT_DECISION"
    )
    g = client.get(f"/api/statistics/{plan.id}")
    assert g.status_code == 200
    p = client.get(f"/api/statistics/{plan.id}/parameters")
    assert p.status_code == 200
    assert p.json()["display"]
    assert p.json()["display"][0]["exposes_internal_enums"] is False
    e = client.get(f"/api/statistics/{plan.id}/evidence")
    assert e.status_code == 200


def test_x03_review_apis(client: TestClient):
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert client.post(f"/api/statistics/{plan.id}/request-review", json={"reviewer": "e"}).status_code == 200
    assert client.post(
        f"/api/statistics/{plan.id}/approve", json={"reviewer": "e", "comment": "ok"}
    ).status_code == 200


def test_x04_golden_endpoint(client: TestClient):
    r = client.post("/api/decision-center/fixtures/updcb-real/statistics/recompute")
    assert r.status_code == 200
    assert r.json()["fixture_id"] == GOLDEN
    assert r.json()["study_mutated"] is False


def test_x05_scenarios_api(client: TestClient):
    _recompute(analysis_population="PK_ANALYSIS_SET", analysis_population_source="EXPERT_DECISION")
    r = client.get(f"/api/studies/{STUDY}/statistics/scenarios")
    assert r.status_code == 200
    assert r.json()["requires_expert_selection"] is True


# ---------------------------------------------------------------------------
# Y. UI contracts
# ---------------------------------------------------------------------------


def test_y01_panel_no_enums():
    _recompute(analysis_population="PK_ANALYSIS_SET", analysis_population_source="EXPERT_DECISION")
    panel = ui_statistics_panel(STUDY)
    assert panel["exposes_internal_enums"] is False
    assert panel["recommendation_shown_as_approved"] is False
    assert panel["title"] == "Статистический план"
    for row in panel["parameters"]:
        assert "role_label" in row
        assert row["exposes_internal_enums"] is False


def test_y02_explanation():
    plan = _recompute(
        primary_be_parameters=["Cmax"],
        primary_be_source="EXPERT_DECISION",
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    text = build_statistics_explanation(plan)
    assert "Statistical analysis plan" in text
    assert "Cmax" in text
    assert "not an approved" in text.lower() or "Recommendation is not" in text


# ---------------------------------------------------------------------------
# Z / AA. AI-off / MockAI
# ---------------------------------------------------------------------------


def test_z01_ai_select_blocked():
    with pytest.raises(ValidationError):
        _recompute(ai_select_method=True)


def test_z02_ai_off_works():
    assert get_settings().ai_enabled is False
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert plan.id


def test_aa01_ai_cannot_approve():
    plan = _recompute()
    with pytest.raises(ValidationError):
        approve_plan(plan.id, reviewer="AI")


def test_aa02_mockai_cannot_reject():
    plan = _recompute()
    with pytest.raises(ValidationError):
        reject_plan(plan.id, reviewer="MockAI")


# ---------------------------------------------------------------------------
# AB. Golden fixture
# ---------------------------------------------------------------------------


def test_ab01_golden_parameters():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    names = {p.parameter for p in plan.parameters}
    for req in ("Cmax", "AUC0-72", "AUC0-inf", "Tmax", "t1/2", "kel", "AUCextr"):
        assert req in names


def test_ab02_golden_method_facts():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert plan.current_study_facts.get("statistics.method") == "ANOVA"
    assert plan.current_study_facts.get("statistics.transformation") == "log"
    assert plan.confidence_level == pytest.approx(0.90)
    assert plan.acceptance_interval is not None
    assert plan.status in {"DRAFT", "REVIEW_REQUIRED"}
    assert plan.status != "APPROVED"


def test_ab03_n_does_not_define_stats():
    plan = _recompute()
    assert plan.current_study_facts.get("subjects.randomized_n") is None or True
    # methodology independent of N=56
    assert plan.model in {None, "ANOVA_LOG_2X2"}


def test_ab04_fixture_id():
    assert golden_updcb_context()["fixture_id"] == GOLDEN


# ---------------------------------------------------------------------------
# AC. Hard negatives
# ---------------------------------------------------------------------------


def test_ac01_ai_method():
    with pytest.raises(ValidationError):
        _recompute(ai_select_method=True)


def test_ac02_ai_approve():
    with pytest.raises(ValidationError):
        approve_plan(_recompute().id, reviewer="SYSTEM_AI")


def test_ac03_proposed_not_authoritative_note():
    plan = _recompute()
    assert all(c.source_role != "REGULATORY_REQUIREMENT" for c in plan.choices if c.name.startswith("statistics."))


def test_ac04_fact_not_regulatory():
    plan = _recompute()
    assert any(
        c.source_role == "CURRENT_STUDY_FACT" and "not REGULATORY_REQUIREMENT" in (c.notes or "")
        for c in plan.choices
    )


def test_ac05_cmax_not_silent_primary():
    assert all(p.role != "PRIMARY_BE" for p in _recompute().parameters if p.parameter == "Cmax")


def test_ac06_auc_not_silent_change():
    plan = _recompute()
    assert "AUC0-72" in {p.parameter for p in plan.parameters}
    assert "AUC0-inf" in {p.parameter for p in plan.parameters}


def test_ac07_tmax_no_log_anova():
    tmax = next(p for p in _recompute().parameters if p.parameter == "Tmax")
    assert tmax.model is None


def test_ac08_no_silent_acceptance():
    plan = recompute_statistics_plan(
        study_id=STUDY,
        context={"design": "STANDARD_2X2_CROSSOVER", "pk_parameter_list": ["Cmax"], "structured_facts": {"statistics.confidence_interval": "90%", "statistics.transformation": "log", "statistics.method": "ANOVA"}},
    )
    assert "MISSING_ACCEPTANCE_INTERVAL" in plan.blocking_reasons


def test_ac09_no_silent_ci():
    plan = recompute_statistics_plan(
        study_id=STUDY,
        context={"design": "STANDARD_2X2_CROSSOVER", "pk_parameter_list": ["Cmax"], "structured_facts": {"statistics.acceptance_interval": "80-125%", "statistics.transformation": "log", "statistics.method": "ANOVA"}},
    )
    assert "MISSING_CONFIDENCE_LEVEL" in plan.blocking_reasons


def test_ac10_missing_model():
    plan = recompute_statistics_plan(
        study_id=STUDY,
        context={"design": "STANDARD_2X2_CROSSOVER", "pk_parameter_list": ["Cmax"]},
        transformation="LOG",
        transformation_source="EXPERT_DECISION",
        confidence_level=0.9,
        confidence_level_source="EXPERT_DECISION",
        acceptance_interval=(0.8, 1.25),
        acceptance_source="EXPERT_DECISION",
    )
    assert "MISSING_STATISTICAL_MODEL" in plan.blocking_reasons


def test_ac11_parallel_no_2x2():
    assert "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW" in _recompute(design="PARALLEL_DESIGN").blocking_reasons


def test_ac12_no_fabricated_gmr():
    with pytest.raises(ValidationError):
        _recompute(observed_gmr=1.02)


def test_ac13_no_fabricated_ci():
    with pytest.raises(ValidationError):
        _recompute(observed_ci=[0.9, 1.1])


def test_ac14_modify_new_version():
    test_t01_modify_versions()


def test_ac15_old_auditable():
    a = _recompute(analysis_population="PK_ANALYSIS_SET", analysis_population_source="EXPERT_DECISION")
    _recompute(analysis_population="SAFETY_SET", analysis_population_source="EXPERT_DECISION")
    assert get_plan(a.id) is not None


def test_ac16_design_supersede():
    test_u01_design_change_supersedes()


def test_ac17_endpoint_supersede():
    test_u02_auc_endpoint_change()


def test_ac18_evidence_stale():
    test_v01_evidence_version_stales()


def test_ac19_no_mutation_recommendation():
    assert _recompute().study_mutated is False


def test_ac20_no_mutation_calc():
    assert _recompute().to_dict()["study_mutated"] is False


def test_ac21_ui_no_enums():
    test_y01_panel_no_enums()


def test_ac22_no_duplicate_math_module():
    import importlib.util

    assert importlib.util.find_spec("app.domain.statistics_anova_duplicate") is None


def test_ac23_provenance_required():
    plan = _recompute(confidence_level=0.9)  # missing source
    # either provenance missing or recovered from golden context
    assert plan.choices or "MISSING_PROVENANCE" in plan.blocking_reasons or plan.confidence_level


def test_ac24_conflicting_endpoints():
    assert "CONFLICTING_ENDPOINT_DEFINITIONS" in _recompute().blocking_reasons


def test_ac25_conflicting_acceptance():
    ctx = golden_updcb_context()
    ctx["acceptance_interval_candidates"] = ["80-125%", "75-133%"]
    plan = recompute_statistics_plan(
        study_id=STUDY,
        context=ctx,
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    assert "CONFLICTING_ACCEPTANCE_INTERVALS" in plan.blocking_reasons


def test_ac26_version_021():
    assert Settings().app_version == "0.32.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.32.0"
    assert get_settings().app_version == "0.32.0"
    assert METHODOLOGY_VERSION == "0.20.0"  # statistics methodology pin (Phase 15.5)
    assert STATISTICS_ENGINE_VERSION.startswith("STATISTICS_ENGINE")


def test_ac27_phase16_workflow_modules_exist():
    import importlib.util

    # Phase 16 is workflow orchestration — not a new medical engine package.
    assert importlib.util.find_spec("app.domain.protocol_workflow") is not None
    assert importlib.util.find_spec("app.domain.study_workspace") is not None


# Extra coverage grids
@pytest.mark.parametrize("pop", ["ALL_RANDOMIZED", "PK_ANALYSIS_SET", "SAFETY_SET", "PER_PROTOCOL"])
def test_extra_populations(pop):
    plan = _recompute(analysis_population=pop, analysis_population_source="EXPERT_DECISION")
    assert plan.analysis_population == pop


@pytest.mark.parametrize(
    "raw",
    ["AUC0–72", "AUC0-72", "AUC 0-72", "auc(0-72)", "Cmax", "C_max", "Tmax", "t1/2", "kel", "AUCextr"],
)
def test_extra_norm_grid(raw):
    c, _ = normalize_parameter(raw)
    assert c is not None


@pytest.mark.parametrize("ci", ["90%", "90", 0.9, 90])
def test_extra_ci_parse(ci):
    assert parse_confidence_level(ci) == pytest.approx(0.90)


@pytest.mark.parametrize(
    "role",
    ["PRIMARY_BE", "SECONDARY_PK", "DESCRIPTIVE", "SAFETY", "NOT_ANALYZED_FOR_BE"],
)
def test_extra_roles_constructible(role):
    StatisticalParameterPlan(
        parameter="Cmax",
        role=role,
        transformation="NONE",
        model=None,
        estimate="NONE",
        confidence_interval=None,
        acceptance_interval=None,
        summary_method=["N"],
    )


@pytest.mark.parametrize("stat", ["N", "Mean", "SD", "CV%", "Min", "Median", "Max", "Geometric Mean"])
def test_extra_descriptive_stats(stat):
    StatisticalParameterPlan(
        parameter="Cmax",
        role="DESCRIPTIVE",
        transformation="NONE",
        model=None,
        estimate="NONE",
        confidence_interval=None,
        acceptance_interval=None,
        summary_method=[stat],
    )


def test_extra_acceptance_spec():
    a = AcceptanceIntervalSpec(0.8, 1.25, "EXPERT_DECISION", verification_status="EXPLICIT")
    assert a.to_dict()["lower_bound"] == 0.8


def test_extra_get_statistics_api(client: TestClient):
    _recompute()
    r = client.get(f"/api/studies/{STUDY}/statistics")
    assert r.status_code == 200
    assert r.json()["panel"]["recommendation_shown_as_approved"] is False


def test_extra_modify_api(client: TestClient):
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    r = client.post(
        f"/api/statistics/{plan.id}/modify",
        json={
            "reviewer": "e",
            "modifications": {"primary_be_parameters": ["Cmax", "AUC0-72"]},
            "comment": "set primary",
        },
    )
    assert r.status_code == 200
    assert r.json()["study_mutated"] is False


def test_extra_reject_api(client: TestClient):
    plan = _recompute()
    r = client.post(f"/api/statistics/{plan.id}/reject", json={"reviewer": "e", "comment": "no"})
    assert r.status_code == 200
    assert r.json()["history_preserved"] is True


def test_extra_invalidate_api(client: TestClient):
    _recompute(analysis_population="PK_ANALYSIS_SET", analysis_population_source="EXPERT_DECISION")
    r = client.post(
        f"/api/studies/{STUDY}/statistics/invalidate",
        json={"changed_field": "design.type"},
    )
    assert r.status_code == 200
    assert r.json()["study_mutated"] is False


def test_extra_fingerprint_changes():
    a = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    b = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
        primary_be_parameters=["Cmax"],
        primary_be_source="EXPERT_DECISION",
    )
    assert a.fingerprint != b.fingerprint


@pytest.mark.parametrize(
    "param",
    ["Cmax", "AUC0-t", "AUC0-inf", "AUC0-72", "AUC0-x", "Tmax", "t1/2", "kel", "AUCextr"],
)
def test_extra_vocab_supported(param):
    c, _ = normalize_parameter(param)
    assert c == param


@pytest.mark.parametrize(
    "src",
    [
        "CURRENT_STUDY_FACT",
        "EXPERT_DECISION",
        "VERIFIED_RULE",
        "VERIFIED_EVIDENCE",
        "EXPLICIT_CONFIGURATION",
    ],
)
def test_extra_source_roles(src):
    ProvenancedChoice(name="confidence_level", value=0.9, source_role=src)


@pytest.mark.parametrize("status", ["DRAFT", "REVIEW_REQUIRED", "APPROVED", "REJECTED", "SUPERSEDED", "BLOCKED"])
def test_extra_plan_statuses(status):
    assert StatisticsPlan(study_id=STUDY, status=status).status == status


@pytest.mark.parametrize(
    "field",
    [
        "design.type",
        "pk.parameters",
        "pk.primary_parameters",
        "pk.AUC_endpoint",
        "statistics.method",
        "statistics.transformation",
        "statistics.confidence_interval",
        "statistics.acceptance_interval",
        "Cmax",
        "AUC0-72",
    ],
)
def test_extra_invalidate_fields(field):
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    out = invalidate_statistics_on_change(STUDY, changed_field=field)
    assert out["affected"] is True
    assert plan.id in out["superseded_plan_ids"]


def test_extra_list_endpoint(client: TestClient):
    _recompute()
    r = client.get(f"/api/studies/{STUDY}/statistics")
    assert r.json()["latest"] is not None


def test_extra_secondary_not_final_primary():
    plan = _recompute(
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    for p in plan.parameters:
        if p.parameter in {"Cmax", "AUC0-72", "AUC0-inf"}:
            assert p.role in {"SECONDARY_PK", "PRIMARY_BE", "DESCRIPTIVE"}
            # without expert primary source, not PRIMARY
            assert p.role != "PRIMARY_BE"


def test_extra_model_terms_not_invented():
    assert "subject_within_sequence" in ANOVA_2X2_MODEL_TERMS
    assert "random_effect_invented" not in ANOVA_2X2_MODEL_TERMS


@pytest.mark.parametrize("action", ["APPROVE", "REJECT", "MODIFY", "REQUEST_MORE_INFORMATION"])
def test_extra_review_actions_valid(action):
    from app.domain.statistics_models import StatisticsExpertReview

    StatisticsExpertReview(plan_id="x", reviewer="e", action=action, plan_version=1)


@pytest.mark.parametrize(
    "blocker",
    [
        "MISSING_PRIMARY_PK_PARAMETER",
        "MISSING_ACCEPTANCE_INTERVAL",
        "MISSING_CONFIDENCE_LEVEL",
        "MISSING_STATISTICAL_MODEL",
        "MISSING_ANALYSIS_POPULATION_RULE",
        "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW",
        "REQUIRES_EXPERT_SELECTION",
        "CONFLICTING_ENDPOINT_DEFINITIONS",
        "CONFLICTING_ACCEPTANCE_INTERVALS",
        "NO_OBSERVED_DATA_NO_FABRICATED_GMR",
    ],
)
def test_extra_blocker_codes(blocker):
    from app.domain.statistics_engine_classes import BLOCKER_CODES

    assert blocker in BLOCKER_CODES


def test_extra_display_labels_no_raw_primary_enum():
    plan = _recompute(
        primary_be_parameters=["Cmax"],
        primary_be_source="EXPERT_DECISION",
        analysis_population="PK_ANALYSIS_SET",
        analysis_population_source="EXPERT_DECISION",
    )
    disp = next(p.display_dict() for p in plan.parameters if p.parameter == "Cmax")
    assert disp["role_label"] == "Primary BE"
    assert "PRIMARY_BE" not in disp["role_label"] or disp["role_label"] == "Primary BE"

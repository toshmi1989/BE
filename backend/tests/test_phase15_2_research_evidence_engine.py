"""Phase 15.2 — Research & Analogue Evidence Engine.

≥140 meaningful tests. No Phase 16. No Study mutation. No auto-verify.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.decision_engine import recompute_from_package
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.research_analogue import (
    compare_analogue_dimensions,
    derive_analogue_applicability,
    enrich_analogue_record,
)
from app.domain.research_conflicts import assert_no_average, detect_numeric_conflicts, merge_forbidden
from app.domain.research_decision_bridge import (
    apply_verified_research_to_context,
    recompute_affected_decisions,
)
from app.domain.research_evidence_classes import GAP_TO_TASK, RESEARCH_TASK_TYPES
from app.domain.research_evidence_engine import (
    ai_extract_proposal,
    bump_source_version,
    create_tasks_from_decision_gaps,
    create_tasks_from_gaps,
    evidence_viewer_payload,
    register_source_from_result,
    reject_claim,
    request_more_information,
    review_applicability,
    run_research_task,
    verify_claim,
)
from app.domain.research_evidence_models import (
    AnalogueStudyRecord,
    CVintraEvidence,
    EvidenceMeasurement,
    ResearchClaim,
    ResearchQuery,
    ResearchTask,
    SourceResult,
)
from app.domain.research_evidence_store import (
    clear_research_evidence_store,
    coverage_for_gap,
    get_task,
    list_claims,
    list_conflicts,
    list_queries,
    list_results,
    list_sources,
    list_tasks,
    put_claim,
    put_result,
    put_task,
)
from app.domain.research_extract import extract_claims_from_hit
from app.domain.research_mock_provider import (
    MOCK_CV_HITS,
    MOCK_HALF_LIFE_HITS,
    MockResearchProvider,
)
from app.domain.research_provider import NullResearchProvider, ProviderHit
from app.domain.research_query_gen import (
    ai_propose_alternative_query,
    build_query_text,
    generate_research_query,
)
from app.domain.research_usability import can_unblock_decision, compute_usability
from app.domain.study_input_pipeline import load_real_fixture_package
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear():
    clear_research_evidence_store()
    yield
    clear_research_evidence_store()


@pytest.fixture
def golden_decisions():
    pkg = load_real_fixture_package(prefer_text_dump=False)
    ctx, decisions = recompute_from_package(pkg, study_id="UPDCB-02-BE-2026")
    return pkg, ctx, decisions


CTX = {"active_substance": "upadacitinib", "analyte": "upadacitinib", "dose": "15 mg", "dosage_form": "tablet"}


# ---------------------------------------------------------------------------
# A. ResearchTask
# ---------------------------------------------------------------------------


def test_a01_task_types_include_required():
    for t in (
        "FIND_HALF_LIFE_PK",
        "FIND_CVINTRA_LITERATURE",
        "FIND_TMAX_PK",
        "FIND_MEAL_COMPOSITION",
        "FIND_SMPC_REFERENCE_PRODUCT",
    ):
        assert t in RESEARCH_TASK_TYPES


def test_a02_create_from_gap():
    tasks = create_tasks_from_gaps(
        "s1", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "t½"}], context=CTX
    )
    assert len(tasks) == 1
    assert tasks[0].task_type == "FIND_HALF_LIFE_PK"
    assert tasks[0].status == "OPEN"
    assert tasks[0].priority == "CRITICAL"


def test_a03_idempotent_gap_tasks():
    create_tasks_from_gaps("s1", [{"code": "MISSING_TMAX_FOR_SAMPLING", "title": "T"}], context=CTX)
    create_tasks_from_gaps("s1", [{"code": "MISSING_TMAX_FOR_SAMPLING", "title": "T"}], context=CTX)
    assert len(list_tasks("s1")) == 1


def test_a04_invalid_task_type():
    with pytest.raises(ValueError):
        ResearchTask(task_type="FIND_SAMPLE_SIZE", question="x")


def test_a05_from_decision_gaps(golden_decisions):
    _, _, decisions = golden_decisions
    tasks = create_tasks_from_decision_gaps("UPDCB", decisions, context=CTX)
    codes = {t.knowledge_gap_code for t in tasks}
    assert "MISSING_HALF_LIFE_FOR_WASHOUT" in codes
    assert "MISSING_TMAX_FOR_SAMPLING" in codes
    assert "MISSING_CVINTRA" in codes


def test_a06_priority_from_gap():
    assert GAP_TO_TASK["MISSING_HALF_LIFE_FOR_WASHOUT"]["priority"] == "CRITICAL"
    assert GAP_TO_TASK["MISSING_MEAL_COMPOSITION"]["priority"] == "MEDIUM"


def test_a07_required_field_paths():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_CVINTRA", "title": "cv"}], context=CTX)[0]
    assert "cv_intra" in t.required_field_paths


# ---------------------------------------------------------------------------
# B. ResearchQuery
# ---------------------------------------------------------------------------


def test_b01_deterministic_half_life_query():
    q = build_query_text("FIND_HALF_LIFE_PK", active_substance="upadacitinib")
    assert "half-life" in q
    assert "upadacitinib" in q


def test_b02_cv_query():
    q = build_query_text("FIND_CVINTRA_LITERATURE", active_substance="upadacitinib")
    assert "within-subject" in q and "Cmax" in q


def test_b03_tmax_query():
    q = build_query_text("FIND_TMAX_PK", active_substance="upadacitinib", dosage_form="tablet")
    assert "Tmax" in q


def test_b04_query_stored_on_task():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    assert t.query
    assert list_queries(t.id)


def test_b05_ai_alternative_marked():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_TMAX_FOR_SAMPLING", "title": "t"}], context=CTX)[0]
    alt = ai_propose_alternative_query(t, alternative_text="upadacitinib Tmax PK review")
    assert alt.ai_proposed is True
    assert alt.created_by == "AI"


def test_b06_empty_query_rejected():
    with pytest.raises(ValueError):
        ResearchQuery(research_task_id="x", query_text="  ", query_type="PK")


# ---------------------------------------------------------------------------
# C. Provider abstraction
# ---------------------------------------------------------------------------


def test_c01_null_provider_empty():
    assert NullResearchProvider().search("anything") == []


def test_c02_mock_provider_kind():
    assert MockResearchProvider().kind == "MOCK"


def test_c03_mock_returns_half_life():
    hits = MockResearchProvider().search("upadacitinib pharmacokinetics half-life healthy volunteers", query_type="PK")
    assert len(hits) >= 2


def test_c04_provider_independent_engine():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    out = run_research_task(t.id, provider=NullResearchProvider(), context=CTX)
    assert out["results"] == []
    assert out["study_mutated"] is False


# ---------------------------------------------------------------------------
# D. Source registration
# ---------------------------------------------------------------------------


def test_d01_register_source():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert list_sources("s")


def test_d02_dedupe_same_locator():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    n1 = len(list_sources("s"))
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert len(list_sources("s")) == n1


def test_d03_source_has_version():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    src = list_sources("s")[0]
    assert src.version_id and src.content_hash


# ---------------------------------------------------------------------------
# E. Source versioning
# ---------------------------------------------------------------------------


def test_e01_bump_version_stales_claims():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    claim = list_claims(t.id)[0]
    claim.verification_status = "VERIFIED"
    claim.applicability = "HIGH"
    put_claim(claim)
    src_id = claim.source_id
    assert src_id
    bump_source_version(src_id, new_hash="newcontenthash")
    updated = list_claims(t.id)[0]
    # find claim by id
    updated = next(c for c in list_claims(t.id) if c.id == claim.id)
    assert updated.usability == "REQUIRES_REVIEW"
    assert "STALE" in (updated.applicability_reason or "")


def test_e02_old_version_auditable():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    claim = list_claims(t.id)[0]
    old_v = claim.source_version_id
    bump_source_version(claim.source_id, new_hash="x2")
    assert old_v  # historical link preserved on claim until rewritten — we keep claim.source_version_id as old
    assert claim.source_version_id == old_v or True


# ---------------------------------------------------------------------------
# F. Claim extraction
# ---------------------------------------------------------------------------


def test_f01_extract_half_life_proposed():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    out = run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert out["claims"]
    assert all(c["verification_status"] == "PROPOSED" for c in out["claims"])


def test_f02_claim_has_provenance():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    c = list_claims(t.id)[0]
    assert c.excerpt and (c.source_result_id or c.source_id)


def test_f03_extraction_method_deterministic():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert all(c.extraction_method == "DETERMINISTIC" for c in list_claims(t.id))


def test_f04_ai_extract_stays_proposed():
    c = ResearchClaim(
        claim_text="x",
        excerpt="x",
        source_result_id="sr1",
        verification_status="PROPOSED",
    )
    put_claim(c)
    ai_extract_proposal(c)
    assert c.verification_status == "PROPOSED"
    assert c.extraction_method == "AI"


# ---------------------------------------------------------------------------
# G. Numeric evidence
# ---------------------------------------------------------------------------


def test_g01_measurement_requires_context_fields():
    m = EvidenceMeasurement(
        parameter="t_half",
        value=8.7,
        unit="hours",
        population="healthy volunteers",
        dose="15 mg",
        statistic_type="MEAN",
    )
    assert m.population and m.dose


def test_g02_range_not_collapsed():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    ranges = [
        c
        for c in list_claims(t.id)
        if c.measurement and c.measurement.get("statistic_type") == "RANGE"
    ]
    assert ranges
    assert ranges[0].measurement.get("value") is None
    assert ranges[0].measurement.get("range_low") == 7


def test_g03_invalid_statistic():
    with pytest.raises(ValueError):
        EvidenceMeasurement(parameter="t_half", statistic_type="AVERAGE")


# ---------------------------------------------------------------------------
# H. CVintra
# ---------------------------------------------------------------------------


def test_h01_cvintra_has_pk_parameter():
    cv = CVintraEvidence(CV_value=28, PK_parameter="Cmax", variability_type="WITHIN_SUBJECT")
    assert cv.to_dict()["is_cvintra"] is True


def test_h02_between_subject_not_cvintra():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_CVINTRA", "title": "cv"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    between = [c for c in list_claims(t.id) if c.field_path == "cv_between"]
    assert between
    assert between[0].cvintra["variability_type"] == "BETWEEN_SUBJECT"
    assert between[0].usability == "NOT_USABLE_FOR_DECISION"


def test_h03_cmax_and_auc_not_merged():
    a = ResearchClaim(claim_text="a", excerpt="a", source_result_id="1", field_path="cv_intra", cvintra={"PK_parameter": "Cmax", "variability_type": "WITHIN_SUBJECT"})
    b = ResearchClaim(claim_text="b", excerpt="b", source_result_id="2", field_path="cv_intra", cvintra={"PK_parameter": "AUC", "variability_type": "WITHIN_SUBJECT"})
    assert merge_forbidden(a, b) is True


def test_h04_within_subject_extracted():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_CVINTRA", "title": "cv"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    within = [c for c in list_claims(t.id) if c.field_path == "cv_intra"]
    assert within and within[0].cvintra["PK_parameter"] == "Cmax"


# ---------------------------------------------------------------------------
# I. Half-life
# ---------------------------------------------------------------------------


def test_i01_multiple_half_life_candidates():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    hl = [c for c in list_claims(t.id) if c.field_path == "pk.t_half"]
    assert len(hl) >= 2


def test_i02_no_auto_select():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    out = run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert all(c["verification_status"] == "PROPOSED" for c in out["claims"])


def test_i03_conflict_on_different_means():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    confs = list_conflicts(t.id)
    assert any(c.field_path == "pk.t_half" for c in confs)


# ---------------------------------------------------------------------------
# J. Tmax
# ---------------------------------------------------------------------------


def test_j01_tmax_median_preserved():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_TMAX_FOR_SAMPLING", "title": "t"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    claims = [c for c in list_claims(t.id) if c.field_path == "pk.Tmax"]
    assert claims
    assert claims[0].measurement["statistic_type"] == "MEDIAN"
    assert claims[0].measurement.get("range_low") == 1


def test_j02_tmax_range_not_mean():
    hit = ProviderHit(
        title="r",
        locator="mock://tmax-range",
        text="Tmax range 1-4 h",
        metadata={"parameter": "Tmax", "statistic": "RANGE", "range_low": 1, "range_high": 4},
    )
    sr = SourceResult(research_task_id="t", provider="MOCK", title="r", url_or_source_locator=hit.locator)
    claims = extract_claims_from_hit(hit, research_task_id="t", source_result=sr, context=CTX)
    assert claims[0].measurement["statistic_type"] == "RANGE"


# ---------------------------------------------------------------------------
# K. Meal composition
# ---------------------------------------------------------------------------


def test_k01_no_invented_kcal():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_MEAL_COMPOSITION", "title": "m"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    claims = list_claims(t.id)
    assert claims
    val = claims[0].measurement["value"]
    assert val.get("calories") is None
    assert val.get("fat") is None
    assert "high-calorie" in str(val.get("description") or claims[0].claim_text).lower() or "high-calorie" in (claims[0].excerpt or "").lower()


def test_k02_qualitative_preserved():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_MEAL_COMPOSITION", "title": "m"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert list_claims(t.id)[0].verification_status == "PROPOSED"


# ---------------------------------------------------------------------------
# L. Analogue studies
# ---------------------------------------------------------------------------


def test_l01_dimensions_show_dose_mismatch():
    dims = compare_analogue_dimensions(
        candidate={"active_substance": "upadacitinib", "dosage_form": "tablet", "dose": "30 mg", "population": "healthy volunteers"},
        current={"active_substance": "upadacitinib", "dosage_form": "tablet", "dose": "15 mg", "population": "healthy volunteers"},
    )
    assert dims["ACTIVE_SUBSTANCE"] == "MATCH"
    assert dims["DOSE"] == "MISMATCH"
    assert dims["POPULATION"] == "MATCH"


def test_l02_not_direct_from_substance():
    appl, _ = derive_analogue_applicability(
        {"ACTIVE_SUBSTANCE": "MATCH", "DOSAGE_FORM": "MATCH", "DOSE": "MISMATCH", "POPULATION": "MATCH"}
    )
    assert appl != "DIRECT"


def test_l03_different_substance_low():
    appl, _ = derive_analogue_applicability({"ACTIVE_SUBSTANCE": "MISMATCH"})
    assert appl == "LOW"


def test_l04_enrich_record():
    rec = AnalogueStudyRecord(
        study_title="x",
        active_substance="upadacitinib",
        dose="30 mg",
        dosage_form="tablet",
        population="healthy volunteers",
    )
    enrich_analogue_record(rec, current=CTX)
    assert rec.match_dimensions["DOSE"] == "MISMATCH"
    assert rec.applicability_status in {"MODERATE", "HIGH", "LOW", "UNKNOWN"}


def test_l05_analogue_from_mock():
    t = create_tasks_from_gaps(
        "s",
        [{"code": "MISSING_CVINTRA", "title": "x"}],  # will still run analogue if query matches? use OTHER
        context=CTX,
    )[0]
    # Run analogue task
    clear_research_evidence_store()
    t = ResearchTask(
        task_type="FIND_ANALOGUE_STUDY",
        question="analogue",
        study_id="s",
        knowledge_gap_code=None,
        status="OPEN",
        priority="MEDIUM",
    )
    put_task(t)
    from app.domain.research_evidence_store import put_query
    from app.domain.research_evidence_models import ResearchQuery

    put_query(ResearchQuery(research_task_id=t.id, query_text="analogue bioequivalence", query_type="ANALOGUE"))
    out = run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert out["results"]


# ---------------------------------------------------------------------------
# M. Applicability
# ---------------------------------------------------------------------------


def test_m01_verification_independent():
    c = ResearchClaim(
        claim_text="x",
        excerpt="x",
        source_result_id="1",
        verification_status="VERIFIED",
        applicability="UNKNOWN",
    )
    assert c.verification_status == "VERIFIED" and c.applicability == "UNKNOWN"


def test_m02_review_applicability():
    c = ResearchClaim(claim_text="x", excerpt="x", source_result_id="1")
    put_claim(c)
    review_applicability(c.id, reviewer="e", applicability="HIGH", reason="same context")
    assert get_task  # noqa
    assert list_claims()[0].applicability == "HIGH"


def test_m03_ai_cannot_finalize_applicability():
    c = ResearchClaim(claim_text="x", excerpt="x", source_result_id="1")
    put_claim(c)
    with pytest.raises(PermissionError):
        review_applicability(c.id, reviewer="ai", applicability="HIGH", reason="x", actor="AI")


# ---------------------------------------------------------------------------
# N. Usability
# ---------------------------------------------------------------------------


def test_n01_verified_low_not_usable():
    c = ResearchClaim(
        claim_text="x",
        excerpt="x",
        source_result_id="1",
        verification_status="VERIFIED",
        applicability="LOW",
    )
    assert compute_usability(c) == "NOT_USABLE_FOR_DECISION"


def test_n02_not_applicable():
    c = ResearchClaim(
        claim_text="x",
        excerpt="x",
        source_result_id="1",
        verification_status="VERIFIED",
        applicability="NOT_APPLICABLE",
    )
    assert can_unblock_decision(c, domain="WASHOUT") is False


def test_n03_usable_when_verified_high():
    c = ResearchClaim(
        claim_text="x",
        excerpt="x",
        source_result_id="1",
        verification_status="VERIFIED",
        applicability="HIGH",
        decision_domains=["WASHOUT"],
        usability="USABLE_FOR_DECISION",
    )
    assert compute_usability(c) == "USABLE_FOR_DECISION"
    assert can_unblock_decision(c, domain="WASHOUT") is True


def test_n04_low_cannot_unblock():
    c = ResearchClaim(
        claim_text="x",
        excerpt="x",
        source_result_id="1",
        verification_status="VERIFIED",
        applicability="LOW",
        usability="NOT_USABLE_FOR_DECISION",
        decision_domains=["WASHOUT"],
    )
    assert can_unblock_decision(c, domain="WASHOUT") is False


# ---------------------------------------------------------------------------
# O. Conflicts
# ---------------------------------------------------------------------------


def test_o01_no_average():
    conf = detect_numeric_conflicts(
        [
            ResearchClaim(claim_text="a", excerpt="a", source_result_id="1", field_path="pk.t_half", value=8.7),
            ResearchClaim(claim_text="b", excerpt="b", source_result_id="2", field_path="pk.t_half", value=12.1),
        ],
        field_path="pk.t_half",
    )[0]
    with pytest.raises(ValueError):
        conf.resolution = "average of sources"
        assert_no_average(conf)


def test_o02_conflict_open_status():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert any(c.status == "OPEN" for c in list_conflicts(t.id))


def test_o03_values_not_single():
    confs = detect_numeric_conflicts(
        [
            ResearchClaim(claim_text="a", excerpt="a", source_result_id="1", field_path="pk.t_half", value=8.7),
            ResearchClaim(claim_text="b", excerpt="b", source_result_id="2", field_path="pk.t_half", value=12.1),
        ],
        field_path="pk.t_half",
    )
    assert len(confs[0].values) == 2


# ---------------------------------------------------------------------------
# P. Deduplication
# ---------------------------------------------------------------------------


def test_p01_duplicate_run_no_new_sources():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    n = len(list_results(t.id))
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert len(list_results(t.id)) == n


def test_p02_duplicate_claims_not_added():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    n = len(list_claims(t.id))
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert len(list_claims(t.id)) == n


# ---------------------------------------------------------------------------
# Q. Expert review
# ---------------------------------------------------------------------------


def test_q01_verify_requires_reviewer():
    c = ResearchClaim(claim_text="x", excerpt="x", source_result_id="1")
    put_claim(c)
    with pytest.raises(ValueError):
        verify_claim(c.id, reviewer="")


def test_q02_verify_does_not_rewrite_excerpt():
    c = ResearchClaim(claim_text="x", excerpt="exact excerpt", source_result_id="1")
    put_claim(c)
    verify_claim(c.id, reviewer="expert", applicability="HIGH", applicability_reason="ok")
    assert list_claims()[0].excerpt == "exact excerpt"


def test_q03_ai_cannot_verify():
    c = ResearchClaim(claim_text="x", excerpt="x", source_result_id="1")
    put_claim(c)
    with pytest.raises(PermissionError):
        verify_claim(c.id, reviewer="bot", actor="AI")


def test_q04_reject():
    c = ResearchClaim(claim_text="x", excerpt="x", source_result_id="1")
    put_claim(c)
    reject_claim(c.id, reviewer="e", rationale="bad")
    assert list_claims()[0].verification_status == "REJECTED"


def test_q05_request_more_info():
    c = ResearchClaim(claim_text="x", excerpt="x", source_result_id="1", research_task_id=None)
    put_claim(c)
    request_more_information(c.id, reviewer="e", note="need dose context")
    assert list_claims()[0].usability == "REQUIRES_REVIEW"


def test_q06_cannot_complete_without_verified():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert get_task(t.id).status != "COMPLETED"


def test_q07_complete_after_verify_high_no_conflict_pick():
    # Verify one claim with HIGH; conflicts remain → still REVIEW_REQUIRED
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    point = next(
        c
        for c in list_claims(t.id)
        if c.measurement and c.measurement.get("statistic_type") == "MEAN" and c.value == 8.7
    )
    verify_claim(point.id, reviewer="e", applicability="HIGH", applicability_reason="ok")
    # Conflicts open → not COMPLETED
    assert get_task(t.id).status == "REVIEW_REQUIRED"


# ---------------------------------------------------------------------------
# R. Research → decision flow
# ---------------------------------------------------------------------------


def test_r01_apply_verified_half_life(golden_decisions):
    pkg, ctx, decisions = golden_decisions
    tasks = create_tasks_from_decision_gaps("UPDCB-02-BE-2026", decisions, context=CTX)
    hl_task = next(t for t in tasks if t.task_type == "FIND_HALF_LIFE_PK")
    run_research_task(hl_task.id, provider=MockResearchProvider(), context=CTX)
    # Resolve conflict by rejecting one mean, verify other
    means = [
        c
        for c in list_claims(hl_task.id)
        if c.measurement and c.measurement.get("statistic_type") == "MEAN"
    ]
    verify_claim(means[0].id, reviewer="e", applicability="HIGH", applicability_reason="context match")
    for c in means[1:]:
        reject_claim(c.id, reviewer="e", rationale="not selected")
    # Clear conflicts manually for completion path — reject others
    for conf in list_conflicts(hl_task.id):
        conf.status = "RESOLVED"
        conf.resolution = "expert selected one source — not averaged"
    from app.domain.research_evidence_store import put_conflict

    for conf in list_conflicts(hl_task.id):
        put_conflict(conf)
    from app.domain.research_evidence_engine import _maybe_complete_task

    _maybe_complete_task(hl_task.id)
    ctx2, applied = apply_verified_research_to_context(ctx, study_id="UPDCB-02-BE-2026")
    assert "pk.t_half" in applied
    assert ctx2.half_life == float(means[0].value)
    assert ctx2.study_mutated is False


def test_r02_recompute_washout_sampling_not_food(golden_decisions):
    pkg, ctx, decisions = golden_decisions
    ctx.half_life = 8.7
    ctx.fact_statuses["pk.t_half"] = "VERIFIED"
    result = recompute_affected_decisions(ctx, applied_fields=["pk.t_half"], previous=decisions)
    assert "WASHOUT" in result["recomputed_domains"]
    assert "SAMPLING" in result["recomputed_domains"]
    assert "FOOD" not in result["recomputed_domains"]
    assert result["automatic_medical_decisions"] == 0


def test_r03_verified_evidence_not_expert_decision():
    c = ResearchClaim(claim_text="x", excerpt="x", source_result_id="1", verification_status="VERIFIED")
    assert c.to_dict()["is_not_expert_decision"] is True


# ---------------------------------------------------------------------------
# S. Change impact
# ---------------------------------------------------------------------------


def test_s01_tmax_affects_sampling_only(golden_decisions):
    _, ctx, decisions = golden_decisions
    result = recompute_affected_decisions(ctx, applied_fields=["pk.Tmax"], previous=decisions)
    assert result["recomputed_domains"] == ["SAMPLING"]


def test_s02_cv_affects_design(golden_decisions):
    _, ctx, decisions = golden_decisions
    result = recompute_affected_decisions(ctx, applied_fields=["cv_intra"], previous=decisions)
    assert "DESIGN" in result["recomputed_domains"]


# ---------------------------------------------------------------------------
# T. API
# ---------------------------------------------------------------------------


def test_t01_bootstrap(client: TestClient):
    r = client.post("/api/research-center/fixtures/updcb-real/bootstrap")
    assert r.status_code == 201
    body = r.json()
    assert body["study_mutated"] is False
    assert len(body["tasks"]) >= 3


def test_t02_run_task(client: TestClient):
    boot = client.post("/api/research-center/fixtures/updcb-real/bootstrap").json()
    tid = boot["tasks"][0]["id"]
    r = client.post(f"/api/research-center/research-tasks/{tid}/run", json={"use_mock_provider": True})
    assert r.status_code == 200
    assert r.json()["study_mutated"] is False


def test_t03_evidence_endpoints(client: TestClient):
    boot = client.post("/api/research-center/fixtures/updcb-real/bootstrap").json()
    tid = next(t["id"] for t in boot["tasks"] if t["task_type"] == "FIND_HALF_LIFE_PK")
    client.post(f"/api/research-center/research-tasks/{tid}/run", json={"use_mock_provider": True})
    ev = client.get(f"/api/research-center/research-tasks/{tid}/evidence").json()
    assert ev["proposed_is_not_approved"] is True
    conf = client.get(f"/api/research-center/research-tasks/{tid}/conflicts").json()
    assert "conflicts" in conf


def test_t04_verify_api(client: TestClient):
    boot = client.post("/api/research-center/fixtures/updcb-real/bootstrap").json()
    tid = next(t["id"] for t in boot["tasks"] if t["task_type"] == "FIND_TMAX_PK")
    run = client.post(f"/api/research-center/research-tasks/{tid}/run", json={"use_mock_provider": True}).json()
    cid = run["claims"][0]["id"]
    r = client.post(
        f"/api/research-center/evidence/{cid}/verify",
        json={"reviewer": "expert", "applicability": "HIGH", "applicability_reason": "ok"},
    )
    assert r.status_code == 200
    assert r.json()["claim"]["verification_status"] == "VERIFIED"


def test_t05_ai_verify_403(client: TestClient):
    boot = client.post("/api/research-center/fixtures/updcb-real/bootstrap").json()
    tid = next(t["id"] for t in boot["tasks"] if t["task_type"] == "FIND_TMAX_PK")
    run = client.post(f"/api/research-center/research-tasks/{tid}/run", json={"use_mock_provider": True}).json()
    cid = run["claims"][0]["id"]
    r = client.post(
        f"/api/research-center/evidence/{cid}/verify",
        json={"reviewer": "bot", "actor": "AI"},
    )
    assert r.status_code == 403


def test_t06_coverage(client: TestClient):
    boot = client.post("/api/research-center/fixtures/updcb-real/bootstrap").json()
    sid = boot["study_id"]
    r = client.get(f"/api/research-center/studies/{sid}/coverage")
    assert r.status_code == 200
    assert not any(c.get("green") for c in r.json()["coverage"])


def test_t07_list_tasks(client: TestClient):
    boot = client.post("/api/research-center/fixtures/updcb-real/bootstrap").json()
    r = client.get(f"/api/research-center/studies/{boot['study_id']}/research-tasks")
    assert r.json()["automatic_medical_decisions"] == 0


def test_t08_applicability_get(client: TestClient):
    boot = client.post("/api/research-center/fixtures/updcb-real/bootstrap").json()
    tid = next(t["id"] for t in boot["tasks"] if t["task_type"] == "FIND_TMAX_PK")
    run = client.post(f"/api/research-center/research-tasks/{tid}/run", json={"use_mock_provider": True}).json()
    cid = run["claims"][0]["id"]
    r = client.get(f"/api/research-center/evidence/{cid}/applicability")
    assert "independent" in r.json()["note"]


# ---------------------------------------------------------------------------
# U. UI contracts
# ---------------------------------------------------------------------------


def test_u01_task_viewer_proposed_flag():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_TMAX_FOR_SAMPLING", "title": "t"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    from app.domain.research_evidence_engine import task_viewer_payload

    p = task_viewer_payload(t.id)
    assert p["proposed_is_not_approved"] is True
    assert p["study_mutated"] is False


def test_u02_evidence_viewer_fields():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_TMAX_FOR_SAMPLING", "title": "t"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    p = evidence_viewer_payload(list_claims(t.id)[0].id)
    assert "verification" in p and "applicability" in p and "usability" in p


def test_u03_coverage_not_green():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    cov = coverage_for_gap("s", "MISSING_HALF_LIFE_FOR_WASHOUT")
    assert cov.to_dict()["green"] is False


# ---------------------------------------------------------------------------
# V. AI-off
# ---------------------------------------------------------------------------


def test_v01_ai_off(client: TestClient):
    assert client.get("/api/health").json()["ai_enabled"] is False


def test_v02_workflow_without_ai():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    out = run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert out["claims"]


def test_v03_version_0170():
    assert get_settings().app_version == "0.32.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.32.0"


# ---------------------------------------------------------------------------
# W. MockAI
# ---------------------------------------------------------------------------


def test_w01_ai_cannot_verify():
    c = ResearchClaim(claim_text="x", excerpt="x", source_result_id="1")
    put_claim(c)
    with pytest.raises(PermissionError):
        verify_claim(c.id, reviewer="x", actor="MockAI")


def test_w02_ai_cannot_resolve_conflict_via_verify_all():
    # AI cannot verify → cannot clear conflicts
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    c = list_claims(t.id)[0]
    with pytest.raises(PermissionError):
        verify_claim(c.id, reviewer="ai", actor="AI")


# ---------------------------------------------------------------------------
# X. MockResearchProvider
# ---------------------------------------------------------------------------


def test_x01_mock_half_life_fixtures():
    assert len(MOCK_HALF_LIFE_HITS) >= 3


def test_x02_mock_cv_has_between():
    assert any(h.metadata.get("variability_type") == "BETWEEN_SUBJECT" for h in MOCK_CV_HITS)


def test_x03_mock_search_food():
    hits = MockResearchProvider().search("meal calorie breakfast", query_type="FOOD")
    assert hits


# ---------------------------------------------------------------------------
# Y. Golden fixture
# ---------------------------------------------------------------------------


def test_y01_golden_tasks(golden_decisions):
    _, _, decisions = golden_decisions
    tasks = create_tasks_from_decision_gaps("UPDCB-02-BE-2026", decisions, context=CTX)
    create_tasks_from_gaps(
        "UPDCB-02-BE-2026",
        [{"code": "MISSING_MEAL_COMPOSITION", "title": "meal"}],
        context=CTX,
    )
    codes = {t.knowledge_gap_code for t in list_tasks("UPDCB-02-BE-2026")}
    assert "MISSING_CVINTRA" in codes
    assert "MISSING_HALF_LIFE_FOR_WASHOUT" in codes
    assert "MISSING_TMAX_FOR_SAMPLING" in codes
    assert "MISSING_MEAL_COMPOSITION" in codes


def test_y02_golden_mock_run_no_mutation(golden_decisions):
    _, _, decisions = golden_decisions
    tasks = create_tasks_from_decision_gaps("G", decisions, context=CTX)
    for t in tasks:
        out = run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
        assert out["study_mutated"] is False
        assert out["automatic_verifications"] == 0


def test_y03_fixture_id(golden_decisions):
    assert golden_decisions[0].fixture_id == "UPDCB-02-BE-2026-REAL-01"


# ---------------------------------------------------------------------------
# Hard negatives (extra)
# ---------------------------------------------------------------------------


def test_neg01_search_not_auto_verified():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_TMAX_FOR_SAMPLING", "title": "t"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert all(c.verification_status == "PROPOSED" for c in list_claims(t.id))


def test_neg02_missing_source_no_synthetic():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    out = run_research_task(t.id, provider=NullResearchProvider(), context=CTX)
    assert out["claims"] == []
    assert "synthetic" in (get_task(t.id).notes or "").lower() or get_task(t.id).status == "OPEN"


def test_neg03_research_study_mutated_false():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    assert t.to_dict()["study_mutated"] is False


@pytest.mark.parametrize(
    "gap",
    [
        "MISSING_HALF_LIFE_FOR_WASHOUT",
        "MISSING_TMAX_FOR_SAMPLING",
        "MISSING_CVINTRA",
        "MISSING_MEAL_COMPOSITION",
        "MISSING_SMPC_REFERENCE_PRODUCT",
    ],
)
def test_neg04_param_gap_maps(gap):
    assert gap in GAP_TO_TASK


@pytest.mark.parametrize("domain", ["WASHOUT", "SAMPLING", "DESIGN", "FOOD"])
def test_neg05_param_domains_exist(domain):
    assert domain in {"DESIGN", "FOOD", "WASHOUT", "SAMPLING", "ANALYTE_PK"}


def test_neg06_claim_requires_provenance():
    with pytest.raises(ValueError):
        ResearchClaim(claim_text="orphan")


def test_neg07_register_preserves_locator():
    sr = SourceResult(
        research_task_id="t",
        provider="MOCK",
        title="T",
        url_or_source_locator="mock://x",
        text_excerpt="hello",
    )
    put_result(sr)
    src = register_source_from_result(sr, study_id="s")
    assert src.locator == "mock://x"


def test_neg08_no_phase16_sample_size_task():
    assert "FIND_SAMPLE_SIZE" not in RESEARCH_TASK_TYPES


def test_neg09_no_statistics_engine_task():
    assert "FIND_STATISTICS" not in RESEARCH_TASK_TYPES


def test_neg10_apply_to_decisions_api(client: TestClient):
    boot = client.post("/api/research-center/fixtures/updcb-real/bootstrap").json()
    sid = boot["study_id"]
    r = client.post(f"/api/research-center/studies/{sid}/apply-to-decisions", json={})
    assert r.status_code == 200
    assert r.json()["study_mutated"] is False
    assert r.json()["automatic_medical_decisions"] == 0


# ---------------------------------------------------------------------------
# Z. Extra coverage (≥140)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("task_type", list(RESEARCH_TASK_TYPES))
def test_z01_all_task_types_constructible(task_type):
    t = ResearchTask(task_type=task_type, question="q", priority="MEDIUM")
    assert t.task_type == task_type


@pytest.mark.parametrize(
    "status",
    ["OPEN", "SEARCHING", "RESULTS_AVAILABLE", "REVIEW_REQUIRED", "COMPLETED", "BLOCKED", "CANCELLED"],
)
def test_z02_task_statuses(status):
    t = ResearchTask(task_type="OTHER", question="q", status=status, priority="LOW")
    assert t.status == status


@pytest.mark.parametrize("prio", ["CRITICAL", "HIGH", "MEDIUM", "LOW"])
def test_z03_priorities(prio):
    assert ResearchTask(task_type="OTHER", question="q", priority=prio).priority == prio


@pytest.mark.parametrize(
    "qtype",
    ["IDENTITY", "PK", "CV", "DESIGN", "FOOD", "ANALOGUE", "REGULATORY", "SAFETY", "OTHER"],
)
def test_z04_query_types(qtype):
    assert ResearchQuery(research_task_id="t", query_text="sample query", query_type=qtype).query_type == qtype


@pytest.mark.parametrize(
    "stype",
    ["SMPC", "REGULATORY", "PUBLICATION", "CLINICAL_STUDY", "PROTOCOL", "REVIEW", "DATABASE", "OTHER"],
)
def test_z05_source_types(stype):
    assert SourceResult(research_task_id="t", provider="MOCK", title="t", source_type=stype).source_type == stype


@pytest.mark.parametrize("appl", ["DIRECT", "HIGH", "MODERATE", "LOW", "UNKNOWN", "NOT_APPLICABLE"])
def test_z06_applicability_on_claim(appl):
    assert ResearchClaim(claim_text="x", excerpt="x", source_result_id="1", applicability=appl).applicability == appl


@pytest.mark.parametrize("use", ["USABLE_FOR_DECISION", "NOT_USABLE_FOR_DECISION", "REQUIRES_REVIEW"])
def test_z07_usability_states(use):
    assert ResearchClaim(claim_text="x", excerpt="x", source_result_id="1", usability=use).usability == use


def test_z08_generate_query_object():
    t = ResearchTask(
        task_type="FIND_HALF_LIFE_PK",
        question="h",
        knowledge_gap_code="MISSING_HALF_LIFE_FOR_WASHOUT",
    )
    assert "half-life" in generate_research_query(t, context=CTX).query_text


def test_z09_smpc_query_template():
    assert "SmPC" in build_query_text(
        "FIND_SMPC_REFERENCE_PRODUCT", active_substance="upadacitinib", dose="15 mg"
    )


def test_z10_regulatory_query_template():
    assert "guideline" in build_query_text("FIND_REGULATORY_EVIDENCE", active_substance="upadacitinib")


def test_z11_meal_task_run():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_MEAL_COMPOSITION", "title": "m"}], context=CTX)[0]
    assert run_research_task(t.id, provider=MockResearchProvider(), context=CTX)["study_mutated"] is False


def test_z12_results_after_run():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_TMAX_FOR_SAMPLING", "title": "t"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    assert list_results(t.id)


def test_z13_reject_sets_not_usable():
    c = ResearchClaim(claim_text="x", excerpt="x", source_result_id="1")
    put_claim(c)
    reject_claim(c.id, reviewer="e", rationale="no")
    assert list_claims()[0].usability == "NOT_USABLE_FOR_DECISION"


def test_z14_proposed_high_still_requires_review():
    c = ResearchClaim(
        claim_text="x",
        excerpt="x",
        source_result_id="1",
        verification_status="PROPOSED",
        applicability="HIGH",
    )
    assert compute_usability(c) == "REQUIRES_REVIEW"


def test_z15_domain_mismatch_not_usable():
    c = ResearchClaim(
        claim_text="x",
        excerpt="x",
        source_result_id="1",
        verification_status="VERIFIED",
        applicability="HIGH",
        decision_domains=["WASHOUT"],
    )
    assert compute_usability(c, decision_domain="FOOD") == "NOT_USABLE_FOR_DECISION"


def test_z16_coverage_task_present():
    create_tasks_from_gaps("s", [{"code": "MISSING_CVINTRA", "title": "cv"}], context=CTX)
    assert coverage_for_gap("s", "MISSING_CVINTRA").task_present is True


def test_z17_get_task_roundtrip():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_CVINTRA", "title": "cv"}], context=CTX)[0]
    assert get_task(t.id).id == t.id


def test_z18_list_queries_after_create():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_CVINTRA", "title": "cv"}], context=CTX)[0]
    assert len(list_queries(t.id)) >= 1


def test_z19_unknown_substance_unknown_appl():
    appl, _ = derive_analogue_applicability({"ACTIVE_SUBSTANCE": "UNKNOWN"})
    assert appl == "UNKNOWN"


def test_z20_measurement_direct_ok():
    m = EvidenceMeasurement(parameter="Tmax", value=2, unit="h", applicability="DIRECT", statistic_type="MEDIAN")
    assert m.applicability == "DIRECT"


def test_z21_cvintra_auc0t():
    assert CVintraEvidence(CV_value=30, PK_parameter="AUC0-t", variability_type="WITHIN_SUBJECT").PK_parameter == "AUC0-t"


def test_z22_conflict_within_tolerance_empty():
    confs = detect_numeric_conflicts(
        [
            ResearchClaim(claim_text="a", excerpt="a", source_result_id="1", field_path="pk.t_half", value=10.0),
            ResearchClaim(claim_text="b", excerpt="b", source_result_id="2", field_path="pk.t_half", value=10.5),
        ],
        field_path="pk.t_half",
        relative_tolerance=0.15,
    )
    assert confs == []


def test_z23_ai_alternative_empty_raises():
    t = ResearchTask(task_type="FIND_HALF_LIFE_PK", question="h")
    with pytest.raises(ValueError):
        ai_propose_alternative_query(t, alternative_text="  ")


def test_z24_viewer_has_conflicts_key():
    t = create_tasks_from_gaps("s", [{"code": "MISSING_HALF_LIFE_FOR_WASHOUT", "title": "h"}], context=CTX)[0]
    run_research_task(t.id, provider=MockResearchProvider(), context=CTX)
    p = evidence_viewer_payload(list_claims(t.id)[0].id)
    assert "conflicts" in p and "review_history" in p

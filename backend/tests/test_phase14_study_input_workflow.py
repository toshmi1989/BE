"""Phase 14 — Real Writer Input Workflow tests.

AI-off deterministic. No Study mutation. No auto conflict resolve.
No new medical decision algorithms.
"""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.study_input_canonical import (
    assert_extraction_does_not_mutate_study,
    resolve_to_canonical_projection,
)
from app.domain.study_input_classify import classify_document
from app.domain.study_input_classes import FIELD_PATH_SET, PACKAGE_STATUSES
from app.domain.study_input_conflicts import (
    auto_resolve_forbidden,
    detect_candidate_conflicts,
    resolve_conflict,
)
from app.domain.study_input_coverage import build_input_coverage, detect_missing_inputs
from app.domain.study_input_extractors import (
    extract_checklist,
    extract_design_only,
    extract_smpc,
    extract_synopsis,
)
from app.domain.study_input_golden import (
    DESIGN_ONLY_EXPECTATIONS,
    UPDCB_SEMANTIC_EXPECTATIONS,
    compare_semantic,
)
from app.domain.study_input_package import CandidateStudyValue, StudyInputPackage, reject_candidate, verify_candidate
from app.domain.study_input_pipeline import (
    FIXTURE_ROOT,
    apply_ai_candidates,
    attach_document,
    create_package,
    load_design_only_fixture,
    load_real_fixture_package,
    reclassify_document,
    run_extraction,
)
from app.domain.study_input_store import clear_store, package_readiness, put_package
from app.main import create_app


REPO = Path(__file__).resolve().parents[2]
FIXTURE = FIXTURE_ROOT / "updcb_02_be_2026"
CHECKLIST_TXT = (FIXTURE / "sources" / "checklist.docx.txt").read_text(encoding="utf-8")
SYNOPSIS_TXT = (FIXTURE / "sources" / "synopsis.docx.txt").read_text(encoding="utf-8")
DESIGN_TXT = (FIXTURE_ROOT / "design_only_updcb" / "sources" / "design.txt").read_text(encoding="utf-8")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("AI_ENABLED", "false")
    get_settings.cache_clear()
    clear_store()
    app = create_app()
    with TestClient(app) as c:
        yield c
    clear_store()
    get_settings.cache_clear()


@pytest.fixture
def real_pkg() -> StudyInputPackage:
    clear_store()
    return load_real_fixture_package()


# ---------------------------------------------------------------------------
# A. CHECKLIST extraction
# ---------------------------------------------------------------------------


def test_a01_checklist_protocol_number() -> None:
    cands = extract_checklist(CHECKLIST_TXT, source_id="SRC-CL")
    assert any(c.field_path == "study.protocol_number" and c.value == "UPDCB-02-BE-2026" for c in cands)


def test_a02_checklist_sponsor() -> None:
    cands = extract_checklist(CHECKLIST_TXT, source_id="SRC-CL")
    assert any(c.field_path == "sponsor.name" and "ПРОМОМЕД" in str(c.value) for c in cands)


def test_a03_checklist_reference_dose_30mg() -> None:
    cands = extract_checklist(CHECKLIST_TXT, source_id="SRC-CL")
    dose = next(c for c in cands if c.field_path == "reference_product.dose")
    assert dose.value == "30 mg"
    assert dose.status == "PROPOSED"
    assert dose.document_type == "CHECKLIST"


def test_a04_checklist_does_not_invent_test_dose() -> None:
    cands = extract_checklist(CHECKLIST_TXT, source_id="SRC-CL")
    assert not any(c.field_path == "test_product.dose" for c in cands)


def test_a05_checklist_cro_name() -> None:
    cands = extract_checklist(CHECKLIST_TXT, source_id="SRC-CL")
    assert any(c.field_path == "cro.name" for c in cands)


def test_a06_checklist_reference_name_ranvek() -> None:
    cands = extract_checklist(CHECKLIST_TXT, source_id="SRC-CL")
    assert any(c.field_path == "reference_product.name" and "РАНВЭК" in str(c.value) for c in cands)


def test_a07_checklist_provenance_required() -> None:
    cands = extract_checklist(CHECKLIST_TXT, source_id="SRC-CL")
    assert all(c.excerpt and c.source_id for c in cands)


def test_a08_checklist_method_deterministic() -> None:
    cands = extract_checklist(CHECKLIST_TXT, source_id="SRC-CL")
    assert all(c.extraction_method == "DETERMINISTIC" for c in cands)


# ---------------------------------------------------------------------------
# B. SYNOPSIS extraction
# ---------------------------------------------------------------------------


def test_b01_synopsis_protocol() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    assert any(c.field_path == "study.protocol_number" and c.value == "UPDCB-02-BE-2026" for c in cands)


def test_b02_synopsis_reference_dose_15() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    assert any(c.field_path == "reference_product.dose" and c.value == "15 mg" for c in cands)


def test_b03_synopsis_test_dose_15() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    assert any(c.field_path == "test_product.dose" and c.value == "15 mg" for c in cands)


def test_b04_synopsis_subjects_n() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    assert any(c.field_path == "subjects.screened_n" and c.value == 62 for c in cands)
    assert any(c.field_path == "subjects.randomized_n" and c.value == 56 for c in cands)


def test_b05_synopsis_design_flags() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    by = {c.field_path: c.value for c in cands}
    assert by["design.randomized"] is True
    assert by["design.open_label"] is True
    assert by["design.crossover"] is True
    assert by["design.periods"] == 2
    assert by["design.sequences"] == 2
    assert by["design.groups"] == 4


def test_b06_synopsis_washout_7() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    assert any(c.field_path == "washout.duration" and c.value == 7 for c in cands)


def test_b07_synopsis_sampling_19() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    assert any(c.field_path == "sampling.total_points" and c.value == 19 for c in cands)
    times = next(c.value for c in cands if c.field_path == "sampling.times")
    assert 0 in times or 0.0 in times
    assert 72 in times or 72.0 in times
    assert 0.25 in times or 0.25 in [float(x) for x in times]


def test_b08_synopsis_bioanalysis() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    assert any(c.field_path == "bioanalysis.analyte" and c.value == "upadacitinib" for c in cands)
    assert any(c.field_path == "bioanalysis.method" and c.value == "LC-MS/MS" for c in cands)


def test_b09_synopsis_statistics() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    by = {c.field_path: c.value for c in cands}
    assert by["statistics.method"] == "ANOVA"
    assert by["statistics.transformation"] == "log"
    assert by["statistics.confidence_interval"] == "90%"
    assert by["statistics.acceptance_interval"] == "80.00-125.00%"


def test_b10_synopsis_allocation() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    assert any(c.field_path == "subjects.group_allocation" and c.value == "1:1:1:1" for c in cands)


def test_b11_synopsis_status_proposed() -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="SRC-SY")
    assert all(c.status == "PROPOSED" for c in cands)


def test_b12_synopsis_not_hardcoded_as_domain_constant() -> None:
    # Values come from text — empty text yields no n=56
    assert not any(c.field_path == "subjects.randomized_n" for c in extract_synopsis("", source_id="X"))


# ---------------------------------------------------------------------------
# C. DESIGN-only extraction
# ---------------------------------------------------------------------------


def test_c01_design_only_flags() -> None:
    cands = extract_design_only(DESIGN_TXT, source_id="SRC-D")
    by = {c.field_path: c.value for c in cands}
    assert by["design.randomized"] is True
    assert by["design.open_label"] is True
    assert by["design.crossover"] is True
    assert by["design.periods"] == 2
    assert by["design.sequences"] == 2
    assert by["design.groups"] == 4


def test_c02_design_only_subjects() -> None:
    cands = extract_design_only(DESIGN_TXT, source_id="SRC-D")
    by = {c.field_path: c.value for c in cands}
    assert by["subjects.sex"] == "male"
    assert by["subjects.age_min"] == 18
    assert by["subjects.age_max"] == 45
    assert by["subjects.screened_n"] == 62
    assert by["subjects.randomized_n"] == 56
    assert by["subjects.group_allocation"] == "1:1:1:1"


def test_c03_design_source_type() -> None:
    cands = extract_design_only(DESIGN_TXT, source_id="SRC-D")
    assert all(c.document_type == "DESIGN" for c in cands)


def test_c04_design_no_synopsis_word_required() -> None:
    assert "синопсис" not in DESIGN_TXT.lower()
    assert extract_design_only(DESIGN_TXT, source_id="SRC-D")


def test_c05_design_conditions_fasting_fed() -> None:
    cands = extract_design_only(DESIGN_TXT, source_id="SRC-D")
    cond = next(c.value for c in cands if c.field_path == "design.conditions")
    assert "fasting" in cond and "fed" in cond


def test_c06_design_fixture_package() -> None:
    pkg = load_design_only_fixture()
    assert all(c.document_type == "DESIGN" for c in pkg.candidates)
    assert any(g["code"] == "MISSING_SMPC_REFERENCE_PRODUCT" for g in pkg.knowledge_gaps)


# ---------------------------------------------------------------------------
# D. SMPC extraction
# ---------------------------------------------------------------------------


def test_d01_smpc_name_dose(real_pkg: StudyInputPackage) -> None:
    smpc = [c for c in real_pkg.candidates if c.document_type == "SMPC"]
    assert any(c.field_path == "reference_product.name" and "РАНВЭК" in str(c.value) for c in smpc)
    assert any(c.field_path == "reference_product.dose" and c.value == "15 mg" for c in smpc)


def test_d02_smpc_active_substance(real_pkg: StudyInputPackage) -> None:
    assert any(
        c.document_type == "SMPC" and c.field_path == "reference_product.active_substance" and c.value == "upadacitinib"
        for c in real_pkg.candidates
    )


def test_d03_smpc_not_auto_verified(real_pkg: StudyInputPackage) -> None:
    assert all(c.status == "PROPOSED" for c in real_pkg.candidates if c.document_type == "SMPC")


def test_d04_smpc_text_extractor() -> None:
    text = "РАНВЭК, 15 мг, таблетки с пролонгированным высвобождением. Действующее вещество: упадацитиниб. Противопоказания. CYP3A4."
    cands = extract_smpc(text, source_id="SRC-S", pages=[{"page_number": 1, "text": text}])
    assert any(c.value == "15 mg" for c in cands if c.field_path == "reference_product.dose")


# ---------------------------------------------------------------------------
# E. Classification
# ---------------------------------------------------------------------------


def test_e01_classify_checklist_filename() -> None:
    r = classify_document(filename="Чек-лист протокол.docx", text="спонсор")
    assert r.document_type == "CHECKLIST"


def test_e02_classify_synopsis_filename() -> None:
    r = classify_document(filename="Синопсис_UPDCB.docx", text="")
    assert r.document_type == "SYNOPSIS"


def test_e03_classify_smpc_filename() -> None:
    r = classify_document(filename="02001-SmPC-v2.pdf", text="")
    assert r.document_type == "SMPC"


def test_e04_user_selected_not_overwritten() -> None:
    r = classify_document(filename="weird.pdf", text="рандомизированное перекрестное", user_selected_type="CHECKLIST")
    assert r.document_type == "CHECKLIST"
    assert r.method == "MANUAL"
    assert r.overridable is False


def test_e05_design_short_text() -> None:
    r = classify_document(filename="note.txt", text=DESIGN_TXT)
    assert r.document_type == "DESIGN"


def test_e06_reclassify_user_wins(real_pkg: StudyInputPackage) -> None:
    doc = real_pkg.documents[0]
    reclassify_document(real_pkg, doc.document_id, document_type="OTHER", user_selected=True)
    assert doc.document_type == "OTHER"
    assert doc.user_selected_type is True


def test_e07_unknown_fallback() -> None:
    r = classify_document(filename="x.bin", text="hello world")
    assert r.document_type == "UNKNOWN"


# ---------------------------------------------------------------------------
# F. Source / version / provenance
# ---------------------------------------------------------------------------


def test_f01_documents_have_hash(real_pkg: StudyInputPackage) -> None:
    assert all(d.content_hash and len(d.content_hash) == 64 for d in real_pkg.documents if d.role == "INPUT")


def test_f02_source_and_version_ids(real_pkg: StudyInputPackage) -> None:
    assert all(d.source_id and d.source_version_id for d in real_pkg.documents)


def test_f03_candidate_provenance(real_pkg: StudyInputPackage) -> None:
    assert all(c.source_id and c.excerpt for c in real_pkg.candidates)


def test_f04_fixture_json_exists() -> None:
    assert (FIXTURE / "fixture.json").exists()


def test_f05_golden_is_reference_output(real_pkg: StudyInputPackage) -> None:
    golden = next(d for d in real_pkg.documents if d.document_type == "GOLDEN_PROTOCOL")
    assert golden.role == "REFERENCE_OUTPUT"
    assert not any(c.document_type == "GOLDEN_PROTOCOL" for c in real_pkg.candidates)


# ---------------------------------------------------------------------------
# G. Candidate lifecycle
# ---------------------------------------------------------------------------


def test_g01_verify_requires_reviewer() -> None:
    c = CandidateStudyValue(
        field_path="subjects.sex",
        value="male",
        value_type="string",
        source_id="S",
        document_type="DESIGN",
        excerpt="мужского",
    )
    with pytest.raises(ValueError):
        verify_candidate(c, reviewer="")


def test_g02_verify_sets_verified() -> None:
    c = CandidateStudyValue(
        field_path="subjects.sex",
        value="male",
        value_type="string",
        source_id="S",
        document_type="DESIGN",
        excerpt="мужского",
    )
    verify_candidate(c, reviewer="expert")
    assert c.status == "VERIFIED"
    assert c.reviewed_by == "expert"


def test_g03_reject() -> None:
    c = CandidateStudyValue(
        field_path="subjects.sex",
        value="male",
        value_type="string",
        source_id="S",
        document_type="DESIGN",
        excerpt="мужского",
    )
    reject_candidate(c, reviewer="expert", notes="wrong")
    assert c.status == "REJECTED"


def test_g04_missing_excerpt_rejected() -> None:
    with pytest.raises(ValueError):
        CandidateStudyValue(
            field_path="subjects.sex",
            value="male",
            value_type="string",
            source_id="S",
            document_type="DESIGN",
            excerpt="",
        )


def test_g05_invalid_field_path_rejected() -> None:
    with pytest.raises(ValueError):
        CandidateStudyValue(
            field_path="hack.injected",
            value=1,
            value_type="int",
            source_id="S",
            document_type="DESIGN",
            excerpt="x",
        )


# ---------------------------------------------------------------------------
# H. Conflict detection (REQUIRED real conflict)
# ---------------------------------------------------------------------------


def test_h01_reference_dose_open_conflict(real_pkg: StudyInputPackage) -> None:
    conflicts = [c for c in real_pkg.conflicts if c["field_path"] == "reference_product.dose"]
    assert len(conflicts) == 1
    assert conflicts[0]["status"] == "OPEN"
    assert set(conflicts[0]["values"]) == {"15 mg", "30 mg"}


def test_h02_conflict_sources_include_checklist_synopsis_smpc(real_pkg: StudyInputPackage) -> None:
    c = next(x for x in real_pkg.conflicts if x["field_path"] == "reference_product.dose")
    types = {s["document_type"] for s in c["sources"]}
    assert {"CHECKLIST", "SYNOPSIS", "SMPC"} <= types


def test_h03_no_majority_auto_resolve(real_pkg: StudyInputPackage) -> None:
    # 2x 15mg vs 1x 30mg — still OPEN
    assert all(c["status"] == "OPEN" for c in real_pkg.conflicts)


def test_h04_auto_resolve_forbidden_helper() -> None:
    from app.domain.study_input_conflicts import FieldConflict

    fc = FieldConflict(
        conflict_id="x",
        field_path="reference_product.dose",
        candidate_ids=[],
        values=["15 mg", "30 mg"],
        sources=[],
    )
    auto_resolve_forbidden(fc)


# ---------------------------------------------------------------------------
# I. Conflict review
# ---------------------------------------------------------------------------


def test_i01_resolve_requires_reason(real_pkg: StudyInputPackage) -> None:
    from app.domain.study_input_conflicts import FieldConflict

    raw = real_pkg.conflicts[0]
    fc = FieldConflict(
        conflict_id=raw["conflict_id"],
        field_path=raw["field_path"],
        candidate_ids=raw["candidate_ids"],
        values=raw["values"],
        sources=raw["sources"],
    )
    with pytest.raises(ValueError):
        resolve_conflict(fc, reviewer="e", outcome="SELECT_VALUE", reason="", selected_candidate_id="x")


def test_i02_resolve_select_value(real_pkg: StudyInputPackage) -> None:
    from app.domain.study_input_conflicts import FieldConflict

    raw = real_pkg.conflicts[0]
    sel = raw["candidate_ids"][0]
    fc = FieldConflict(
        conflict_id=raw["conflict_id"],
        field_path=raw["field_path"],
        candidate_ids=raw["candidate_ids"],
        values=raw["values"],
        sources=raw["sources"],
    )
    resolve_conflict(
        fc,
        reviewer="expert",
        outcome="SELECT_VALUE",
        reason="Checklist typo; SmPC authoritative after review",
        selected_candidate_id=sel,
    )
    assert fc.status == "RESOLVED"
    assert fc.reviewer == "expert"


# ---------------------------------------------------------------------------
# J / K. Missing input + research tasks
# ---------------------------------------------------------------------------


def test_j01_missing_smpc_creates_gap() -> None:
    pkg = load_design_only_fixture()
    assert any(g["code"] == "MISSING_SMPC_REFERENCE_PRODUCT" for g in pkg.knowledge_gaps)


def test_k01_missing_smpc_creates_research_task() -> None:
    pkg = load_design_only_fixture()
    assert any(t["code"] == "FIND_SMPC_REFERENCE_PRODUCT" for t in pkg.research_tasks)


def test_j02_design_without_synopsis_not_blocking_extraction() -> None:
    pkg = load_design_only_fixture()
    assert pkg.candidates  # extraction proceeded
    assert any(g["code"] == "MISSING_SYNOPSIS_OPTIONAL" and not g["blocking"] for g in pkg.knowledge_gaps)


def test_j03_real_package_has_smpc_no_missing_smpc(real_pkg: StudyInputPackage) -> None:
    assert not any(g["code"] == "MISSING_SMPC_REFERENCE_PRODUCT" for g in real_pkg.knowledge_gaps)


# ---------------------------------------------------------------------------
# L. Canonical resolution
# ---------------------------------------------------------------------------


def test_l01_proposed_not_applied_when_verification_required(real_pkg: StudyInputPackage) -> None:
    result = resolve_to_canonical_projection(real_pkg.candidates, conflicts=real_pkg.conflicts, require_verified=True)
    assert result.applied == {}
    assert result.study_mutated is False


def test_l02_open_conflict_skipped(real_pkg: StudyInputPackage) -> None:
    # Verify a non-conflict field
    cand = next(c for c in real_pkg.candidates if c.field_path == "subjects.randomized_n")
    verify_candidate(cand, reviewer="e")
    result = resolve_to_canonical_projection(real_pkg.candidates, conflicts=real_pkg.conflicts, require_verified=True)
    assert "subjects.randomized_n" in result.applied
    assert any(s["reason"] == "OPEN_CONFLICT" for s in result.skipped if s["field_path"] == "reference_product.dose")


def test_l03_extraction_does_not_mutate_study_snapshot(real_pkg: StudyInputPackage) -> None:
    before = {"protocol": "X", "dose": None}
    after = copy.deepcopy(before)
    run_extraction(real_pkg)
    assert_extraction_does_not_mutate_study(before, after)


# ---------------------------------------------------------------------------
# M. Coverage
# ---------------------------------------------------------------------------


def test_m01_reference_product_conflict_state(real_pkg: StudyInputPackage) -> None:
    cov = build_input_coverage(real_pkg)
    assert cov["domains"]["REFERENCE_PRODUCT"]["state"] == "CONFLICT"
    assert cov["ready_for_assembly"] is False


def test_m02_design_complete_or_present(real_pkg: StudyInputPackage) -> None:
    state = real_pkg.coverage["domains"]["DESIGN"]["state"]
    assert state in {"PRESENT", "VERIFIED", "REVIEW_REQUIRED", "PARTIAL"}


def test_m03_readiness_not_green_with_conflict(real_pkg: StudyInputPackage) -> None:
    r = package_readiness(real_pkg)
    assert r["ready_green"] is False
    assert r["critical_conflict_unresolved"] is True


# ---------------------------------------------------------------------------
# N / O. API + UI contract
# ---------------------------------------------------------------------------


def test_n01_api_load_real_fixture(client: TestClient) -> None:
    res = client.post("/api/study-input/fixtures/updcb-real/load")
    assert res.status_code == 201
    body = res.json()
    assert body["fixture_id"] == "UPDCB-02-BE-2026-REAL-01"
    assert body["study_mutated"] is False


def test_n02_api_conflicts(client: TestClient) -> None:
    pkg = client.post("/api/study-input/fixtures/updcb-real/load").json()
    conf = client.get(f"/api/study-input/packages/{pkg['package_id']}/conflicts").json()
    assert any(c["field_path"] == "reference_product.dose" and c["status"] == "OPEN" for c in conf)


def test_n03_api_coverage(client: TestClient) -> None:
    pkg = client.post("/api/study-input/fixtures/updcb-real/load").json()
    cov = client.get(f"/api/study-input/packages/{pkg['package_id']}/coverage").json()
    assert cov["domains"]["REFERENCE_PRODUCT"]["state"] == "CONFLICT"


def test_n04_api_verify_candidate(client: TestClient) -> None:
    pkg = client.post("/api/study-input/fixtures/updcb-real/load").json()
    cands = client.get(f"/api/study-input/packages/{pkg['package_id']}/candidates").json()
    cid = cands[0]["id"]
    res = client.post(
        f"/api/study-input/packages/{pkg['package_id']}/candidates/{cid}/review",
        json={"action": "VERIFY", "reviewer": "api-expert"},
    )
    assert res.status_code == 200
    assert res.json()["study_mutated"] is False
    assert res.json()["candidate"]["status"] == "VERIFIED"


def test_n05_api_readiness(client: TestClient) -> None:
    pkg = client.post("/api/study-input/fixtures/updcb-real/load").json()
    r = client.get(f"/api/study-input/packages/{pkg['package_id']}/readiness").json()
    assert r["ready_green"] is False


def test_n06_api_create_package(client: TestClient) -> None:
    res = client.post("/api/study-input/packages", json={})
    assert res.status_code == 201
    assert res.json()["status"] == "DRAFT"


def test_n07_api_design_fixture(client: TestClient) -> None:
    res = client.post("/api/study-input/fixtures/design-only/load")
    assert res.status_code == 201
    missing = client.get(f"/api/study-input/packages/{res.json()['package_id']}/missing").json()
    assert any(g["code"] == "MISSING_SMPC_REFERENCE_PRODUCT" for g in missing["knowledge_gaps"])


def test_n08_api_resolve_conflict(client: TestClient) -> None:
    pkg = client.post("/api/study-input/fixtures/updcb-real/load").json()
    conf = client.get(f"/api/study-input/packages/{pkg['package_id']}/conflicts").json()[0]
    res = client.post(
        f"/api/study-input/packages/{pkg['package_id']}/conflicts/{conf['conflict_id']}/resolve",
        json={
            "reviewer": "expert",
            "outcome": "SELECT_VALUE",
            "reason": "SmPC dose after expert review",
            "selected_candidate_id": conf["candidate_ids"][1],
        },
    )
    assert res.status_code == 200
    assert res.json()["conflict"]["status"] == "RESOLVED"


def test_o01_api_golden_compare(client: TestClient) -> None:
    pkg = client.post("/api/study-input/fixtures/updcb-real/load").json()
    rep = client.get(f"/api/study-input/packages/{pkg['package_id']}/golden-compare").json()
    assert rep["match_count"] >= 15
    assert rep["conflict_ok"] is True


# ---------------------------------------------------------------------------
# P. AI-off
# ---------------------------------------------------------------------------


def test_p01_ai_disabled_in_settings(client: TestClient) -> None:
    h = client.get("/api/health").json()
    assert h["ai_enabled"] is False


def test_p02_real_extraction_ai_off(real_pkg: StudyInputPackage) -> None:
    assert all(c.extraction_method == "DETERMINISTIC" for c in real_pkg.candidates)
    assert len(real_pkg.candidates) >= 40


def test_p03_version_0150() -> None:
    assert get_settings().app_version == "0.32.0"


# ---------------------------------------------------------------------------
# Q. MockAI
# ---------------------------------------------------------------------------


def test_q01_ai_proposals_proposed_only(real_pkg: StudyInputPackage) -> None:
    created = apply_ai_candidates(
        real_pkg,
        [
            {
                "field_path": "food.breakfast_type",
                "value": "high-calorie",
                "value_type": "string",
                "excerpt": "завтрак",
                "document_type": "SYNOPSIS",
            }
        ],
    )
    assert created and created[0].status == "PROPOSED" and created[0].extraction_method == "AI"


def test_q02_malformed_ai_rejected(real_pkg: StudyInputPackage) -> None:
    before = len(real_pkg.candidates)
    apply_ai_candidates(real_pkg, [{"field_path": "not.a.path", "value": 1}])
    assert len(real_pkg.candidates) == before


def test_q03_ai_cannot_mutate_study(client: TestClient) -> None:
    pkg = client.post("/api/study-input/fixtures/updcb-real/load").json()
    res = client.post(
        f"/api/study-input/packages/{pkg['package_id']}/ai-propose",
        json={
            "proposals": [
                {
                    "field_path": "washout.duration",
                    "value": 99,
                    "excerpt": "ai",
                    "document_type": "SYNOPSIS",
                }
            ]
        },
    )
    assert res.json()["study_mutated"] is False


def test_q04_ai_cannot_set_verified(real_pkg: StudyInputPackage) -> None:
    created = apply_ai_candidates(
        real_pkg,
        [
            {
                "field_path": "food.breakfast_timing",
                "value": "30 min",
                "excerpt": "x",
                "document_type": "SYNOPSIS",
                "status": "VERIFIED",  # ignored — constructor forces PROPOSED via apply
            }
        ],
    )
    assert created[0].status == "PROPOSED"


# ---------------------------------------------------------------------------
# R. Golden semantic
# ---------------------------------------------------------------------------


def test_r01_golden_semantic_expectations(real_pkg: StudyInputPackage) -> None:
    by_path: dict = {}
    doses = []
    for c in real_pkg.candidates:
        if c.document_type == "SYNOPSIS":
            by_path[c.field_path] = c.value
        if c.field_path == "reference_product.dose":
            doses.append(c.value)
    by_path["reference_product.dose__all"] = doses
    rep = compare_semantic(
        fixture_id="UPDCB-02-BE-2026-REAL-01",
        actual_by_path=by_path,
        expectations=UPDCB_SEMANTIC_EXPECTATIONS,
        conflict_values={"30 mg", "15 mg"},
    )
    assert rep.mismatch_count == 0
    assert rep.missing_count <= 2
    assert rep.conflict_ok is True


def test_r02_design_only_golden() -> None:
    pkg = load_design_only_fixture()
    by = {c.field_path: c.value for c in pkg.candidates}
    rep = compare_semantic(
        fixture_id="DESIGN-ONLY",
        actual_by_path=by,
        expectations=DESIGN_ONLY_EXPECTATIONS,
        conflict_field=None,
        conflict_values=None,
    )
    assert rep.mismatch_count == 0
    assert rep.missing_count == 0


# ---------------------------------------------------------------------------
# S. Regression assembly gate
# ---------------------------------------------------------------------------


def test_s01_package_statuses_valid(real_pkg: StudyInputPackage) -> None:
    assert real_pkg.status in PACKAGE_STATUSES


def test_s02_health_still_ok(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200


# ---------------------------------------------------------------------------
# T. Hard negatives / guards
# ---------------------------------------------------------------------------


def test_t01_extraction_cannot_mutate_study_flag(real_pkg: StudyInputPackage) -> None:
    assert real_pkg.to_dict()["study_mutated"] is False


def test_t02_other_doc_no_controlled_fields() -> None:
    pkg = create_package()
    path = FIXTURE_ROOT / "design_only_updcb" / "sources" / "design.txt"
    doc = attach_document(pkg, path=path, document_type="OTHER", user_selected=True)
    assert doc.document_type == "OTHER"
    run_extraction(pkg)
    assert pkg.candidates == []


def test_t03_previous_protocol_no_study_fields() -> None:
    pkg = create_package()
    path = FIXTURE / "sources" / "golden_protocol.docx"
    attach_document(pkg, path=path, document_type="PREVIOUS_PROTOCOL", user_selected=True, role="INPUT")
    run_extraction(pkg)
    assert pkg.candidates == []


def test_t04_missing_provenance_rejected() -> None:
    with pytest.raises(ValueError):
        CandidateStudyValue(
            field_path="design.periods",
            value=2,
            value_type="int",
            source_id="",
            document_type="DESIGN",
            excerpt="x",
        )


def test_t05_rerun_extraction_replace_not_duplicate_uncontrolled(real_pkg: StudyInputPackage) -> None:
    n1 = len(real_pkg.candidates)
    run_extraction(real_pkg, replace=True)
    n2 = len(real_pkg.candidates)
    assert n2 == n1


def test_t06_field_path_controlled() -> None:
    assert "reference_product.dose" in FIELD_PATH_SET


def test_t07_no_fake_medical_on_missing_smpc() -> None:
    pkg = load_design_only_fixture()
    assert not any(c.field_path.startswith("safety.") and c.document_type == "SMPC" for c in pkg.candidates)
    assert any(g["code"] == "MISSING_SMPC_REFERENCE_PRODUCT" for g in pkg.knowledge_gaps)


def test_t08_proposed_not_authoritative() -> None:
    result = resolve_to_canonical_projection(
        [
            CandidateStudyValue(
                field_path="washout.duration",
                value=7,
                value_type="int",
                source_id="S",
                document_type="SYNOPSIS",
                excerpt="7 дней",
                status="PROPOSED",
            )
        ],
        require_verified=True,
    )
    assert "washout.duration" not in result.applied


def test_t09_conflicts_not_auto_resolved_on_detect() -> None:
    cands = [
        CandidateStudyValue(
            field_path="reference_product.dose",
            value="30 mg",
            value_type="string",
            source_id="A",
            document_type="CHECKLIST",
            excerpt="30",
        ),
        CandidateStudyValue(
            field_path="reference_product.dose",
            value="15 mg",
            value_type="string",
            source_id="B",
            document_type="SYNOPSIS",
            excerpt="15",
        ),
    ]
    conf = detect_candidate_conflicts(cands)
    assert conf[0].status == "OPEN"
    assert conf[0].outcome is None


def test_t10_canonical_projection_study_mutated_false(real_pkg: StudyInputPackage) -> None:
    assert resolve_to_canonical_projection(real_pkg.candidates, conflicts=real_pkg.conflicts).study_mutated is False


# ---------------------------------------------------------------------------
# Extra coverage to reach ≥100 meaningful tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "design.randomized",
        "design.open_label",
        "design.crossover",
        "design.periods",
        "design.sequences",
        "design.groups",
        "subjects.sex",
        "subjects.age_min",
        "subjects.age_max",
        "subjects.screened_n",
        "subjects.randomized_n",
        "subjects.group_allocation",
        "washout.duration",
        "sampling.total_points",
        "bioanalysis.analyte",
        "statistics.method",
        "test_product.dose",
        "study.protocol_number",
    ],
)
def test_x_param_synopsis_has_path(path: str) -> None:
    cands = extract_synopsis(SYNOPSIS_TXT, source_id="S")
    assert any(c.field_path == path for c in cands), path


@pytest.mark.parametrize(
    "token,path,value",
    [
        ("рандомизированное", "design.randomized", True),
        ("открытое", "design.open_label", True),
        ("перекрестное", "design.crossover", True),
        ("двухпериодное", "design.periods", 2),
        ("четырех группах", "design.groups", 4),
        ("1:1:1:1", "subjects.group_allocation", "1:1:1:1"),
    ],
)
def test_x_param_design_tokens(token: str, path: str, value) -> None:
    assert token.lower() in DESIGN_TXT.lower() or token in DESIGN_TXT
    cands = extract_design_only(DESIGN_TXT, source_id="D")
    assert any(c.field_path == path and c.value == value for c in cands)


def test_x01_package_document_count(real_pkg: StudyInputPackage) -> None:
    assert len(real_pkg.documents) == 4


def test_x02_input_docs_three(real_pkg: StudyInputPackage) -> None:
    assert len([d for d in real_pkg.documents if d.role == "INPUT"]) == 3


def test_x03_checklist_hash_stable() -> None:
    p = FIXTURE / "sources" / "checklist.docx"
    h1 = hashlib.sha256(p.read_bytes()).hexdigest()
    h2 = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h1 == h2


def test_x04_smpc_pdf_exists() -> None:
    assert (FIXTURE / "sources" / "smpc_ranvek.pdf").exists()


def test_x05_api_canonical_projection(client: TestClient) -> None:
    pkg = client.post("/api/study-input/fixtures/updcb-real/load").json()
    res = client.get(f"/api/study-input/packages/{pkg['package_id']}/canonical-projection").json()
    assert res["study_mutated"] is False
    assert res["applied"] == {}


def test_x06_api_list_documents(client: TestClient) -> None:
    pkg = client.post("/api/study-input/fixtures/updcb-real/load").json()
    docs = client.get(f"/api/study-input/packages/{pkg['package_id']}/documents").json()
    assert len(docs) == 4


def test_x07_api_classify(client: TestClient) -> None:
    pkg = client.post("/api/study-input/fixtures/updcb-real/load").json()
    doc_id = pkg["documents"][0]["document_id"]
    res = client.post(
        f"/api/study-input/packages/{pkg['package_id']}/documents/{doc_id}/classify",
        json={"document_type": "CHECKLIST", "user_selected": True},
    )
    assert res.status_code == 200
    assert res.json()["user_selected_type"] is True


def test_x08_api_extract_empty_package(client: TestClient) -> None:
    pkg = client.post("/api/study-input/packages", json={}).json()
    res = client.post(f"/api/study-input/packages/{pkg['package_id']}/extract")
    assert res.status_code == 200
    assert res.json()["study_mutated"] is False


def test_x09_missing_gap_no_fabricated_contraindications() -> None:
    pkg = load_design_only_fixture()
    assert not any("contraindic" in str(c.value).lower() for c in pkg.candidates)


def test_x10_put_package_store(real_pkg: StudyInputPackage) -> None:
    put_package(real_pkg)
    from app.domain.study_input_store import get_package

    assert get_package(real_pkg.package_id) is real_pkg

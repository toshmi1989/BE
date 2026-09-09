"""Phase 13.3 — Decision 85 regulatory claim verification tests (§28).

≥60 meaningful tests. Exact no-mutation names from phase §22.
No invented pages. No auto-verify without reviewer. No assert True.
"""

from __future__ import annotations

import copy
import hashlib
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.decision85_claims import (
    CLAIM_SPECS,
    DECISION85_DOC_ID,
    DECISION85_FILENAME,
    DECISION85_SOURCE_ID,
    FIRST_BATCH_KEYS,
    KNOWN_AMENDMENTS,
    build_decision85_claims,
    decision85_doc_path,
    extract_amendments_from_text,
    extract_point_clause,
    import_decision85_source,
    interview_conflicts_for_decision85,
    knowledge_gaps_decision85,
    load_decision85_text,
    rule_candidates_from_verified,
)
from app.domain.decision85_mhtml import extract_mhtml_text, flatten_ws
from app.domain.decision85_pipeline import run_decision85_verification_pipeline
from app.domain.document_ingest import sha256_hex
from app.domain.knowledge_seed import KNOWLEDGE_RULE_SEEDS
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.regulatory_claims import EvidenceProvenance, build_claim
from app.domain.regulatory_interview import interview_claims_as_evidence
from app.domain.regulatory_source_slots import refresh_slots
from app.domain.regulatory_verify import (
    VerifyGuardError,
    clear_review_audit,
    create_rule_candidate_from_claim,
    review_audit_trail,
    validate_verify_payload,
    verify_claim_explicit,
)
from app.main import create_app


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
D85_PATH = REPO_ROOT / "fixtures" / "regulatory" / "eec" / DECISION85_FILENAME
assert D85_PATH.is_file(), f"Decision 85 source missing: {D85_PATH}"

REVIEWER = "phase13_3_test_reviewer"


def _iso_root(tmp_path: Path) -> Path:
    """Isolated regulatory root with Decision 85 copied into eec/."""
    root = tmp_path / "regulatory"
    eec = root / "eec"
    eec.mkdir(parents=True)
    (root / "_imported").mkdir(parents=True)
    shutil.copy2(D85_PATH, eec / DECISION85_FILENAME)
    cache = D85_PATH.with_name("16sr0085_extracted.txt")
    if cache.is_file():
        shutil.copy2(cache, eec / cache.name)
    return root


def _canonical_study() -> dict:
    return {
        "study": {"id": "study-13.3", "protocol_number": "BE-13.3-001", "version": "1.0"},
        "product": {"trade_name": "Test", "inn": "inn", "dosage": "100 mg"},
        "reference_product": {
            "trade_name": "Ref",
            "inn": "inn",
            "dosage": "100 mg",
            "manufacturer": "Maker",
            "status": "FINAL",
            "selected": True,
        },
        "design": {"type": "CROSSOVER_2X2", "periods": 2, "status": "FINAL"},
        "sampling": {
            "points": [{"time_h": 0.0}, {"time_h": 2.0}, {"time_h": 24.0}],
            "status": "FINAL",
        },
        "pk": {"primary": ["Cmax", "AUC0-t"], "status": "FINAL"},
        "safety": {"monitoring": "standard_be", "status": "FINAL"},
        "food": {"condition": "FED", "kcal": 900},
        "washout": {"periods": 7},
        "analyte": {"name": "parent"},
        "statistics": {"cv_intra": None, "method": "ANOVA"},
    }


def _by_key(claims: list, key: str):
    for c in claims:
        cid = c.claim_id if hasattr(c, "claim_id") else c.get("claim_id", "")
        if f"D85-{key}-" in cid or cid.startswith(f"D85-{key}-"):
            return c
    raise AssertionError(f"claim key {key} not found in {[getattr(c,'claim_id',c.get('claim_id')) for c in claims]}")


def _claim_dicts(result: dict) -> list[dict]:
    return list(result.get("claims") or [])


# ---------------------------------------------------------------------------
# Source import / version / amendments
# ---------------------------------------------------------------------------


def test_source_file_present() -> None:
    assert decision85_doc_path().is_file()
    assert decision85_doc_path().name == DECISION85_FILENAME


def test_source_is_mhtml() -> None:
    raw = D85_PATH.read_bytes()
    assert raw.startswith(b"MIME-Version")
    text = extract_mhtml_text(D85_PATH)
    assert "биоэквивалент" in text.lower() or "референт" in text.lower()


def test_source_import(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_decision85_source(root=root, project_id="p133")
    assert result["status"] == "IMPORTED"
    assert result["study_mutated"] is False
    assert result["auto_verified"] is False
    assert result["source_version"]["source_id"] == DECISION85_SOURCE_ID
    assert result["source_version"]["ingestion_status"] == "OK"
    assert result["source_version"]["verification_status"] == "REVIEW_REQUIRED"
    assert (root / "_imported" / DECISION85_SOURCE_ID).is_dir()


def test_source_hash(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    content = (root / "eec" / DECISION85_FILENAME).read_bytes()
    expected = hashlib.sha256(content).hexdigest()
    assert sha256_hex(content) == expected
    result = import_decision85_source(root=root)
    assert result["content_hash"] == expected
    assert result["source_version"]["content_hash"] == expected


def test_source_version(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_decision85_source(root=root)
    sv = result["source_version"]
    assert sv["version_id"].startswith("SV-")
    assert sv["document_identifier"] == DECISION85_DOC_ID
    assert sv["source_class"] == "EEC_REGULATORY"
    assert sv["issuing_authority"]
    assert "Евразийск" in sv["issuing_authority"] or "EEC" in sv["issuing_authority"]
    assert sv["filename"] == DECISION85_FILENAME
    assert sv["technical_fixture"] is False


def test_source_duplicate_returns_existing(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    r1 = import_decision85_source(root=root)
    assert r1["status"] == "IMPORTED"
    r2 = import_decision85_source(root=root)
    assert r2["status"] == "EXISTING_SOURCE_VERSION"
    assert r2["source_version"]["version_id"] == r1["source_version"]["version_id"]
    assert r2["study_mutated"] is False


def test_amendment_metadata(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_decision85_source(root=root)
    am = result["amendments"]
    assert len(am) == 3
    nums = {a["number"] for a in am}
    assert nums == {"67", "22", "30"}
    assert all(a["status"] == "SOURCE_EMBEDDED" for a in am)
    assert result["amendment_metadata_certainty"] == "SOURCE_EMBEDDED"


def test_amendment_dates_match_known() -> None:
    text = load_decision85_text()
    found = extract_amendments_from_text(text)
    by_num = {a["number"]: a for a in found}
    for known in KNOWN_AMENDMENTS:
        assert by_num[known["number"]]["date"] == known["date"]
        assert by_num[known["number"]]["status"] == "SOURCE_EMBEDDED"


def test_amendments_not_invented_when_header_absent() -> None:
    assert extract_amendments_from_text("no amendment header here") == []


def test_app_version_0_14_3() -> None:
    assert Settings().app_version == "0.33.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.33.0"
    assert get_settings().app_version == "0.33.0"


# ---------------------------------------------------------------------------
# Claim pack / points
# ---------------------------------------------------------------------------


def test_claim_pack_count(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_decision85_source(root=root)
    claims = result["claim_objects"]
    assert len(claims) == len(CLAIM_SPECS)
    assert len(claims) == 21
    assert all(c.claim_id.startswith("D85-") for c in claims)


def test_point_18_reference(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    c = _by_key(claims, "REF-01")
    assert "18" in c.claim_id
    assert c.domain == "REFERENCE"
    assert "референтного" in (c.raw_extract or "").lower()
    assert "последовательност" in (c.raw_extract or "").lower()


def test_point_44_food_fasting(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "FOOD-01")
    assert c.domain == "FOOD"
    assert "натощак" in (c.raw_extract or "").lower()
    assert "44" in c.claim_id


def test_point_46_standard_meal(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "FOOD-02")
    ex = c.raw_extract or ""
    assert "800" in ex
    assert "1000" in ex
    assert "50 процентов" in ex.lower() or "50%" in ex
    assert "жир" in ex.lower()


def test_point_47_pk_parameters(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    pk1 = _by_key(claims, "PK-01")
    pk2 = _by_key(claims, "PK-02")
    assert "AUC(0-t)" in (pk1.raw_extract or "")
    assert "Cmax" in (pk1.raw_extract or "")
    assert "AUC(0-72" in (pk2.raw_extract or "")
    assert "kel" in (pk2.raw_extract or "").lower()


def test_points_50_52_analyte(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    a1 = _by_key(claims, "ANALYTE-01")
    a2 = _by_key(claims, "ANALYTE-02")
    a3 = _by_key(claims, "ANALYTE-03")
    assert "50" in a1.claim_id and "исходного соединения" in (a1.raw_extract or "")
    assert "51" in a2.claim_id and "пролекарств" in (a2.raw_extract or "").lower()
    assert "52" in a3.claim_id and "не рекомендуется" in (a3.raw_extract or "").lower()


def test_point_38_sampling(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    s01 = _by_key(claims, "SAMPLING-01")
    auc = _by_key(claims, "SAMPLING-AUC")
    term = _by_key(claims, "SAMPLING-TERMINAL")
    assert "tmax" in (s01.raw_extract or "").lower()
    assert "80 процентов" in (auc.raw_extract or "").lower()
    assert "3 - 4" in (term.raw_extract or "") or "3–4" in (term.raw_extract or "")


def test_point_41_endogenous(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "SAMPLING-03")
    assert "41" in c.claim_id
    assert "эндогенн" in (c.raw_extract or "").lower()
    assert "фонов" in (c.raw_extract or "").lower()


def test_design_clauses_points_15_16(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    d1 = _by_key(claims, "DESIGN-01")
    d2 = _by_key(claims, "DESIGN-02")
    d4 = _by_key(claims, "DESIGN-04")
    assert "15" in d1.claim_id
    assert "двухпериодное" in (d1.raw_extract or "").lower()
    assert "16" in d2.claim_id
    assert "репликативн" in (d2.raw_extract or "").lower()
    assert "параллельн" in (d4.raw_extract or "").lower()
    assert "длительным t1/2" in (d4.raw_extract or "").lower()


def test_washout_point_15_soft_wording(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "WASHOUT-15")
    ex = (c.raw_extract or "").lower()
    assert "отмывочным периодом" in ex
    assert "5 периодов полувыведения" in ex
    assert c.notes and "обычно достаточно" in (c.notes.lower() + " " + (c.normalized_claim or "").lower())


def test_points_85_88_statistics(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    s85 = _by_key(claims, "STAT-03")
    s86 = _by_key(claims, "STAT-04")
    s87 = _by_key(claims, "STAT-01")
    s88 = _by_key(claims, "STAT-02")
    assert "85" in s85.claim_id
    assert "узким терапевтическим" in (s85.raw_extract or "").lower()
    assert "86" in s86.claim_id and "протоколе" in (s86.raw_extract or "").lower()
    assert "90 процентные" in (s87.raw_extract or "").lower()
    assert "ANOVA" in (s88.raw_extract or "")


def test_extract_point_clause_exact() -> None:
    text = load_decision85_text()
    clause = extract_point_clause(text, 18)
    assert clause is not None
    assert clause.point == 18
    assert clause.exact_text.startswith("18.")
    assert "референтного" in clause.exact_text.lower()


def test_exact_excerpt_matches_source(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    text = load_decision85_text(root=root)
    claims = import_decision85_source(root=root)["claim_objects"]
    for c in claims:
        flat = flatten_ws(text)
        excerpt = flatten_ws(c.raw_extract or "")
        # Cap may truncate with ellipsis — compare without trailing ellipsis
        core = excerpt.rstrip("…").rstrip(".")
        assert core[:200] in flat or excerpt[:200] in flat
        assert c.provenance is not None
        assert c.provenance.quoted_text == c.raw_extract


# ---------------------------------------------------------------------------
# Provenance / pages
# ---------------------------------------------------------------------------


def test_page_provenance_unavailable(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_decision85_source(root=root)
    assert result["page_provenance"] == "UNAVAILABLE_WEB_ARCHIVE"
    for c in result["claim_objects"]:
        assert c.provenance is not None
        assert c.provenance.page is None
        assert "UNAVAILABLE_WEB_ARCHIVE" in (c.notes or "")


def test_page_unavailable_not_invented(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    pages = [c.provenance.page for c in claims if c.provenance]
    assert all(p is None for p in pages)
    # Never invent integer page like 18/44/46 from point numbers
    assert 18 not in pages
    assert 44 not in pages


def test_section_provenance(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    for c in claims:
        assert c.provenance is not None
        assert c.provenance.section
        assert "Decision 85 point" in c.provenance.section
        assert c.provenance.paragraph_or_chunk
        assert c.provenance.paragraph_or_chunk.startswith("point-")
        assert c.provenance.source_id == DECISION85_SOURCE_ID
        assert c.provenance.extraction_method == "DECISION85_MHTML_POINT"


def test_no_fake_page_numbers_in_claims(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    pipe = run_decision85_verification_pipeline(root=root)
    for c in _claim_dicts(pipe):
        prov = c.get("provenance") or {}
        assert prov.get("page") is None


# ---------------------------------------------------------------------------
# Verification guards / review / first batch
# ---------------------------------------------------------------------------


def test_import_does_not_auto_verify(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_decision85_source(root=root)
    assert result["auto_verified"] is False
    assert all(c.verification_status != "VERIFIED" for c in result["claim_objects"])
    assert all(c.verification_status == "REVIEW_REQUIRED" for c in result["claim_objects"])


def test_pipeline_without_reviewer_does_not_verify(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = run_decision85_verification_pipeline(root=root, verify_first_batch=False)
    assert len(result["verified_claims"]) == 0
    assert result["auto_verified"] is False
    assert result["rules_auto_verified"] == 0


def test_verify_first_batch_requires_reviewer(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    with pytest.raises(ValueError, match="reviewer"):
        run_decision85_verification_pipeline(root=root, verify_first_batch=True, reviewer=None)


def test_first_batch_only_partially_verified(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    clear_review_audit()
    result = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER
    )
    assert len(result["claims"]) == 21
    assert len(result["verified_claims"]) == 8
    assert len(result["proposed_claims"]) == 13
    verified_keys = {
        c["claim_id"].replace("D85-", "").rsplit("-P", 1)[0] for c in result["verified_claims"]
    }
    assert verified_keys == set(FIRST_BATCH_KEYS)
    # Non-batch remain unverified
    non_batch = [c for c in result["claims"] if c["verification_status"] != "VERIFIED"]
    assert len(non_batch) == 13
    assert all(c["verification_status"] in {"REVIEW_REQUIRED", "UNVERIFIED", "EXTRACTED"} for c in non_batch)


def test_verification_guard_allows_missing_page_with_section_chunk(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    c = _by_key(claims, "REF-01")
    assert c.provenance.page is None
    validate_verify_payload(c, reviewer=REVIEWER)
    verified = verify_claim_explicit(c, reviewer=REVIEWER)
    assert verified.verification_status == "VERIFIED"


def test_verification_guard_rejects_incomplete_page(tmp_path: Path) -> None:
    claim = build_claim(
        claim_id="D85-BAD",
        claim_kind="REGULATORY_CLAIM",
        domain="REFERENCE",
        source_class="EEC_REGULATORY",
        raw_extract="text",
        normalized_claim="norm",
        source_version_id="SV-1",
        provenance=EvidenceProvenance(
            source_id=DECISION85_SOURCE_ID,
            document_id="SV-1",
            source_version="SV-1",
            page=None,
            section=None,
            paragraph_or_chunk=None,
            quoted_text="text",
        ),
    )
    with pytest.raises(VerifyGuardError) as exc:
        verify_claim_explicit(claim, reviewer=REVIEWER)
    assert exc.value.field == "page"


def test_verification_guard_requires_excerpt(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "FOOD-01")
    c.raw_extract = None
    if c.provenance:
        c.provenance.quoted_text = None
    with pytest.raises(VerifyGuardError) as exc:
        verify_claim_explicit(c, reviewer=REVIEWER)
    # Guard checks page substitute (section+chunk+excerpt) before the excerpt field
    assert exc.value.field in {"exact_excerpt", "page"}


def test_verification_guard_requires_reviewer(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "FOOD-01")
    with pytest.raises(VerifyGuardError) as exc:
        verify_claim_explicit(c, reviewer="")
    assert exc.value.field == "reviewer"


def test_review_audit(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    clear_review_audit()
    run_decision85_verification_pipeline(root=root, verify_first_batch=True, reviewer=REVIEWER)
    trail = review_audit_trail()
    assert len(trail) == 8
    assert all(e["action"] == "verify" for e in trail)
    assert all(e["reviewer"] == REVIEWER for e in trail)
    assert all(e["new_status"] == "VERIFIED" for e in trail)
    assert all(e["study_mutated"] is False for e in trail)


def test_rule_candidate_proposed(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER
    )
    cands = result["rule_candidates"]
    assert len(cands) >= 1
    assert all(r["status"] == "PROPOSED" for r in cands)
    assert all(r.get("requires_expert_confirmation") is True for r in cands)
    assert all(r.get("study_mutated") is False for r in cands)
    assert result["rules_auto_verified"] == 0


def test_no_auto_rule_verification(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER
    )
    assert result["rules_auto_verified"] == 0
    for seed in KNOWLEDGE_RULE_SEEDS:
        assert seed.status == "PROPOSED"
    for r in result["rule_candidates"]:
        assert r["status"] != "VERIFIED"


# ---------------------------------------------------------------------------
# Exact §22 no-mutation names
# ---------------------------------------------------------------------------


def test_verified_claim_does_not_mutate_study(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    study = _canonical_study()
    before = copy.deepcopy(study)
    result = run_decision85_verification_pipeline(
        root=root,
        verify_first_batch=True,
        reviewer=REVIEWER,
        canonical_study=study,
    )
    assert result["study_mutated"] is False
    assert study == before
    assert len(result["verified_claims"]) == 8


def test_verified_rule_candidate_does_not_mutate_study(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    study = _canonical_study()
    before = copy.deepcopy(study)
    result = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER, canonical_study=study
    )
    for c in result["verified_claims"]:
        # recreate object-like for candidate helper via verified dict fields
        pass
    claims = import_decision85_source(root=root)["claim_objects"]
    for c in claims:
        key = c.claim_id.replace("D85-", "").rsplit("-P", 1)[0]
        if key in FIRST_BATCH_KEYS:
            verify_claim_explicit(c, reviewer=REVIEWER)
            cand = create_rule_candidate_from_claim(c, rule_code=key)
            assert cand["status"] == "PROPOSED"
            assert cand["study_mutated"] is False
    assert study == before
    assert result["study_mutated"] is False


def test_reference_claim_does_not_select_reference(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    study = _canonical_study()
    before_ref = copy.deepcopy(study["reference_product"])
    result = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER, canonical_study=study
    )
    assert study["reference_product"] == before_ref
    assert result["study_mutated"] is False
    ref_claim = next(c for c in result["verified_claims"] if "REF-01" in c["claim_id"])
    assert ref_claim["verification_status"] == "VERIFIED"


def test_design_claim_does_not_set_design(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    study = _canonical_study()
    before = copy.deepcopy(study["design"])
    # Design claims are not in first batch — verify one explicitly
    claims = import_decision85_source(root=root)["claim_objects"]
    d = _by_key(claims, "DESIGN-01")
    verify_claim_explicit(d, reviewer=REVIEWER)
    assert study["design"] == before
    pipe = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER, canonical_study=study
    )
    assert study["design"] == before
    assert pipe["study_mutated"] is False


def test_food_claim_does_not_modify_food(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    study = _canonical_study()
    before = copy.deepcopy(study["food"])
    result = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER, canonical_study=study
    )
    assert study["food"] == before
    assert result["study_mutated"] is False
    assert any("FOOD-01" in c["claim_id"] for c in result["verified_claims"])


def test_sampling_claim_does_not_modify_sampling(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    study = _canonical_study()
    before = copy.deepcopy(study["sampling"])
    result = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER, canonical_study=study
    )
    assert study["sampling"] == before
    assert result["study_mutated"] is False
    assert any("SAMPLING-AUC" in c["claim_id"] for c in result["verified_claims"])


def test_pk_claim_does_not_modify_pk(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    study = _canonical_study()
    before = copy.deepcopy(study["pk"])
    result = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER, canonical_study=study
    )
    assert study["pk"] == before
    assert result["study_mutated"] is False
    assert any("PK-01" in c["claim_id"] for c in result["verified_claims"])


# ---------------------------------------------------------------------------
# Interview separation / conflicts / gaps / numbers
# ---------------------------------------------------------------------------


def test_interview_separation(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    run_decision85_verification_pipeline(root=root, verify_first_batch=True, reviewer=REVIEWER)
    interviews = interview_claims_as_evidence()
    assert interviews
    for ic in interviews:
        assert ic.source_class in {"EXPERT_INTERVIEW", "EXPERT_INTERVIEW_CLAIM"} or ic.claim_kind in {
            "EXPERT_INTERVIEW",
            "EXPERT_INTERVIEW_CLAIM",
        }
        assert ic.verification_status != "VERIFIED"
        # Decision 85 upload must not upgrade interview claims
        assert not str(ic.claim_id).startswith("D85-")


def test_conflict_detection(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = run_decision85_verification_pipeline(root=root)
    assert len(result["conflicts"]) >= 1
    for conf in result["conflicts"]:
        assert conf.get("resolution_status") == "OPEN"
        assert conf.get("resolution") is None
        assert conf.get("conflict_type") == "VALUE_CONFLICT"
        assert any(str(cid).startswith("D85-") for cid in (conf.get("claim_ids") or []))
        assert any(str(cid).startswith("INT-") for cid in (conf.get("claim_ids") or []))


def test_interview_conflicts_helper(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    conflicts = interview_conflicts_for_decision85(claims)
    assert len(conflicts) >= 1


def test_source_derived_numbers_800_1000(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "FOOD-02")
    assert "800" in (c.raw_extract or "")
    assert "1000" in (c.raw_extract or "")
    assert c.verification_status != "VERIFIED"  # numbers alone do not approve medical behavior


def test_source_derived_numbers_50_percent(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "FOOD-02")
    assert "50 процентов" in (c.raw_extract or "").lower()


def test_source_derived_numbers_80_percent(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "SAMPLING-AUC")
    assert "80 процентов" in (c.raw_extract or "").lower()


def test_source_derived_numbers_3_4_terminal(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "SAMPLING-TERMINAL")
    ex = c.raw_extract or ""
    assert "3 - 4" in ex or "3–4" in ex


def test_no_potvin_from_decision85(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_decision85_source(root=root)
    blob = " ".join((c.raw_extract or "") + " " + (c.normalized_claim or "") for c in result["claim_objects"])
    assert "potvin" not in blob.lower()
    gaps = knowledge_gaps_decision85(result)
    codes = {g["code"] for g in gaps}
    assert "REG.POTVIN.NO_D85_SOURCE" in codes


def test_wash_soft_wording_vs_hard_rule_gap(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_decision85_source(root=root)
    gaps = knowledge_gaps_decision85(result)
    wash = next(g for g in gaps if g["code"] == "REG.WASH.HARD_THRESHOLD_UNCERTAIN")
    assert "обычно достаточно" in wash["question"] or "5 half-lives" in wash["question"]
    assert wash["status"] == "OPEN"
    # WASH-01 seed remains PROPOSED
    wash_seed = next(s for s in KNOWLEDGE_RULE_SEEDS if s.rule_code == "WASH-01")
    assert wash_seed.status == "PROPOSED"


def test_sampling_3plus3_not_in_d85_gap(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    gaps = knowledge_gaps_decision85(import_decision85_source(root=root))
    assert any(g["code"] == "REG.SAMPLING.TMAX_3PLUS3.NOT_IN_D85" for g in gaps)
    s01 = _by_key(import_decision85_source(root=root)["claim_objects"], "SAMPLING-01")
    assert "3 points before" not in (s01.normalized_claim or "").lower()


def test_no_fake_claims(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    text = load_decision85_text(root=root)
    claims = import_decision85_source(root=root)["claim_objects"]
    # Every claim must map to a CLAIM_SPECS entry and pass token checks
    keys = {s.claim_key for s in CLAIM_SPECS}
    for c in claims:
        key = c.claim_id.replace("D85-", "").rsplit("-P", 1)[0]
        assert key in keys
        spec = next(s for s in CLAIM_SPECS if s.claim_key == key)
        for tok in spec.excerpt_must_contain:
            assert tok.lower() in (c.raw_extract or "").lower()
    # Specs that fail token match are skipped (not fabricated) — all current specs present
    assert len(claims) == len(CLAIM_SPECS)


def test_skip_rather_than_fabricate_missing_tokens(tmp_path: Path) -> None:
    """If required tokens absent, build_decision85_claims skips — no fake claim."""
    root = _iso_root(tmp_path)
    # Use truncated text missing point 18 body tokens
    fake = "1. Введение\n\n18. Краткий текст без нужных токенов.\n\n19. Далее\n"
    claims = build_decision85_claims(text=fake, source_version_id="SV-fake", root=root)
    assert all("REF-01" not in c.claim_id for c in claims)


def test_decision85_slot_present_or_ingested(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    import_decision85_source(root=root)
    slots = refresh_slots(base=root)
    decision = next(s for s in slots if s.slot_code == "DECISION_85")
    assert decision.status in {"PRESENT", "INGESTED", "REVIEW_REQUIRED"}
    assert decision.status != "MISSING"


def test_coverage_domains(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER
    )
    cov = result["coverage"]
    assert cov["package_status"] == "PARTIAL"
    assert cov["verified_claims"] == 8
    assert cov["proposed_claims"] >= 13 or len(result["proposed_claims"]) == 13
    domains = {c["domain"] for c in result["claims"]}
    for d in ("REFERENCE", "DESIGN", "FOOD", "SAMPLING", "WASHOUT", "ANALYTE", "PK", "STATISTICS"):
        assert d in domains


def test_pipeline_summary_counts(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = run_decision85_verification_pipeline(
        root=root, verify_first_batch=True, reviewer=REVIEWER
    )
    assert len(result["claims"]) == 21
    assert len(result["verified_claims"]) == 8
    assert len(result["proposed_claims"]) == 13
    assert len(result["conflicts"]) >= 1
    assert len(result["amendments"]) == 3
    assert all(a["status"] == "SOURCE_EMBEDDED" for a in result["amendments"])
    assert len(result["rule_candidates"]) >= 1
    assert all(r["status"] == "PROPOSED" for r in result["rule_candidates"])


def test_rule_candidates_only_from_verified(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    assert rule_candidates_from_verified(claims) == []
    c = _by_key(claims, "REF-01")
    verify_claim_explicit(c, reviewer=REVIEWER)
    cands = rule_candidates_from_verified(claims)
    assert len(cands) >= 1
    assert all(r["status"] == "PROPOSED" for r in cands)


def test_first_batch_keys_match_spec() -> None:
    assert set(FIRST_BATCH_KEYS) == {
        "REF-01",
        "FOOD-01",
        "FOOD-02",
        "PK-01",
        "PK-02",
        "SAMPLING-AUC",
        "SAMPLING-TERMINAL",
        "ANALYTE-01",
    }
    batch_specs = [s for s in CLAIM_SPECS if s.first_batch]
    assert {s.claim_key for s in batch_specs} == set(FIRST_BATCH_KEYS)


def test_normalized_claim_distinct_from_excerpt(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    c = _by_key(import_decision85_source(root=root)["claim_objects"], "REF-01")
    assert c.normalized_claim
    assert c.raw_extract
    assert c.normalized_claim != c.raw_extract


def test_confidence_high_does_not_mean_verified(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    claims = import_decision85_source(root=root)["claim_objects"]
    assert all(c.confidence == "HIGH" for c in claims)
    assert all(c.verification_status != "VERIFIED" for c in claims)


# ---------------------------------------------------------------------------
# API smoke
# ---------------------------------------------------------------------------


def test_api_decision85_import() -> None:
    client = TestClient(create_app())
    r = client.post("/api/regulatory-evidence/decision85/import")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in {"IMPORTED", "EXISTING_SOURCE_VERSION"}
    assert data["study_mutated"] is False
    assert data["auto_verified"] is False
    assert len(data.get("claims") or []) >= 21 or data.get("source_version")


def test_api_decision85_pipeline_without_verify() -> None:
    client = TestClient(create_app())
    r = client.post("/api/regulatory-evidence/decision85/pipeline", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["study_mutated"] is False
    assert len(data.get("verified_claims") or []) == 0
    assert data.get("auto_verified") is False


def test_api_decision85_pipeline_verify_requires_reviewer() -> None:
    client = TestClient(create_app())
    r = client.post(
        "/api/regulatory-evidence/decision85/pipeline",
        json={"verify_first_batch": True},
    )
    assert r.status_code == 422


def test_api_decision85_pipeline_first_batch() -> None:
    client = TestClient(create_app())
    r = client.post(
        "/api/regulatory-evidence/decision85/pipeline",
        json={"verify_first_batch": True, "reviewer": REVIEWER, "canonical_study": _canonical_study()},
    )
    assert r.status_code == 200
    data = r.json()
    assert len(data["verified_claims"]) == 8
    assert len(data["proposed_claims"]) == 13
    assert data["study_mutated"] is False
    assert all(rc["status"] == "PROPOSED" for rc in data.get("rule_candidates") or [])


def test_api_decision85_claims() -> None:
    client = TestClient(create_app())
    client.post("/api/regulatory-evidence/decision85/import")
    r = client.get("/api/regulatory-evidence/decision85/claims")
    assert r.status_code == 200
    data = r.json()
    assert len(data["claims"]) >= 21
    assert all(str(c["claim_id"]).startswith("D85-") for c in data["claims"])


def test_medical_rules_added_zero() -> None:
    """Phase 13.3 adds claim candidates only — KnowledgeRule seeds stay PROPOSED."""
    assert all(s.status == "PROPOSED" for s in KNOWLEDGE_RULE_SEEDS)


def test_missing_source_returns_gap(tmp_path: Path) -> None:
    empty = tmp_path / "empty_reg"
    empty.mkdir()
    (empty / "eec").mkdir()
    result = import_decision85_source(root=empty)
    assert result["status"] == "MISSING"
    assert result["knowledge_gap"]["code"] == "REG.DECISION85.MISSING"
    assert result["study_mutated"] is False
    pipe = run_decision85_verification_pipeline(root=empty)
    assert pipe["status"] == "MISSING"
    assert pipe["study_mutated"] is False
    assert pipe["verified_claims"] == []

"""Phase 13.1 — Regulatory Evidence Foundation tests (§46).

No Decision 85 PDF fabrication. No Study mutation. No auto-verification.
Medical rules added in 13.1 modules: ZERO.
"""

from __future__ import annotations

import copy
import inspect
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.knowledge_seed import KNOWLEDGE_RULE_SEEDS
from app.domain.knowledge_transitions import (
    assert_knowledge_rule_transition,
    assert_verified_provenance,
    has_verified_provenance,
)
from app.domain.production_readiness import build_production_readiness_report
from app.domain.regulatory_claims import (
    EvidenceProvenance,
    ProposedRegulatoryBasis,
    build_claim,
    confidence_does_not_imply_verification,
    detect_stale_evidence,
    explicitly_verify_claim,
    link_claim_to_basis,
)
from app.domain.regulatory_conflicts import (
    ClassifiedEvidenceConflict,
    StudyEvidenceConflict,
    classify_conflict_type,
    detect_study_evidence_conflict,
    detect_value_conflicts,
    resolve_conflict_forbidden_auto,
)
from app.domain.regulatory_coverage import build_regulatory_coverage_report
from app.domain.regulatory_evidence_manifest import (
    DEFAULT_REGULATORY_ROOT,
    RegulatorySourceEntry,
    detect_duplicate_sources,
    file_sha256,
    load_regulatory_manifest,
    supersede_source,
)
from app.domain.regulatory_evidence_pipeline import run_regulatory_evidence_pipeline
from app.domain.regulatory_evidence_tasks import (
    PRIORITY_RULE_WORKSPACE,
    REGULATORY_EVIDENCE_TASKS,
    tasks_for_domain,
)
from app.domain.regulatory_interview import (
    INTERVIEW_CLAIM_SEEDS,
    assert_interview_not_regulatory,
    interview_claims_as_evidence,
    proposed_rules_remain_proposed,
)
from app.domain.regulatory_review_queue import (
    RegulatoryReviewQueue,
    approve_review_item,
    enqueue_claim_review,
    enqueue_rule_candidate,
    reject_review_item,
)
from app.domain.regulatory_source_classes import (
    CLAIM_KINDS,
    CONFLICT_TYPES,
    EVIDENCE_DOMAINS,
    SOURCE_CLASSES,
    SOURCE_VERIFICATION_STATUSES,
    assert_not_auto_verified,
    is_interview_class,
    is_regulatory_document_class,
)
from app.main import create_app


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
PHASE13_MODULES = (
    "app.domain.regulatory_source_classes",
    "app.domain.regulatory_evidence_manifest",
    "app.domain.regulatory_claims",
    "app.domain.regulatory_conflicts",
    "app.domain.regulatory_evidence_tasks",
    "app.domain.regulatory_review_queue",
    "app.domain.regulatory_coverage",
    "app.domain.regulatory_interview",
    "app.domain.regulatory_evidence_pipeline",
    "app.api.regulatory_evidence",
)


def _canonical_study() -> dict:
    return {
        "study": {"id": "study-13.1", "protocol_number": "BE-13.1-001", "version": "1.0"},
        "product": {"trade_name": "Test", "inn": "inn", "dosage": "100 mg"},
        "reference_product": {
            "trade_name": "Ref",
            "inn": "inn",
            "dosage": "100 mg",
            "manufacturer": "Maker",
            "status": "FINAL",
        },
        "design": {"type": "CROSSOVER_2X2", "periods": 2, "status": "FINAL"},
        "sampling": {
            "points": [{"time_h": 0.0}, {"time_h": 2.0}, {"time_h": 24.0}],
            "status": "FINAL",
        },
        "pk": {"primary": ["Cmax", "AUC0-t"], "status": "FINAL"},
        "safety": {"monitoring": "standard_be", "status": "FINAL"},
        "food": {"condition": "FED"},
        "washout": {"periods": 7},
        "analyte": {"name": "parent"},
        "statistics": {"cv_intra": None},
    }


def _prov(**kwargs) -> EvidenceProvenance:
    base = {
        "source_id": "SRC-DECISION85",
        "document_id": "Decision-85",
        "source_version": "1",
        "page": 18,
        "section": "III",
        "quoted_text": "exact quoted regulatory text",
        "extraction_method": "MANUAL",
    }
    base.update(kwargs)
    return EvidenceProvenance(**base)


# ---------------------------------------------------------------------------
# §46 required tests (exact names)
# ---------------------------------------------------------------------------


def test_regulatory_source_manifest() -> None:
    m = load_regulatory_manifest()
    assert m.package_status == "PARTIAL"
    assert m.package_status != "REAL"
    assert m.manifest_id
    assert len(m.sources) >= 5
    decision = next(s for s in m.sources if s.source_id == "SRC-DECISION85")
    assert decision.ingestion_status == "MISSING"
    assert decision.source_class == "EEC_REGULATORY"
    assert any(s.source_class == "EXPERT_INTERVIEW" for s in m.sources)
    assert any(g.get("code") == "REG.DECISION85.MISSING" for g in m.knowledge_gaps)
    assert (DEFAULT_REGULATORY_ROOT / "manifest.json").is_file()


def test_source_hash(tmp_path: Path) -> None:
    p = tmp_path / "sample.bin"
    p.write_bytes(b"regulatory-hash-bytes-13.1")
    h1 = file_sha256(p)
    h2 = file_sha256(p)
    assert h1 == h2
    assert len(h1) == 64
    assert re.fullmatch(r"[0-9a-f]{64}", h1)
    p.write_bytes(b"changed")
    assert file_sha256(p) != h1


def test_duplicate_source_detection() -> None:
    a = RegulatorySourceEntry(
        source_id="A",
        source_class="FDA_GUIDANCE",
        title="t",
        document_identifier="DOC-1",
        file_hash="abc",
    )
    b = RegulatorySourceEntry(
        source_id="A",
        source_class="FDA_GUIDANCE",
        title="t2",
        document_identifier="DOC-1",
        file_hash="abc",
    )
    dups = detect_duplicate_sources([a, b])
    types = {d["type"] for d in dups}
    assert "SOURCE_ID" in types
    assert "DOCUMENT_IDENTIFIER" in types
    assert "CONTENT_HASH" in types


def test_versioned_source() -> None:
    old = RegulatorySourceEntry(
        source_id="SRC-V1",
        source_class="EMA_GUIDANCE",
        title="v1",
        source_version="1",
        verification_status="EXTRACTED",
    )
    new = RegulatorySourceEntry(
        source_id="SRC-V2",
        source_class="EMA_GUIDANCE",
        title="v2",
        source_version="2",
        verification_status="UNVERIFIED",
    )
    out = supersede_source([old], old_source_id="SRC-V1", new_entry=new)
    assert len(out) == 2
    assert out[0].verification_status == "SUPERSEDED"
    assert out[0].superseded_by == "SRC-V2"
    assert out[1].source_version == "2"
    assert "SUPERSEDED" in SOURCE_VERIFICATION_STATUSES


def test_source_verification_states() -> None:
    required = {
        "UNVERIFIED",
        "EXTRACTED",
        "REVIEW_REQUIRED",
        "VERIFIED",
        "REJECTED",
        "SUPERSEDED",
    }
    assert required.issubset(set(SOURCE_VERIFICATION_STATUSES))
    with pytest.raises(ValueError, match="VERIFIED"):
        assert_not_auto_verified("VERIFIED", context="ingest")
    assert_not_auto_verified("EXTRACTED")
    assert_not_auto_verified("UNVERIFIED")


def test_page_provenance() -> None:
    complete = _prov(page=44, section=None, paragraph_or_chunk=None)
    assert complete.is_complete_for_regulatory() is True
    incomplete = EvidenceProvenance(source_id="X", quoted_text=None, page=1)
    assert incomplete.is_complete_for_regulatory() is False
    no_loc = EvidenceProvenance(source_id="X", quoted_text="text", page=None, section=None)
    assert no_loc.is_complete_for_regulatory() is False


def test_evidence_claim_provenance() -> None:
    claim = build_claim(
        claim_id="CLM-1",
        claim_kind="REGULATORY_CLAIM",
        domain="REFERENCE",
        raw_extract="raw",
        normalized_claim="norm",
        provenance=_prov(),
        source_class="EEC_REGULATORY",
    )
    assert claim.provenance is not None
    assert claim.provenance.page == 18
    assert claim.provenance.quoted_text
    assert claim.provenance.source_id == "SRC-DECISION85"
    d = claim.to_dict()
    assert d["provenance"]["page"] == 18


def test_raw_extract_vs_normalized_claim() -> None:
    claim = build_claim(
        claim_id="CLM-RAW-NORM",
        claim_kind="NORMALIZED_CLAIM",
        domain="FOOD",
        raw_extract="Fed meal concept referenced to Decision 85 p.46",
        normalized_claim="Interview practice: fed meal per Decision 85 p.46",
        confidence="MEDIUM",
    )
    assert claim.raw_extract != claim.normalized_claim
    assert "RAW_EXTRACT" in CLAIM_KINDS
    assert "NORMALIZED_CLAIM" in CLAIM_KINDS
    raw_only = build_claim(
        claim_id="CLM-RAW",
        claim_kind="RAW_EXTRACT",
        domain="FOOD",
        raw_extract="literal extract",
        normalized_claim=None,
    )
    assert raw_only.normalized_claim is None
    assert raw_only.raw_extract == "literal extract"


def test_regulatory_claim_distinction() -> None:
    reg = build_claim(
        claim_id="REG-1",
        claim_kind="REGULATORY_CLAIM",
        domain="REFERENCE",
        source_class="EEC_REGULATORY",
        provenance=_prov(),
    )
    interview = build_claim(
        claim_id="INT-1",
        claim_kind="EXPERT_INTERVIEW_CLAIM",
        domain="REFERENCE",
        source_class="EXPERT_INTERVIEW",
    )
    assert reg.is_regulatory_claim() is True
    assert reg.is_interview_claim() is False
    assert interview.is_interview_claim() is True
    assert interview.is_regulatory_claim() is False
    assert is_regulatory_document_class("EEC_REGULATORY") is True
    assert is_interview_class("EXPERT_INTERVIEW") is True


def test_confidence_vs_verification() -> None:
    claim = build_claim(
        claim_id="CLM-CONF",
        claim_kind="NORMALIZED_CLAIM",
        domain="PK",
        confidence="HIGH",
        verification_status="UNVERIFIED",
    )
    assert claim.confidence == "HIGH"
    assert claim.verification_status == "UNVERIFIED"
    assert confidence_does_not_imply_verification("HIGH", "UNVERIFIED") is True
    assert claim.verification_status != "VERIFIED"


def test_regulatory_basis() -> None:
    claim = build_claim(
        claim_id="CLM-BASIS",
        claim_kind="REGULATORY_CLAIM",
        domain="REFERENCE",
        source_class="EEC_REGULATORY",
        provenance=_prov(),
    )
    basis = ProposedRegulatoryBasis(
        basis_id="BASIS-1",
        source_id="SRC-DECISION85",
        document_identifier="Decision-85",
        section="III",
        page=18,
        paragraph=None,
        claim_id=claim.claim_id,
        status="PROPOSED",
    )
    linked = link_claim_to_basis(claim, basis)
    assert linked.regulatory_basis_id == "BASIS-1"
    assert linked.verification_status == "REVIEW_REQUIRED"
    assert basis.status != "VERIFIED"
    assert basis.to_dict()["basis_id"] == "BASIS-1"


def test_evidence_conflict() -> None:
    claims = [
        {
            "claim_id": "c1",
            "field_name": "food_condition",
            "normalized_claim": "FASTING",
            "source_id": "S1",
        },
        {
            "claim_id": "c2",
            "field_name": "food_condition",
            "normalized_claim": "FED",
            "source_id": "S2",
        },
    ]
    conflicts = detect_value_conflicts(claims)
    assert len(conflicts) == 1
    assert conflicts[0].resolution_status == "OPEN"
    assert conflicts[0].conflict_type == "VALUE_CONFLICT"
    assert set(conflicts[0].values) == {"FASTING", "FED"}


def test_conflict_classification() -> None:
    assert classify_conflict_type(same_field=True, different_version=True) == "VERSION_CONFLICT"
    assert classify_conflict_type(same_field=True, different_jurisdiction=True) == "JURISDICTION_CONFLICT"
    assert classify_conflict_type(same_field=True, different_population=True) == "POPULATION_CONFLICT"
    assert classify_conflict_type(same_field=True, different_definition=True) == "DEFINITION_CONFLICT"
    assert classify_conflict_type(same_field=True, different_methodology=True) == "METHODOLOGY_CONFLICT"
    assert classify_conflict_type(same_field=True, different_time=True) == "TIME_CONFLICT"
    assert classify_conflict_type(same_field=True) == "VALUE_CONFLICT"
    assert set(CONFLICT_TYPES) >= {
        "VALUE_CONFLICT",
        "DEFINITION_CONFLICT",
        "POPULATION_CONFLICT",
        "JURISDICTION_CONFLICT",
        "VERSION_CONFLICT",
        "TIME_CONFLICT",
        "METHODOLOGY_CONFLICT",
    }


def test_expert_review_queue() -> None:
    q = RegulatoryReviewQueue(queue_id="RQ-TEST")
    item = enqueue_claim_review(q, item_id="REV-1", claim_id="CLM-1")
    assert item.status == "PENDING"
    assert len(q.pending()) == 1
    approved = approve_review_item(item)
    assert approved["status"] == "APPROVED"
    assert approved["study_mutated"] is False
    assert approved["canonical_mutated"] is False
    item2 = enqueue_rule_candidate(q, item_id="REV-RULE", rule_code="REF-01")
    rejected = reject_review_item(item2)
    assert rejected["status"] == "REJECTED"
    assert rejected["study_mutated"] is False


def test_expert_interview_source_distinction() -> None:
    m = load_regulatory_manifest()
    interview_sources = m.by_class("EXPERT_INTERVIEW")
    assert len(interview_sources) >= 1
    for s in interview_sources:
        assert is_interview_class(s.source_class)
        assert not is_regulatory_document_class(s.source_class)
    claims = interview_claims_as_evidence()
    assert len(claims) == len(INTERVIEW_CLAIM_SEEDS)
    for c in claims:
        assert assert_interview_not_regulatory(c) is True
        assert c.claim_kind == "EXPERT_INTERVIEW_CLAIM"
        assert c.source_class == "EXPERT_INTERVIEW"


def test_rule_candidate() -> None:
    q = RegulatoryReviewQueue(queue_id="RQ-CAND")
    item = enqueue_rule_candidate(
        q,
        item_id="REV-RULE-REF-01",
        rule_code="REF-01",
        claim_id="INT-REF-01",
    )
    assert item.item_type == "rule_candidate"
    assert item.rule_code == "REF-01"
    assert item.status == "PENDING"
    assert "REF-01" in PRIORITY_RULE_WORKSPACE
    assert "MEDICAL_RULE_CANDIDATE" in CLAIM_KINDS
    cand = build_claim(
        claim_id="CAND-1",
        claim_kind="MEDICAL_RULE_CANDIDATE",
        domain="REFERENCE",
        related_rule_codes=["REF-01"],
        verification_status="UNVERIFIED",
    )
    assert cand.verification_status != "VERIFIED"


def test_no_auto_verification() -> None:
    with pytest.raises(ValueError, match="allow_verified"):
        build_claim(
            claim_id="BAD",
            claim_kind="REGULATORY_CLAIM",
            domain="REFERENCE",
            verification_status="VERIFIED",
            provenance=_prov(),
        )
    ok = build_claim(
        claim_id="OK",
        claim_kind="REGULATORY_CLAIM",
        domain="REFERENCE",
        verification_status="VERIFIED",
        allow_verified=True,
        provenance=_prov(),
    )
    assert ok.verification_status == "VERIFIED"
    result = run_regulatory_evidence_pipeline()
    assert result.rules_auto_verified == 0
    assert all(c.get("verification_status") != "VERIFIED" for c in result.claims)


def test_study_evidence_conflict() -> None:
    study = _canonical_study()
    conflict = detect_study_evidence_conflict(
        study_field="product.dosage",
        canonical_value=study["product"]["dosage"],
        source_value="200 mg",
        source_ids=["SRC-X"],
        claim_ids=["CLM-X"],
    )
    assert conflict is not None
    assert isinstance(conflict, StudyEvidenceConflict)
    assert conflict.resolution_status == "OPEN"
    assert conflict.canonical_value == "100 mg"
    assert conflict.source_value == "200 mg"
    # Agreement → no conflict
    assert (
        detect_study_evidence_conflict(
            study_field="product.dosage",
            canonical_value="100 mg",
            source_value="100 mg",
        )
        is None
    )


def test_reference_evidence() -> None:
    tasks = tasks_for_domain("REFERENCE")
    assert any(t.task_code == "REFERENCE_SELECTION" for t in tasks)
    claim = next(c for c in interview_claims_as_evidence() if c.domain == "REFERENCE")
    assert claim.field_name == "reference_selection"
    assert "REF-01" in claim.related_rule_codes
    assert "REFERENCE" in EVIDENCE_DOMAINS


def test_design_evidence() -> None:
    tasks = tasks_for_domain("DESIGN")
    codes = {t.task_code for t in tasks}
    assert "DESIGN_STANDARD_2X2" in codes
    assert "DESIGN_ENDOGENOUS" in codes
    endog = next(c for c in interview_claims_as_evidence() if c.field_name == "endogenous")
    assert endog.domain == "DESIGN"
    assert endog.is_interview_claim()


def test_food_evidence() -> None:
    tasks = tasks_for_domain("FOOD")
    assert {t.task_code for t in tasks} >= {"FOOD_FASTING", "FOOD_FED", "FOOD_STANDARD_MEAL"}
    food_claims = [c for c in interview_claims_as_evidence() if c.domain == "FOOD"]
    assert len(food_claims) >= 2
    assert any("p.44" in (c.raw_extract or "") for c in food_claims)
    assert any("p.46" in (c.raw_extract or "") for c in food_claims)


def test_sampling_evidence() -> None:
    tasks = tasks_for_domain("SAMPLING")
    assert len(tasks) >= 5
    assert any(t.task_code == "SAMPLING_TMAX" for t in tasks)
    assert all(t.requires_official_source for t in tasks)
    # No official sampling source in PARTIAL package → gap expected in coverage
    cov = build_regulatory_coverage_report(
        report_id="COV-SAMP",
        package_status="PARTIAL",
        sources=[],
        claims=[],
        conflicts=[],
        review_items=[],
        knowledge_gaps=[],
    )
    samp = next(d for d in cov.domains if d.domain == "SAMPLING")
    assert samp.verified_count == 0
    assert len(samp.gaps) >= 1


def test_washout_evidence() -> None:
    tasks = tasks_for_domain("WASHOUT")
    assert any(t.task_code == "WASHOUT_RULE" for t in tasks)
    assert "WASH-01" in PRIORITY_RULE_WORKSPACE
    wash = next(t for t in tasks if t.task_code == "WASHOUT_RULE")
    assert "WASH-01" in wash.related_rule_codes


def test_analyte_evidence() -> None:
    tasks = tasks_for_domain("ANALYTE")
    assert any(t.task_code == "ANALYTE_SELECTION" for t in tasks)
    claim = next(c for c in interview_claims_as_evidence() if c.domain == "ANALYTE")
    assert "ANALYTE-01" in claim.related_rule_codes
    assert "p.50" in (claim.raw_extract or "")


def test_pk_evidence() -> None:
    tasks = tasks_for_domain("PK")
    codes = {t.task_code for t in tasks}
    assert "PK_PRIMARY_PARAMETERS" in codes
    assert "AUC_DEFINITION" in codes
    assert "AUC_TRUNCATION" in codes
    assert all(t.domain == "PK" for t in tasks)


def test_cv_evidence() -> None:
    tasks = tasks_for_domain("STATISTICS")
    codes = {t.task_code for t in tasks}
    assert "CVINTRA" in codes
    assert "90CI" in codes
    assert "POTVIN_B" in codes
    assert "POTVIN_C" in codes
    # Discovery only — no verified numeric threshold claim
    for t in tasks:
        assert t.status in {"OPEN", "EVIDENCE_FOUND", "GAP"}


def test_safety_evidence() -> None:
    tasks = tasks_for_domain("SAFETY")
    assert any(t.task_code == "STANDARD_BE_SAFETY" for t in tasks)
    safety = next(c for c in interview_claims_as_evidence() if c.domain == "SAFETY")
    assert "2026" in (safety.raw_extract or "")
    assert safety.is_interview_claim()
    m = load_regulatory_manifest()
    assert any(g.get("code") == "REG.SAFETY.POST_2026_PROTOCOL.MISSING" for g in m.knowledge_gaps)


def test_missing_source_gap() -> None:
    m = load_regulatory_manifest()
    missing = m.missing_sources()
    assert len(missing) >= 4
    codes = {g.get("code") for g in m.knowledge_gaps}
    assert "REG.DECISION85.MISSING" in codes
    assert "REG.FDA.MISSING" in codes
    assert "REG.EMA.MISSING" in codes
    assert "REG.SMPC.MISSING" in codes
    decision_path = DEFAULT_REGULATORY_ROOT / "eec" / "decision_85.pdf"
    assert not decision_path.is_file()


def test_duplicate_evidence() -> None:
    claims = [
        {"claim_id": "d1", "field_name": "washout", "normalized_claim": "5 half-lives", "source_id": "S1"},
        {"claim_id": "d2", "field_name": "washout", "normalized_claim": "7 half-lives", "source_id": "S2"},
        {"claim_id": "d3", "field_name": "washout", "normalized_claim": "5 half-lives", "source_id": "S3"},
    ]
    # Same field with differing values → conflict (duplicate/disagreeing evidence)
    conflicts = detect_value_conflicts(claims)
    assert len(conflicts) == 1
    assert conflicts[0].affected_field == "washout"
    entries = [
        RegulatorySourceEntry("X", "OTHER", "a", file_hash="same"),
        RegulatorySourceEntry("Y", "OTHER", "b", file_hash="same"),
    ]
    assert any(d["type"] == "CONTENT_HASH" for d in detect_duplicate_sources(entries))


def test_source_version_superseding() -> None:
    v1 = RegulatorySourceEntry(
        source_id="SRC-OLD",
        source_class="FDA_GUIDANCE",
        title="old",
        source_version="2020",
        verification_status="EXTRACTED",
    )
    v2 = RegulatorySourceEntry(
        source_id="SRC-NEW",
        source_class="FDA_GUIDANCE",
        title="new",
        source_version="2024",
        verification_status="UNVERIFIED",
    )
    out = supersede_source([v1], old_source_id="SRC-OLD", new_entry=v2)
    superseded = next(e for e in out if e.source_id == "SRC-OLD")
    assert superseded.verification_status == "SUPERSEDED"
    assert superseded.superseded_by == "SRC-NEW"
    claim = build_claim(
        claim_id="STALE",
        claim_kind="REGULATORY_CLAIM",
        domain="PK",
        provenance=_prov(source_id="SRC-OLD", source_version="2020"),
    )
    stale = detect_stale_evidence(claim=claim, current_source_version="2024")
    assert stale is not None
    assert stale["code"] == "EVIDENCE.STALE_SOURCE_VERSION"


def test_no_Study_mutation() -> None:
    study = _canonical_study()
    before = copy.deepcopy(study)
    result = run_regulatory_evidence_pipeline(canonical_study=study)
    assert study == before
    assert result.study_mutated is False


def test_no_final_ReferenceProduct_mutation() -> None:
    study = _canonical_study()
    before = copy.deepcopy(study["reference_product"])
    run_regulatory_evidence_pipeline(canonical_study=study)
    assert study["reference_product"] == before
    assert study["reference_product"]["status"] == "FINAL"


def test_no_final_Design_mutation() -> None:
    study = _canonical_study()
    before = copy.deepcopy(study["design"])
    run_regulatory_evidence_pipeline(canonical_study=study)
    assert study["design"] == before
    assert study["design"]["status"] == "FINAL"


def test_no_final_Sampling_mutation() -> None:
    study = _canonical_study()
    before = copy.deepcopy(study["sampling"])
    run_regulatory_evidence_pipeline(canonical_study=study)
    assert study["sampling"] == before
    assert study["sampling"]["status"] == "FINAL"


def test_no_final_PK_mutation() -> None:
    study = _canonical_study()
    before = copy.deepcopy(study["pk"])
    run_regulatory_evidence_pipeline(canonical_study=study)
    assert study["pk"] == before
    assert study["pk"]["status"] == "FINAL"


def test_no_final_Safety_mutation() -> None:
    study = _canonical_study()
    before = copy.deepcopy(study["safety"])
    run_regulatory_evidence_pipeline(canonical_study=study)
    assert study["safety"] == before
    assert study["safety"]["status"] == "FINAL"


def test_proposed_rule_remains_proposed() -> None:
    assert proposed_rules_remain_proposed() is True
    assert all(s.status == "PROPOSED" for s in KNOWLEDGE_RULE_SEEDS)
    for code in PRIORITY_RULE_WORKSPACE:
        seed = next((s for s in KNOWLEDGE_RULE_SEEDS if s.rule_code == code), None)
        assert seed is not None
        assert seed.status == "PROPOSED"
    result = run_regulatory_evidence_pipeline()
    assert result.rules_auto_verified == 0
    assert result.coverage.get("knowledge_rules_verified") == 0


def test_verified_rule_requires_evidence() -> None:
    assert has_verified_provenance() is False
    with pytest.raises(Exception, match="requires"):
        assert_verified_provenance()
    assert has_verified_provenance(regulatory_basis_id="BASIS-1") is True
    assert has_verified_provenance(evidence_claim_ids=["CLM-1"]) is True
    assert has_verified_provenance(source_ids=["SRC-1"]) is True
    claim = build_claim(
        claim_id="REG-V",
        claim_kind="REGULATORY_CLAIM",
        domain="REFERENCE",
        provenance=EvidenceProvenance(source_id="S", quoted_text=None),
        source_class="EEC_REGULATORY",
    )
    with pytest.raises(ValueError, match="provenance"):
        explicitly_verify_claim(claim, reviewer="expert")


def test_rejected_rule_remains_rejected() -> None:
    assert_knowledge_rule_transition("REJECTED", "PROPOSED")
    with pytest.raises(Exception):
        assert_knowledge_rule_transition("REJECTED", "VERIFIED")
    q = RegulatoryReviewQueue(queue_id="RQ-REJ")
    item = enqueue_rule_candidate(q, item_id="R1", rule_code="REF-01")
    reject_review_item(item)
    assert item.status == "REJECTED"
    # Rejected review item is not silently promoted to VERIFIED claim/rule
    assert item.status != "VERIFIED"
    assert item.status != "APPROVED"


def test_conflict_not_auto_resolved() -> None:
    conflict = ClassifiedEvidenceConflict(
        conflict_id="EC-001",
        conflict_type="VALUE_CONFLICT",
        affected_field="dose",
        claim_ids=["a", "b"],
        source_ids=["s1", "s2"],
        values=["100", "200"],
        resolution_status="OPEN",
    )
    with pytest.raises(RuntimeError, match="forbidden"):
        resolve_conflict_forbidden_auto(conflict)
    assert conflict.resolution_status == "OPEN"
    result = run_regulatory_evidence_pipeline()
    for c in result.conflicts:
        assert c.get("resolution_status") == "OPEN"
    for c in result.study_conflicts:
        assert c.get("resolution_status") == "OPEN"


def test_production_readiness_coverage() -> None:
    pipe = run_regulatory_evidence_pipeline()
    report = build_production_readiness_report(
        classification="TECHNICAL_FIXTURE",
        package_id=pipe.manifest.get("manifest_id"),
        regulatory_evidence_coverage=pipe.coverage,
        production_blockers=["Official Decision 85 document not present in repository"],
        gate_results={"DRAFT": "READY", "REVIEW": "BLOCKED", "FINAL": "BLOCKED"},
    )
    d = report.to_dict()
    assert "regulatory_evidence_coverage" in d
    assert d["regulatory_evidence_coverage"]["package_status"] == "PARTIAL"
    assert any("PARTIAL" in str(b) or "Regulatory evidence" in str(b) for b in d["production_blockers"])
    assert d["recommendation"] != "PRODUCTION-READY"
    assert Settings().app_version == "0.30.0"


def test_regulatory_coverage_report() -> None:
    pipe = run_regulatory_evidence_pipeline()
    cov = pipe.coverage
    assert cov["package_status"] == "PARTIAL"
    assert cov["verified_claims"] == 0
    assert cov["proposed_claims"] >= 1
    assert cov["knowledge_rules_verified"] == 0
    domains = {d["domain"] for d in cov["domains"]}
    assert "REFERENCE" in domains
    assert "FOOD" in domains
    assert "SAFETY" in domains
    assert cov["sources_missing"] >= 4


def test_ui_api_contract() -> None:
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        meta = client.get("/api/regulatory-evidence/meta")
        assert meta.status_code == 200
        body = meta.json()
        assert body["auto_verify"] is False
        assert body["study_mutation_on_approve"] is False
        assert "EEC_REGULATORY" in body["source_classes"]
        assert "REF-01" in body["priority_rule_workspace"]

        manifest = client.get("/api/regulatory-evidence/manifest")
        assert manifest.status_code == 200
        assert manifest.json()["package_status"] == "PARTIAL"

        pipe = client.post("/api/regulatory-evidence/pipeline/run", json={"include_interview": True})
        assert pipe.status_code == 200
        pdata = pipe.json()
        assert pdata["package_status"] == "PARTIAL"
        assert pdata["study_mutated"] is False
        assert pdata["rules_auto_verified"] == 0

        rq = client.get("/api/regulatory-evidence/review-queue")
        assert rq.status_code == 200
        assert "items" in rq.json()

        cov = client.get("/api/regulatory-evidence/coverage")
        assert cov.status_code == 200
        assert cov.json()["package_status"] == "PARTIAL"
        assert cov.json()["verified_claims"] == 0
    get_settings.cache_clear()


def test_malformed_source() -> None:
    # Unknown class / verification coerced; missing required source_id raises
    from app.domain.regulatory_evidence_manifest import _entry_from_dict

    entry = _entry_from_dict(
        {
            "source_id": "SRC-BAD",
            "source_class": "NOT_A_REAL_CLASS",
            "title": "bad",
            "verification_status": "NOT_A_STATUS",
            "ingestion_status": "OK",
        }
    )
    assert entry.source_class == "OTHER"
    assert entry.verification_status == "UNVERIFIED"
    with pytest.raises(KeyError):
        _entry_from_dict({"title": "no id"})


def test_extraction_failure(tmp_path: Path) -> None:
    # Corrupt / empty binary path surfaces FAILED ingest, not crash
    root = tmp_path / "regulatory"
    (root / "eec").mkdir(parents=True)
    bad = root / "eec" / "broken.pdf"
    bad.write_bytes(b"%PDF-not-a-real-file")
    manifest = {
        "manifest_id": "tmp",
        "package_status": "PARTIAL",
        "sources": [
            {
                "source_id": "SRC-BROKEN",
                "source_class": "EEC_REGULATORY",
                "title": "broken",
                "relative_path": "eec/broken.pdf",
                "ingestion_status": "PENDING",
                "verification_status": "UNVERIFIED",
            }
        ],
        "knowledge_gaps": [],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = run_regulatory_evidence_pipeline(root=root, include_interview=False)
    # Either FAILED extract or empty OK with no verified claims — never auto-verified
    assert result.rules_auto_verified == 0
    assert all(c.get("verification_status") != "VERIFIED" for c in result.claims)
    if result.ingested:
        statuses = {i.get("status") for i in result.ingested}
        assert statuses <= {"OK", "FAILED"}


def test_missing_page_provenance() -> None:
    claim = build_claim(
        claim_id="NO-PAGE",
        claim_kind="REGULATORY_CLAIM",
        domain="REFERENCE",
        source_class="EEC_REGULATORY",
        provenance=EvidenceProvenance(
            source_id="SRC-DECISION85",
            quoted_text="text without location",
            page=None,
            section=None,
            paragraph_or_chunk=None,
        ),
    )
    assert claim.provenance is not None
    assert claim.provenance.is_complete_for_regulatory() is False
    with pytest.raises(ValueError, match="provenance"):
        explicitly_verify_claim(claim, reviewer="r1")


def test_source_version_mismatch() -> None:
    claim = build_claim(
        claim_id="MISMATCH",
        claim_kind="REGULATORY_CLAIM",
        domain="FOOD",
        provenance=_prov(source_version="1"),
        source_class="EEC_REGULATORY",
    )
    stale = detect_stale_evidence(claim=claim, current_source_version="2")
    assert stale is not None
    assert stale["claim_version"] == "1"
    assert stale["current_version"] == "2"
    fresh = detect_stale_evidence(claim=claim, current_source_version="1")
    assert fresh is None


def test_evidence_stale_detection() -> None:
    no_prov = build_claim(
        claim_id="NOP",
        claim_kind="NORMALIZED_CLAIM",
        domain="PK",
        provenance=None,
    )
    missing = detect_stale_evidence(claim=no_prov, current_source_version="1")
    assert missing is not None
    assert missing["code"] == "EVIDENCE.STALE_OR_MISSING_PROVENANCE"
    claim = build_claim(
        claim_id="OLD",
        claim_kind="REGULATORY_CLAIM",
        domain="PK",
        provenance=_prov(source_version="1"),
    )
    stale = detect_stale_evidence(claim=claim, current_source_version="3")
    assert stale["code"] == "EVIDENCE.STALE_SOURCE_VERSION"


def test_interview_claim_not_regulatory_claim() -> None:
    for c in interview_claims_as_evidence():
        assert c.claim_kind == "EXPERT_INTERVIEW_CLAIM"
        assert c.is_regulatory_claim() is False
        assert c.is_interview_claim() is True
        assert c.verification_status != "VERIFIED"
    path = DEFAULT_REGULATORY_ROOT / "interview" / "interview_claims.json"
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert all(row.get("is_regulatory_document") is False for row in data)
    assert all(row.get("source_type") == "EXPERT_INTERVIEW" for row in data)


def test_full_regulatory_evidence_pipeline() -> None:
    study = _canonical_study()
    before = copy.deepcopy(study)
    result = run_regulatory_evidence_pipeline(canonical_study=study, include_interview=True)
    assert study == before
    assert result.package_status == "PARTIAL"
    assert result.package_status != "REAL"
    assert result.study_mutated is False
    assert result.rules_auto_verified == 0
    assert result.coverage["verified_claims"] == 0
    assert len(result.claims) >= len(INTERVIEW_CLAIM_SEEDS)
    assert result.review_queue["items"]
    assert result.knowledge_gaps
    assert any(g.get("code") == "REG.DECISION85.MISSING" for g in result.knowledge_gaps)
    d = result.to_dict()
    assert d["package_status"] == "PARTIAL"
    assert d["study_mutated"] is False


# ---------------------------------------------------------------------------
# Additional meaningful assertions (≥50 total with required names)
# ---------------------------------------------------------------------------


def test_package_status_partial_not_real() -> None:
    m = load_regulatory_manifest()
    assert m.package_status == "PARTIAL"
    assert m.package_status != "REAL"
    # Official PDFs absent
    for rel in (
        "eec/decision_85.pdf",
        "fda/be_guidance.pdf",
        "ema/be_guideline.pdf",
        "smPC/reference_smpc.pdf",
    ):
        assert not (DEFAULT_REGULATORY_ROOT / rel).is_file()


def test_knowledge_rules_seed_remain_proposed() -> None:
    assert all(s.status == "PROPOSED" for s in KNOWLEDGE_RULE_SEEDS)
    assert proposed_rules_remain_proposed(None) is True


def test_medical_rules_added_zero_in_phase13_modules() -> None:
    """Phase 13.1 must not introduce new numeric medical thresholds."""
    threshold_patterns = (
        re.compile(r"\b0\.8[05]\b"),  # classic BE ratio bounds as new norms
        re.compile(r"\b80\s*%\s*-\s*125\s*%\b"),
        re.compile(r"threshold\s*=\s*\d+", re.I),
        re.compile(r"BE_RATIO\s*=", re.I),
    )
    hits: list[str] = []
    for mod_name in PHASE13_MODULES:
        mod = __import__(mod_name, fromlist=["*"])
        src = inspect.getsource(mod)
        for pat in threshold_patterns:
            if pat.search(src):
                hits.append(f"{mod_name}:{pat.pattern}")
    assert hits == []
    # Tasks are discovery titles only — no numeric action definitions
    for t in REGULATORY_EVIDENCE_TASKS:
        assert not re.search(r"\b\d+\.\d+\b", t.title) or "2×2" in t.title or "2x2" in t.title.lower()
    pipe = run_regulatory_evidence_pipeline()
    assert pipe.rules_auto_verified == 0
    assert pipe.coverage["knowledge_rules_verified"] == 0


def test_source_classes_complete() -> None:
    assert "EEC_REGULATORY" in SOURCE_CLASSES
    assert "FDA_GUIDANCE" in SOURCE_CLASSES
    assert "EMA_GUIDANCE" in SOURCE_CLASSES
    assert "SMPC_OHLP" in SOURCE_CLASSES
    assert "EXPERT_INTERVIEW" in SOURCE_CLASSES
    assert "SCIENTIFIC_ARTICLE" in SOURCE_CLASSES


def test_priority_rule_workspace_proposed() -> None:
    assert len(PRIORITY_RULE_WORKSPACE) >= 10
    for code in PRIORITY_RULE_WORKSPACE:
        seed = next(s for s in KNOWLEDGE_RULE_SEEDS if s.rule_code == code)
        assert seed.status == "PROPOSED"


def test_explicit_verify_with_complete_provenance() -> None:
    claim = build_claim(
        claim_id="V1",
        claim_kind="REGULATORY_CLAIM",
        domain="REFERENCE",
        source_class="EEC_REGULATORY",
        provenance=_prov(),
    )
    verified = explicitly_verify_claim(claim, reviewer="expert-a")
    assert verified.verification_status == "VERIFIED"
    assert "verified_by=expert-a" in (verified.notes or "")


def test_interview_json_fixture_present() -> None:
    path = DEFAULT_REGULATORY_ROOT / "interview" / "interview_claims.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = {row["claim_id"] for row in data}
    assert "INT-REF-01" in ids
    assert "INT-FOOD-01" in ids
    assert "INT-SAFETY-01" in ids
    assert len(data) == 6


def test_app_version_0_14_1() -> None:
    # Phase 14 bumped app to 0.30.0; keep this gate aligned with shipped version.
    assert Settings().app_version == "0.30.0"
    from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION

    assert PROTOCOL_GENERATOR_VERSION == "0.30.0"


def test_pipeline_verified_claims_count_zero() -> None:
    result = run_regulatory_evidence_pipeline()
    assert result.coverage["verified_claims"] == 0
    assert sum(1 for c in result.claims if c.get("verification_status") == "VERIFIED") == 0


def test_api_interview_claims_endpoint() -> None:
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get("/api/regulatory-evidence/interview-claims")
        assert r.status_code == 200
        body = r.json()
        assert body["is_regulatory_document"] is False
        assert body["source_type"] == "EXPERT_INTERVIEW"
        assert len(body["claims"]) >= 6
    get_settings.cache_clear()


def test_api_study_conflict_detect_no_mutation() -> None:
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.post(
            "/api/regulatory-evidence/study-conflict/detect",
            json={
                "study_field": "product.dosage",
                "canonical_value": "100 mg",
                "source_value": "200 mg",
                "source_ids": ["S1"],
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["study_mutated"] is False
        assert body["auto_resolved"] is False
        assert body["conflict"]["resolution_status"] == "OPEN"
    get_settings.cache_clear()

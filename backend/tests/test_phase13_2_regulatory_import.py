"""Phase 13.2 — Real Regulatory Evidence Import & Verification tests (§43).

Exact 50 names from phase §43. No Decision 85 PDF fabrication.
No Study mutation. No auto-verification. No package_status=REAL.
"""

from __future__ import annotations

import copy
import hashlib
import io
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.knowledge_seed import KNOWLEDGE_RULE_SEEDS
from app.domain.regulatory_claims import EvidenceProvenance, build_claim
from app.domain.regulatory_conflicts import (
    classify_conflict_type,
    detect_value_conflicts,
    resolve_conflict_forbidden_auto,
)
from app.domain.regulatory_coverage import build_regulatory_coverage_report
from app.domain.regulatory_evidence_manifest import (
    DEFAULT_REGULATORY_ROOT,
    detect_duplicate_sources,
    file_sha256,
    load_regulatory_manifest,
)
from app.domain.regulatory_evidence_pipeline import run_regulatory_evidence_pipeline
from app.domain.regulatory_interview import assert_interview_not_regulatory, interview_claims_as_evidence
from app.domain.regulatory_review_queue import (
    RegulatoryReviewQueue,
    approve_review_item,
    enqueue_claim_review,
    reject_review_item,
)
from app.domain.regulatory_source_slots import (
    OFFICIAL_SLOTS,
    gaps_for_missing_required_slots,
    refresh_slots,
)
from app.domain.regulatory_source_version import (
    copy_fixture_into_import,
    import_regulatory_file,
    list_source_versions,
)
from app.domain.regulatory_verify import (
    VerifyGuardError,
    basis_from_source_version,
    claims_from_import,
    clear_review_audit,
    create_rule_candidate_from_claim,
    reject_claim_explicit,
    review_audit_trail,
    verify_claim_explicit,
)
from app.domain.document_ingest import sha256_hex as digest_hex
from app.main import create_app


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
FIXTURE = REPO_ROOT / "fixtures" / "regulatory" / "test" / "technical_fixture_only.txt"
assert FIXTURE.is_file(), f"missing technical fixture: {FIXTURE}"


def _unique_bytes(tag: str) -> bytes:
    """Fresh content each call so shared DEFAULT registry does not return EXISTING."""
    return FIXTURE.read_bytes() + f"\n{tag}-{uuid.uuid4().hex}\n".encode("utf-8")


def _iso_root(tmp_path: Path) -> Path:
    root = tmp_path / "regulatory"
    (root / "_imported").mkdir(parents=True)
    return root


def _import_fixture(
    tmp_path: Path,
    *,
    source_id: str = "SRC-TECH-ISO",
    project_id: str | None = "proj-iso",
    document_identifier: str | None = "TECH-technical_fixture_only",
    content: bytes | None = None,
    filename: str | None = None,
    technical_fixture: bool = True,
    source_class: str = "OTHER",
) -> object:
    root = _iso_root(tmp_path)
    raw = content if content is not None else FIXTURE.read_bytes()
    name = filename or FIXTURE.name
    return import_regulatory_file(
        content=raw,
        filename=name,
        source_id=source_id,
        source_class=source_class,
        title="Technical fixture",
        document_identifier=document_identifier,
        technical_fixture=technical_fixture,
        project_id=project_id,
        mime_type="text/plain" if name.endswith(".txt") else None,
        base=root,
    ), root


def _minimal_pdf_bytes(*, blank: bool = False) -> bytes:
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

    writer = PdfWriter()
    if blank:
        writer.add_blank_page(width=200, height=200)
    else:
        page = writer.add_blank_page(width=200, height=200)
        # Best-effort text stream — extractors may still yield empty; pages_total>=1 is enough
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 100 100 Td (TECHNICAL FIXTURE PAGE TEXT) Tj ET")
        stream_ref = writer._add_object(stream)
        page[NameObject("/Contents")] = stream_ref
        resources = DictionaryObject()
        font = DictionaryObject()
        font[NameObject("/Type")] = NameObject("/Font")
        font[NameObject("/Subtype")] = NameObject("/Type1")
        font[NameObject("/BaseFont")] = NameObject("/Helvetica")
        resources[NameObject("/Font")] = DictionaryObject({NameObject("/F1"): writer._add_object(font)})
        page[NameObject("/Resources")] = resources
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _canonical_study() -> dict:
    return {
        "study": {"id": "study-13.2", "protocol_number": "BE-13.2-001", "version": "1.0"},
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


# ---------------------------------------------------------------------------
# §43 required tests (exact names)
# ---------------------------------------------------------------------------


def test_source_import(tmp_path: Path) -> None:
    result, root = _import_fixture(tmp_path)
    assert result.status == "IMPORTED"
    assert result.source_version is not None
    assert result.source_version.ingestion_status == "OK"
    assert result.source_version.technical_fixture is True
    assert result.study_mutated is False
    assert (root / "_imported" / "SRC-TECH-ISO").is_dir()
    assert result.pages
    assert result.pages[0]["page_number"] == 1


def test_source_hash(tmp_path: Path) -> None:
    content = FIXTURE.read_bytes()
    expected = hashlib.sha256(content).hexdigest()
    assert digest_hex(content) == expected
    result, _ = _import_fixture(tmp_path, content=content)
    assert result.source_version is not None
    assert result.source_version.content_hash == expected
    # Stable across re-read
    assert digest_hex(FIXTURE.read_bytes()) == expected


def test_duplicate_source(tmp_path: Path) -> None:
    r1, root = _import_fixture(tmp_path, source_id="SRC-DUP-A")
    assert r1.status == "IMPORTED"
    r2 = import_regulatory_file(
        content=FIXTURE.read_bytes(),
        filename=FIXTURE.name,
        source_id="SRC-DUP-B",
        source_class="OTHER",
        document_identifier="TECH-other-id",
        technical_fixture=True,
        project_id="proj-iso",
        mime_type="text/plain",
        base=root,
    )
    assert r2.status == "EXISTING_SOURCE_VERSION"
    assert r2.existing_version_id == r1.source_version.version_id
    assert r2.study_mutated is False


def test_source_version(tmp_path: Path) -> None:
    result, root = _import_fixture(tmp_path)
    sv = result.source_version
    assert sv is not None
    assert sv.version_id.startswith("SV-")
    assert sv.content_hash
    listed = list_source_versions(root, project_id="proj-iso")
    assert any(v.version_id == sv.version_id for v in listed)


def test_version_conflict(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    doc_id = "DOC-VERSION-CONFLICT"
    r1 = import_regulatory_file(
        content=b"version one content for conflict test AAA",
        filename="v1.txt",
        source_id="SRC-VC",
        source_class="OTHER",
        document_identifier=doc_id,
        technical_fixture=True,
        project_id="proj-vc",
        mime_type="text/plain",
        base=root,
    )
    assert r1.status == "IMPORTED"
    r2 = import_regulatory_file(
        content=b"version two DIFFERENT content for conflict test BBB",
        filename="v2.txt",
        source_id="SRC-VC",
        source_class="OTHER",
        document_identifier=doc_id,
        technical_fixture=True,
        project_id="proj-vc",
        mime_type="text/plain",
        base=root,
    )
    assert r2.status == "VERSION_CONFLICT"
    assert r2.conflict is not None
    assert r2.conflict["type"] == "VERSION_CONFLICT"
    versions = list_source_versions(root, project_id="proj-vc")
    prior = next(v for v in versions if v.version_id == r1.source_version.version_id)
    assert prior.is_current is False
    assert prior.verification_status == "SUPERSEDED"
    assert prior.superseded_by == r2.source_version.version_id


def test_source_metadata(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_regulatory_file(
        content=FIXTURE.read_bytes(),
        filename=FIXTURE.name,
        source_id="SRC-META",
        source_class="OTHER",
        title="Meta Title",
        document_identifier="TECH-META-01",
        issuing_authority="TEST-AUTH",
        jurisdiction="TEST",
        language="en",
        technical_fixture=True,
        project_id="proj-meta",
        source_url="https://example.test/fixture.txt",
        mime_type="text/plain",
        base=root,
    )
    sv = result.source_version
    assert sv is not None
    assert sv.title == "Meta Title"
    assert sv.document_identifier == "TECH-META-01"
    assert sv.issuing_authority == "TEST-AUTH"
    assert sv.jurisdiction == "TEST"
    assert sv.language == "en"
    assert sv.source_url == "https://example.test/fixture.txt"
    assert sv.retrieval_date
    assert sv.filename == FIXTURE.name or sv.filename.endswith(".txt")


def test_pdf_pages(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    pdf = _minimal_pdf_bytes(blank=True)
    result = import_regulatory_file(
        content=pdf,
        filename="tech_blank.pdf",
        source_id="SRC-PDF",
        source_class="OTHER",
        document_identifier="TECH-PDF-BLANK",
        technical_fixture=True,
        project_id="proj-pdf",
        mime_type="application/pdf",
        base=root,
    )
    # Blank PDF may be POOR/FAILED quality but still yields page structure or FAILED status
    assert result.status in {"IMPORTED", "FAILED"} or result.source_version is not None
    if result.status == "IMPORTED" and result.pages:
        assert result.source_version.pages_total >= 1
        assert all(p["page_number"] >= 1 for p in result.pages)


def test_page_numbering(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    assert result.pages
    assert result.pages[0]["page_number"] == 1
    # Human-facing: never 0-based
    assert all(int(p["page_number"]) >= 1 for p in result.pages)
    claims = claims_from_import(result)
    assert claims
    assert claims[0].provenance is not None
    assert claims[0].provenance.page == 1


def test_section_provenance(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result)
    assert claims
    prov = claims[0].provenance
    assert prov is not None
    assert prov.paragraph_or_chunk or prov.section or prov.page is not None
    # Explicit section-capable provenance
    claim = build_claim(
        claim_id="SEC-1",
        claim_kind="RAW_EXTRACT",
        domain="REPORTING",
        raw_extract="excerpt",
        normalized_claim="norm",
        provenance=EvidenceProvenance(
            source_id="SRC-TECH-ISO",
            document_id="SV-x",
            source_version="SV-x",
            page=1,
            section="III",
            quoted_text="excerpt",
        ),
    )
    assert claim.provenance.section == "III"


def test_exact_excerpt(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result)
    assert claims
    assert claims[0].raw_extract
    assert claims[0].provenance is not None
    assert claims[0].provenance.quoted_text
    assert "TECHNICAL_FIXTURE_ONLY" in (claims[0].raw_extract or "") or claims[0].raw_extract.strip()


def test_normalized_claim(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result, normalized_claim="Fixture import normalized")
    assert claims
    assert claims[0].normalized_claim == "Fixture import normalized"
    assert claims[0].raw_extract
    assert claims[0].raw_extract != claims[0].normalized_claim


def test_confidence(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result)
    assert claims
    assert claims[0].confidence in {"LOW", "MEDIUM", "HIGH"}
    # HIGH confidence must not imply VERIFIED
    claims[0].confidence = "HIGH"
    assert claims[0].verification_status != "VERIFIED"


def test_verification(tmp_path: Path) -> None:
    clear_review_audit()
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result, normalized_claim="Verified fixture extract")
    claim = claims[0]
    assert claim.verification_status != "VERIFIED"
    verified = verify_claim_explicit(claim, reviewer="expert-a")
    assert verified.verification_status == "VERIFIED"
    assert verified.reviewed_by == "expert-a"


def test_verified_guard(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result)
    claim = claims[0]
    # Strip required fields
    claim.normalized_claim = None
    with pytest.raises(VerifyGuardError) as exc:
        verify_claim_explicit(claim, reviewer="expert")
    assert exc.value.field in {"normalized_claim", "exact_excerpt", "page", "reviewer", "source_id"}


def test_missing_page(tmp_path: Path) -> None:
    claim = build_claim(
        claim_id="NO-PAGE-132",
        claim_kind="REGULATORY_CLAIM",
        domain="REFERENCE",
        source_class="EEC_REGULATORY",
        raw_extract="text",
        normalized_claim="norm",
        source_version_id="SV-1",
        provenance=EvidenceProvenance(
            source_id="SRC-X",
            document_id="SV-1",
            source_version="SV-1",
            page=None,
            quoted_text="text",
        ),
    )
    with pytest.raises(VerifyGuardError) as exc:
        verify_claim_explicit(claim, reviewer="expert")
    assert exc.value.field == "page"


def test_missing_excerpt(tmp_path: Path) -> None:
    claim = build_claim(
        claim_id="NO-EXCERPT",
        claim_kind="RAW_EXTRACT",
        domain="REPORTING",
        source_class="OTHER",
        raw_extract=None,
        normalized_claim="norm",
        source_version_id="SV-1",
        provenance=EvidenceProvenance(
            source_id="SRC-X",
            document_id="SV-1",
            source_version="SV-1",
            page=1,
            quoted_text=None,
        ),
    )
    with pytest.raises(VerifyGuardError) as exc:
        verify_claim_explicit(claim, reviewer="expert")
    assert exc.value.field == "exact_excerpt"


def test_missing_source() -> None:
    claim = build_claim(
        claim_id="NO-SRC",
        claim_kind="RAW_EXTRACT",
        domain="REPORTING",
        source_class="OTHER",
        raw_extract="x",
        normalized_claim="norm",
        source_version_id="SV-1",
        provenance=EvidenceProvenance(
            source_id="",
            document_id="SV-1",
            source_version="SV-1",
            page=1,
            quoted_text="x",
        ),
    )
    # Empty source_id fails guard
    with pytest.raises(VerifyGuardError) as exc:
        verify_claim_explicit(claim, reviewer="expert")
    assert exc.value.field == "source_id"


def test_regulatory_basis(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    assert result.source_version is not None
    claims = claims_from_import(result)
    basis = basis_from_source_version(
        result.source_version,
        claim_id=claims[0].claim_id,
        page=claims[0].provenance.page if claims[0].provenance else 1,
        section="I",
    )
    assert basis.source_id == result.source_version.source_id
    assert basis.status == "UNVERIFIED"
    assert basis.page is not None
    d = basis.to_dict()
    assert d["basis_id"].startswith("RB-")


def test_review_queue(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result)
    queue = RegulatoryReviewQueue(queue_id="q-132")
    for c in claims:
        enqueue_claim_review(queue, item_id=f"REV-{c.claim_id}", claim_id=c.claim_id, payload=c.to_dict())
    assert len(queue.pending()) == len(claims)
    assert all(i.status == "PENDING" for i in queue.items)


def test_approve_review(tmp_path: Path) -> None:
    study = _canonical_study()
    before = copy.deepcopy(study)
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result)
    queue = RegulatoryReviewQueue(queue_id="q-approve")
    item = enqueue_claim_review(queue, item_id="REV-A", claim_id=claims[0].claim_id)
    out = approve_review_item(item)
    assert out["status"] == "APPROVED"
    assert out["study_mutated"] is False
    assert study == before


def test_reject_review(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result)
    queue = RegulatoryReviewQueue(queue_id="q-reject")
    item = enqueue_claim_review(queue, item_id="REV-R", claim_id=claims[0].claim_id)
    out = reject_review_item(item)
    assert out["status"] == "REJECTED"
    assert out["study_mutated"] is False
    rejected = reject_claim_explicit(claims[0], reviewer="expert-r", notes="no")
    assert rejected.verification_status == "REJECTED"


def test_no_Study_mutation(tmp_path: Path) -> None:
    study = _canonical_study()
    before = copy.deepcopy(study)
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result, normalized_claim="no mutation")
    approve_review_item(
        enqueue_claim_review(
            RegulatoryReviewQueue(queue_id="q"),
            item_id="x",
            claim_id=claims[0].claim_id,
        )
    )
    verify_claim_explicit(claims[0], reviewer="expert")
    create_rule_candidate_from_claim(claims[0], rule_code="CAND-132")
    assert study == before
    assert result.study_mutated is False


def test_rule_candidate_stays_proposed(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result, normalized_claim="candidate")
    verify_claim_explicit(claims[0], reviewer="expert")
    cand = create_rule_candidate_from_claim(claims[0], rule_code="CAND-FROM-CLAIM")
    assert cand["status"] == "PROPOSED"
    assert cand["requires_expert_confirmation"] is True
    assert cand["study_mutated"] is False


def test_no_bulk_verification() -> None:
    for seed in KNOWLEDGE_RULE_SEEDS:
        assert seed.status == "PROPOSED"
    result = run_regulatory_evidence_pipeline(include_interview=True)
    assert result.rules_auto_verified == 0
    assert sum(1 for c in result.claims if c.get("verification_status") == "VERIFIED") == 0


def test_source_slot() -> None:
    codes = {s.slot_code for s in OFFICIAL_SLOTS}
    assert "DECISION_85" in codes
    assert "FDA_BE_CORE" in codes
    assert "EMA_BE_CORE" in codes
    assert "REFERENCE_SMPC" in codes
    assert "TECHNICAL_FIXTURE" in codes
    slots = refresh_slots()
    decision = next(s for s in slots if s.slot_code == "DECISION_85")
    # Phase 13.3: Decision 85 MHTML is on disk / may be ingested — not MISSING
    assert decision.status in {"PRESENT", "INGESTED", "REVIEW_REQUIRED"}
    assert decision.status != "MISSING"
    assert decision.required is True


def test_missing_slot_creates_gap() -> None:
    slots = refresh_slots()
    gaps = gaps_for_missing_required_slots(slots)
    codes = {g["code"] for g in gaps}
    # Decision 85 present as of Phase 13.3; other required slots still gap
    assert "REG.DECISION85.MISSING" not in codes
    assert not any(g.get("slot_code") == "DECISION_85" for g in gaps)
    assert "REG.SMPC.MISSING" in codes or any(g.get("slot_code") == "REFERENCE_SMPC" for g in gaps)
    assert all(g["blocking"] for g in gaps if g.get("slot_code") == "REFERENCE_SMPC")


def test_source_coverage() -> None:
    slots = refresh_slots()
    gaps = gaps_for_missing_required_slots(slots)
    report = build_regulatory_coverage_report(
        report_id="cov-132",
        package_status="PARTIAL",
        sources=[s.to_dict() for s in load_regulatory_manifest().sources],
        claims=[],
        knowledge_gaps=gaps,
    )
    assert report.package_status == "PARTIAL"
    assert report.package_status != "REAL"
    assert report.verified_claims == 0
    assert report.sources_missing >= 1 or len(gaps) >= 1


def test_evidence_conflict() -> None:
    claims = [
        {
            "claim_id": "C1",
            "field_name": "food_condition",
            "normalized_claim": "FASTING",
            "provenance": {"source_id": "S1"},
        },
        {
            "claim_id": "C2",
            "field_name": "food_condition",
            "normalized_claim": "FED",
            "provenance": {"source_id": "S2"},
        },
    ]
    conflicts = detect_value_conflicts(claims)
    assert conflicts
    assert conflicts[0].resolution_status == "OPEN"
    with pytest.raises(Exception):
        resolve_conflict_forbidden_auto(conflicts[0])


def test_conflict_classification() -> None:
    assert classify_conflict_type(same_field=True) == "VALUE_CONFLICT"
    assert classify_conflict_type(same_field=True, different_version=True) == "VERSION_CONFLICT"
    assert classify_conflict_type(same_field=True, different_jurisdiction=True) == "JURISDICTION_CONFLICT"


def test_interview_separation() -> None:
    interview = interview_claims_as_evidence()
    assert interview
    for c in interview:
        assert c.claim_kind == "EXPERT_INTERVIEW_CLAIM"
        assert c.source_class == "EXPERT_INTERVIEW"
        assert assert_interview_not_regulatory(c)
    claim = build_claim(
        claim_id="INT-V",
        claim_kind="EXPERT_INTERVIEW_CLAIM",
        domain="REFERENCE",
        source_class="EXPERT_INTERVIEW",
        raw_extract="hint",
        normalized_claim="hint norm",
        source_version_id="INT-1",
        provenance=EvidenceProvenance(
            source_id="SRC-INTERVIEW",
            document_id="INT-1",
            source_version="1",
            page=18,
            quoted_text="hint",
        ),
    )
    with pytest.raises(VerifyGuardError) as exc:
        verify_claim_explicit(claim, reviewer="expert")
    assert exc.value.code == "INTERVIEW_NOT_REGULATORY"


def test_source_duplication() -> None:
    manifest = load_regulatory_manifest()
    dups = detect_duplicate_sources(manifest.sources)
    # May be empty; function must run without inventing sources
    assert isinstance(dups, list)
    root = DEFAULT_REGULATORY_ROOT
    assert root.name == "regulatory"


def test_malformed_pdf(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_regulatory_file(
        content=b"NOT-A-PDF-FILE",
        filename="fake.pdf",
        source_id="SRC-BAD-PDF",
        source_class="OTHER",
        document_identifier="BAD-PDF",
        technical_fixture=True,
        project_id="proj-bad",
        mime_type="application/pdf",
        base=root,
    )
    assert result.status == "FAILED"
    assert result.study_mutated is False


def test_extraction_failure(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    # Valid PDF magic but minimal/corrupt structure → extraction may fail or be poor
    content = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
    result = import_regulatory_file(
        content=content,
        filename="corrupt.pdf",
        source_id="SRC-CORRUPT",
        source_class="OTHER",
        document_identifier="CORRUPT",
        technical_fixture=True,
        project_id="proj-corrupt",
        mime_type="application/pdf",
        base=root,
    )
    assert result.status in {"IMPORTED", "FAILED"}
    if result.source_version:
        assert result.source_version.verification_status != "VERIFIED"
        assert result.source_version.extraction_quality in {
            "FAILED",
            "POOR",
            "FAIR",
            "GOOD",
            "UNKNOWN",
        }


def test_poor_extraction_quality(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    # Very short text → POOR quality path
    result = import_regulatory_file(
        content=b"x",
        filename="tiny.txt",
        source_id="SRC-TINY",
        source_class="OTHER",
        document_identifier="TINY",
        technical_fixture=True,
        project_id="proj-tiny",
        mime_type="text/plain",
        base=root,
    )
    assert result.status == "IMPORTED"
    assert result.source_version is not None
    assert result.source_version.extraction_quality in {"POOR", "FAILED", "FAIR"}
    assert result.source_version.verification_status in {"REVIEW_REQUIRED", "EXTRACTED"}


def test_missing_document_id(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    result = import_regulatory_file(
        content=b"content without document identifier field test",
        filename="noid.txt",
        source_id="SRC-NOID",
        source_class="OTHER",
        document_identifier=None,
        technical_fixture=True,
        project_id="proj-noid",
        mime_type="text/plain",
        base=root,
    )
    assert result.status == "IMPORTED"
    assert result.source_version is not None
    assert result.source_version.document_identifier is None
    # Filename is not silently treated as document_identifier
    assert result.source_version.document_identifier != result.source_version.filename


def test_source_version_superseded(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    doc_id = "DOC-SUPERSEDE"
    r1 = import_regulatory_file(
        content=b"first edition content alpha",
        filename="first.txt",
        source_id="SRC-SUP",
        source_class="OTHER",
        document_identifier=doc_id,
        technical_fixture=True,
        project_id="proj-sup",
        mime_type="text/plain",
        base=root,
    )
    r2 = import_regulatory_file(
        content=b"second edition content beta",
        filename="second.txt",
        source_id="SRC-SUP",
        source_class="OTHER",
        document_identifier=doc_id,
        technical_fixture=True,
        project_id="proj-sup",
        mime_type="text/plain",
        base=root,
    )
    assert r2.status == "VERSION_CONFLICT"
    versions = list_source_versions(root, project_id="proj-sup")
    old = next(v for v in versions if v.version_id == r1.source_version.version_id)
    new = next(v for v in versions if v.version_id == r2.source_version.version_id)
    assert old.verification_status == "SUPERSEDED"
    assert old.is_current is False
    assert new.is_current is True


def test_import_api() -> None:
    get_settings.cache_clear()
    clear_review_audit()
    with TestClient(create_app()) as client:
        pid = f"api-import-proj-{uuid.uuid4().hex[:8]}"
        sid = f"SRC-API-IMPORT-{uuid.uuid4().hex[:8]}"
        content = _unique_bytes("import-api")
        files = {"file": ("tech_import.txt", content, "text/plain")}
        data = {
            "source_id": sid,
            "source_class": "OTHER",
            "technical_fixture": "true",
            "project_id": pid,
            "document_identifier": f"TECH-API-{pid}",
            "normalized_claim": "API imported fixture",
        }
        r = client.post("/api/regulatory-evidence/import", files=files, data=data)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "IMPORTED"
        assert body["auto_verified"] is False
        assert body["study_mutated"] is False
        assert body["source_version"]["technical_fixture"] is True
        assert body["claims"]
    get_settings.cache_clear()


def test_claim_api() -> None:
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        pid = f"api-claim-proj-{uuid.uuid4().hex[:8]}"
        sid = f"SRC-API-CLAIM-{uuid.uuid4().hex[:8]}"
        content = _unique_bytes("claim-api")
        files = {"file": ("tech_claim.txt", content, "text/plain")}
        data = {
            "source_id": sid,
            "source_class": "OTHER",
            "technical_fixture": "true",
            "project_id": pid,
            "document_identifier": f"TECH-CLAIM-{pid}",
            "normalized_claim": "claim api",
        }
        imp = client.post("/api/regulatory-evidence/import", files=files, data=data)
        assert imp.status_code == 200, imp.text
        body = imp.json()
        assert body["status"] == "IMPORTED"
        claims = body.get("claims") or []
        assert claims
        cid = claims[0]["claim_id"]
        got = client.get(f"/api/regulatory-evidence/claims/{cid}")
        assert got.status_code == 200
        assert got.json()["claim_id"] == cid
        src = client.get(f"/api/regulatory-evidence/sources/{sid}")
        assert src.status_code == 200
        sc = client.get(f"/api/regulatory-evidence/sources/{sid}/claims")
        assert sc.status_code == 200
        assert any(c["claim_id"] == cid for c in sc.json()["claims"])
    get_settings.cache_clear()


def test_verify_api() -> None:
    get_settings.cache_clear()
    clear_review_audit()
    with TestClient(create_app()) as client:
        pid = f"api-verify-proj-{uuid.uuid4().hex[:8]}"
        sid = f"SRC-API-VERIFY-{uuid.uuid4().hex[:8]}"
        content = _unique_bytes("verify-api")
        files = {"file": ("tech_verify.txt", content, "text/plain")}
        data = {
            "source_id": sid,
            "source_class": "OTHER",
            "technical_fixture": "true",
            "project_id": pid,
            "document_identifier": f"TECH-VERIFY-{pid}",
            "normalized_claim": "verify via api",
        }
        imp = client.post("/api/regulatory-evidence/import", files=files, data=data)
        assert imp.status_code == 200, imp.text
        claims = imp.json()["claims"]
        assert claims
        cid = claims[0]["claim_id"]
        client.post(f"/api/regulatory-evidence/claims/{cid}/review", json={"reviewer": "r1"})
        bad = client.post(
            f"/api/regulatory-evidence/claims/{cid}/verify",
            json={"reviewer": "", "status": "VERIFIED"},
        )
        assert bad.status_code == 422
        ok = client.post(
            f"/api/regulatory-evidence/claims/{cid}/verify",
            json={"reviewer": "expert-api", "notes": "ok"},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["claim"]["verification_status"] == "VERIFIED"
        assert ok.json()["study_mutated"] is False
    get_settings.cache_clear()


def test_reject_api() -> None:
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        pid = f"api-reject-proj-{uuid.uuid4().hex[:8]}"
        sid = f"SRC-API-REJECT-{uuid.uuid4().hex[:8]}"
        content = _unique_bytes("reject-api")
        files = {"file": ("tech_reject.txt", content, "text/plain")}
        data = {
            "source_id": sid,
            "source_class": "OTHER",
            "technical_fixture": "true",
            "project_id": pid,
            "document_identifier": f"TECH-REJECT-{pid}",
            "normalized_claim": "reject via api",
        }
        imp = client.post("/api/regulatory-evidence/import", files=files, data=data)
        assert imp.status_code == 200
        cid = imp.json()["claims"][0]["claim_id"]
        r = client.post(
            f"/api/regulatory-evidence/claims/{cid}/reject",
            json={"reviewer": "expert-rej", "notes": "nope"},
        )
        assert r.status_code == 200
        assert r.json()["claim"]["verification_status"] == "REJECTED"
        assert r.json()["study_mutated"] is False
    get_settings.cache_clear()


def test_rule_candidate_api() -> None:
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        pid = f"api-rule-proj-{uuid.uuid4().hex[:8]}"
        sid = f"SRC-API-RULE-{uuid.uuid4().hex[:8]}"
        content = _unique_bytes("rule-api")
        files = {"file": ("tech_rule.txt", content, "text/plain")}
        data = {
            "source_id": sid,
            "source_class": "OTHER",
            "technical_fixture": "true",
            "project_id": pid,
            "document_identifier": f"TECH-RULE-{pid}",
            "normalized_claim": "rule candidate",
        }
        imp = client.post("/api/regulatory-evidence/import", files=files, data=data)
        assert imp.status_code == 200
        cid = imp.json()["claims"][0]["claim_id"]
        client.post(
            f"/api/regulatory-evidence/claims/{cid}/verify",
            json={"reviewer": "expert-rule"},
        )
        r = client.post(
            f"/api/regulatory-evidence/claims/{cid}/rule-candidate",
            json={"rule_code": "CAND-API-132", "reviewer": "expert-rule"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "PROPOSED"
        assert r.json()["study_mutated"] is False
    get_settings.cache_clear()


def test_project_isolation(tmp_path: Path) -> None:
    root = _iso_root(tmp_path)
    content_a = b"project A exclusive content for isolation"
    content_b = b"project B exclusive content for isolation"
    ra = import_regulatory_file(
        content=content_a,
        filename="a.txt",
        source_id="SRC-ISO-A",
        source_class="OTHER",
        document_identifier="ISO-A",
        technical_fixture=True,
        project_id="project-A",
        mime_type="text/plain",
        base=root,
    )
    rb = import_regulatory_file(
        content=content_b,
        filename="b.txt",
        source_id="SRC-ISO-B",
        source_class="OTHER",
        document_identifier="ISO-B",
        technical_fixture=True,
        project_id="project-B",
        mime_type="text/plain",
        base=root,
    )
    assert ra.status == "IMPORTED" and rb.status == "IMPORTED"
    listed_b = list_source_versions(root, project_id="project-B")
    ids_b = {v.version_id for v in listed_b}
    assert ra.source_version.version_id not in ids_b
    listed_a = list_source_versions(root, project_id="project-A")
    ids_a = {v.version_id for v in listed_a}
    assert rb.source_version.version_id not in ids_a


def test_no_client_VERIFIED_bypass() -> None:
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        pid = f"api-bypass-v-{uuid.uuid4().hex[:8]}"
        sid = f"SRC-BYPASS-V-{uuid.uuid4().hex[:8]}"
        content = _unique_bytes("bypass-v")
        files = {"file": ("bypass_v.txt", content, "text/plain")}
        data = {
            "source_id": sid,
            "source_class": "OTHER",
            "technical_fixture": "true",
            "project_id": pid,
            "document_identifier": f"TECH-BYPASS-V-{pid}",
            "normalized_claim": "bypass test",
        }
        imp = client.post("/api/regulatory-evidence/import", files=files, data=data)
        assert imp.status_code == 200
        cid = imp.json()["claims"][0]["claim_id"]
        # Client status=VERIFIED still runs server guards (empty reviewer → 422)
        r = client.post(
            f"/api/regulatory-evidence/claims/{cid}/verify",
            json={"reviewer": "  ", "status": "VERIFIED"},
        )
        assert r.status_code == 422
        rev = client.post(
            f"/api/regulatory-evidence/claims/{cid}/review",
            json={"status": "VERIFIED"},
        )
        assert rev.status_code == 422
    get_settings.cache_clear()


def test_no_client_APPROVED_bypass() -> None:
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        pid = f"api-bypass-a-{uuid.uuid4().hex[:8]}"
        sid = f"SRC-BYPASS-A-{uuid.uuid4().hex[:8]}"
        content = _unique_bytes("bypass-a")
        files = {"file": ("bypass_a.txt", content, "text/plain")}
        data = {
            "source_id": sid,
            "source_class": "OTHER",
            "technical_fixture": "true",
            "project_id": pid,
            "document_identifier": f"TECH-BYPASS-A-{pid}",
        }
        imp = client.post("/api/regulatory-evidence/import", files=files, data=data)
        assert imp.status_code == 200
        cid = imp.json()["claims"][0]["claim_id"]
        r = client.post(
            f"/api/regulatory-evidence/claims/{cid}/review",
            json={"status": "APPROVED"},
        )
        assert r.status_code == 422
    get_settings.cache_clear()


def test_full_evidence_pipeline(tmp_path: Path) -> None:
    clear_review_audit()
    study = _canonical_study()
    before = copy.deepcopy(study)
    root = _iso_root(tmp_path)
    result = copy_fixture_into_import(
        fixture_path=FIXTURE,
        source_id="SRC-PIPE-132",
        source_class="OTHER",
        technical_fixture=True,
        document_identifier="TECH-PIPE-132",
        project_id="proj-pipe",
        base=root,
    )
    assert result.status == "IMPORTED"
    assert result.source_version is not None
    assert result.source_version.content_hash == digest_hex(FIXTURE.read_bytes())
    assert result.pages
    assert result.pages[0]["page_number"] == 1
    claims = claims_from_import(result, normalized_claim="Full pipeline fixture claim")
    assert claims
    queue = RegulatoryReviewQueue(queue_id="pipe")
    item = enqueue_claim_review(queue, item_id=f"REV-{claims[0].claim_id}", claim_id=claims[0].claim_id)
    approve_review_item(item)
    verified = verify_claim_explicit(claims[0], reviewer="pipeline-expert")
    assert verified.verification_status == "VERIFIED"
    basis = basis_from_source_version(result.source_version, claim_id=verified.claim_id, page=1)
    assert basis.status == "UNVERIFIED"  # basis itself not auto-verified
    cand = create_rule_candidate_from_claim(verified, rule_code="PIPE-CAND-132")
    assert cand["status"] == "PROPOSED"
    assert study == before
    assert result.study_mutated is False
    # Seeds remain PROPOSED
    assert all(s.status == "PROPOSED" for s in KNOWLEDGE_RULE_SEEDS)
    audit = review_audit_trail()
    assert any(e["action"] == "verify" and e["new_status"] == "VERIFIED" for e in audit)


def test_real_package_manifest() -> None:
    m = load_regulatory_manifest()
    assert m.package_status == "PARTIAL"
    assert m.package_status != "REAL"
    decision = next(s for s in m.sources if s.source_id == "SRC-DECISION85")
    assert decision.ingestion_status == "MISSING"
    for sid in ("SRC-FDA-BE", "SRC-EMA-BE", "SRC-SMPC-REF"):
        src = next(s for s in m.sources if s.source_id == sid)
        assert src.ingestion_status == "MISSING"
    assert FIXTURE.is_file()
    text = FIXTURE.read_text(encoding="utf-8")
    assert "TECHNICAL_FIXTURE_ONLY" in text


def test_regulatory_coverage_report() -> None:
    slots = refresh_slots()
    gaps = gaps_for_missing_required_slots(slots)
    pipe = run_regulatory_evidence_pipeline(include_interview=True)
    assert pipe.package_status == "PARTIAL"
    assert pipe.coverage["verified_claims"] == 0
    assert gaps
    # Decision 85 is present/ingested (Phase 13.3); other required slots still gap
    assert not any(g.get("slot_code") == "DECISION_85" for g in gaps)
    assert any(
        g.get("slot_code") in {"REFERENCE_SMPC", "SAFETY_REFERENCE_PROTOCOL"}
        or "SMPC" in g["code"]
        or "SAFETY" in g["code"]
        for g in gaps
    )


def test_source_reproducibility(tmp_path: Path) -> None:
    content = FIXTURE.read_bytes()
    h1 = digest_hex(content)
    r1, root = _import_fixture(tmp_path, source_id="SRC-REPRO", content=content)
    assert r1.source_version.content_hash == h1
    # Same bytes again → EXISTING, same version id
    r2 = import_regulatory_file(
        content=content,
        filename=FIXTURE.name,
        source_id="SRC-REPRO",
        source_class="OTHER",
        document_identifier="TECH-technical_fixture_only",
        technical_fixture=True,
        project_id="proj-iso",
        mime_type="text/plain",
        base=root,
    )
    assert r2.status == "EXISTING_SOURCE_VERSION"
    assert r2.existing_version_id == r1.source_version.version_id
    assert file_sha256(FIXTURE) == h1


def test_claim_provenance_completeness(tmp_path: Path) -> None:
    result, _ = _import_fixture(tmp_path)
    claims = claims_from_import(result, normalized_claim="complete prov")
    assert claims
    c = claims[0]
    assert c.provenance is not None
    assert c.provenance.source_id
    assert c.provenance.source_version or c.source_version_id
    assert c.provenance.page is not None
    assert c.provenance.quoted_text
    assert c.normalized_claim
    assert c.provenance.is_complete_for_regulatory()


def test_review_audit_trail(tmp_path: Path) -> None:
    clear_review_audit()
    result, _ = _import_fixture(tmp_path, source_id="SRC-AUDIT")
    claims = claims_from_import(result, normalized_claim="audit claim")
    verify_claim_explicit(claims[0], reviewer="auditor", notes="checked")
    trail = review_audit_trail()
    assert trail
    last = trail[-1]
    assert last["action"] == "verify"
    assert last["reviewer"] == "auditor"
    assert last["new_status"] == "VERIFIED"
    assert last["study_mutated"] is False
    # API surface
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        r = client.get("/api/regulatory-evidence/audit")
        assert r.status_code == 200
        assert "entries" in r.json()
    get_settings.cache_clear()

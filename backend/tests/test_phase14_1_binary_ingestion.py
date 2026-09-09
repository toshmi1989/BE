"""Phase 14.1 — Real binary ingestion hardening.

AI-off. Binary DOCX/PDF first-class. No Study mutation. No medical decisions.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.domain.exceptions import ValidationError
from app.domain.study_input_binary_ingest import (
    ingest_binary_file,
    ingest_docx_bytes,
    ingest_pdf_bytes,
    sha256_bytes,
    sha256_file,
    validate_binary_upload,
)
from app.domain.study_input_classify import classify_document
from app.domain.study_input_equivalence import compare_candidate_sets, equivalence_summary
from app.domain.study_input_pipeline import (
    FIXTURE_ROOT,
    apply_ai_candidates,
    attach_document,
    create_package,
    load_design_only_fixture,
    load_real_fixture_package,
    replace_document,
    run_extraction,
)
from app.domain.study_input_store import clear_store
from app.main import create_app


RAW = FIXTURE_ROOT / "updcb_02_be_2026" / "raw"
EXTRACTED = FIXTURE_ROOT / "updcb_02_be_2026" / "extracted"
EXPECTED = FIXTURE_ROOT / "updcb_02_be_2026" / "expected"


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


# ---------------------------------------------------------------------------
# DOCX ingestion (10+)
# ---------------------------------------------------------------------------


def test_docx_checklist_binary_success() -> None:
    r = ingest_binary_file(RAW / "checklist.docx")
    assert r.extraction_status == "SUCCESS"
    assert (r.table_count or 0) >= 1
    assert "30 мг" in r.extracted_text or "30 mg" in r.extracted_text.lower()


def test_docx_synopsis_binary_success() -> None:
    r = ingest_binary_file(RAW / "synopsis.docx")
    assert r.extraction_status == "SUCCESS"
    assert "UPDCB-02-BE-2026" in r.extracted_text
    assert (r.table_count or 0) >= 1


def test_docx_tables_not_paragraph_only() -> None:
    r = ingest_binary_file(RAW / "checklist.docx")
    assert r.table_count and r.table_count > 0
    assert r.tables and any(t.get("cells") for t in r.tables)


def test_docx_checklist_table_location_on_dose() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    dose = next(
        c
        for c in pkg.candidates
        if c.document_type == "CHECKLIST" and c.field_path == "reference_product.dose"
    )
    assert dose.value == "30 mg"
    assert str(dose.location).startswith("table=")


def test_docx_synopsis_semantic_values() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    by = {
        c.field_path: c.value
        for c in pkg.candidates
        if c.document_type == "SYNOPSIS"
    }
    assert by["study.protocol_number"] == "UPDCB-02-BE-2026"
    assert "ПРОМОМЕД" in str(by["sponsor.name"])
    assert by["test_product.dose"] == "15 mg"
    assert by["design.randomized"] is True
    assert by["design.open_label"] is True
    assert by["design.crossover"] is True
    assert by["design.periods"] == 2
    assert by["design.sequences"] == 2
    assert by["design.groups"] == 4
    assert by["subjects.sex"] == "male"
    assert by["subjects.age_min"] == 18
    assert by["subjects.age_max"] == 45
    assert by["subjects.screened_n"] == 62
    assert by["subjects.randomized_n"] == 56
    assert by["subjects.group_allocation"] == "1:1:1:1"
    assert by["washout.duration"] == 7
    assert by["sampling.total_points"] == 19
    times = by["sampling.times"]
    assert times[0] == 0
    assert 72 in times or 72.0 in times


def test_docx_checklist_admin_fields() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    paths = {c.field_path for c in pkg.candidates if c.document_type == "CHECKLIST"}
    assert "sponsor.name" in paths
    assert "cro.name" in paths
    assert "investigator.name" in paths
    assert "reference_product.dose" in paths
    assert "test_product.manufacturer" in paths


def test_docx_golden_protocol_no_study_candidates() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    golden = next(d for d in pkg.documents if d.document_type == "GOLDEN_PROTOCOL")
    assert golden.ingestion_status == "SUCCESS"
    assert not any(c.document_type == "GOLDEN_PROTOCOL" for c in pkg.candidates)
    assert pkg.to_dict()["study_mutated"] is False


def test_docx_design_only_binary() -> None:
    pkg = load_design_only_fixture(prefer_docx=True)
    assert pkg.documents[0].original_filename.endswith(".docx")
    assert pkg.documents[0].ingestion_status == "SUCCESS"
    by = {c.field_path: c.value for c in pkg.candidates}
    assert by["design.randomized"] is True
    assert by["design.groups"] == 4
    assert by["subjects.randomized_n"] == 56
    assert all(c.document_type == "DESIGN" for c in pkg.candidates)


def test_docx_hash_from_binary_not_text() -> None:
    path = RAW / "checklist.docx"
    r = ingest_binary_file(path)
    assert r.content_hash == sha256_file(path)
    assert r.content_hash != sha256_bytes(r.extracted_text.encode("utf-8"))


def test_docx_observability_fields() -> None:
    r = ingest_binary_file(RAW / "checklist.docx")
    obs = r.observability()
    assert obs["status"] == "SUCCESS"
    assert obs["hash"]
    assert obs["table_count"] is not None
    assert obs["study_mutated"] is False


# ---------------------------------------------------------------------------
# PDF ingestion (8+)
# ---------------------------------------------------------------------------


def test_pdf_smpc_binary_success() -> None:
    r = ingest_binary_file(RAW / "smpc.pdf")
    assert r.extraction_status == "SUCCESS"
    assert r.page_count == 49


def test_pdf_page_provenance_on_dose() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    dose = next(
        c for c in pkg.candidates if c.document_type == "SMPC" and c.field_path == "reference_product.dose"
    )
    assert dose.value == "15 mg"
    assert str(dose.location).startswith("page=")


def test_pdf_identity_fields() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    smpc = {c.field_path: c.value for c in pkg.candidates if c.document_type == "SMPC"}
    assert "РАНВЭК" in str(smpc["reference_product.name"])
    assert smpc["reference_product.dose"] == "15 mg"
    assert smpc["reference_product.active_substance"] == "upadacitinib"
    assert "prolonged" in str(smpc["reference_product.dosage_form"])


def test_pdf_signal_sections_present() -> None:
    r = ingest_binary_file(RAW / "smpc.pdf")
    text = r.extracted_text.lower()
    assert "противопоказан" in text
    assert "cyp3a4" in text or "cyp 3a4" in text
    pkg = load_real_fixture_package(prefer_text_dump=False)
    notes = " ".join((c.notes or "") for c in pkg.candidates if c.document_type == "SMPC")
    assert "signal" in notes.lower() or "CYP3A4" in notes or "contraindic" in notes.lower()


def test_pdf_hash_preserves_bytes() -> None:
    p = RAW / "smpc.pdf"
    assert ingest_binary_file(p).content_hash == sha256_file(p)


def test_pdf_pages_have_heading_hints() -> None:
    r = ingest_binary_file(RAW / "smpc.pdf")
    assert r.pages and r.pages[0].get("heading_hint")


def test_pdf_failed_not_silent_success() -> None:
    r = ingest_pdf_bytes(b"%PDF-1.4 truncated", filename="bad.pdf")
    assert r.extraction_status in {"FAILED", "PARTIAL"}
    assert r.extraction_status != "SUCCESS" or r.warnings


def test_pdf_empty_rejected_by_validate() -> None:
    with pytest.raises(ValidationError):
        validate_binary_upload(filename="x.pdf", mime_type="application/pdf", content=b"")


# ---------------------------------------------------------------------------
# Classification (8)
# ---------------------------------------------------------------------------


def test_classify_checklist_from_binary_text() -> None:
    r = ingest_binary_file(RAW / "checklist.docx")
    c = classify_document(filename="checklist.docx", text=r.extracted_text)
    assert c.document_type == "CHECKLIST"


def test_classify_synopsis_from_binary_text() -> None:
    r = ingest_binary_file(RAW / "synopsis.docx")
    c = classify_document(filename="synopsis.docx", text=r.extracted_text)
    assert c.document_type == "SYNOPSIS"


def test_classify_smpc_from_binary_text() -> None:
    r = ingest_binary_file(RAW / "smpc.pdf")
    c = classify_document(filename="smpc.pdf", text=r.extracted_text)
    assert c.document_type == "SMPC"


def test_classify_design_docx() -> None:
    path = FIXTURE_ROOT / "design_only_updcb" / "raw" / "design.docx"
    r = ingest_binary_file(path)
    c = classify_document(filename="design.docx", text=r.extracted_text)
    assert c.document_type == "DESIGN"


def test_classify_golden_protocol() -> None:
    r = ingest_binary_file(RAW / "golden_protocol.docx")
    c = classify_document(filename="golden_protocol.docx", text=r.extracted_text[:3000])
    assert c.document_type in {"GOLDEN_PROTOCOL", "PREVIOUS_PROTOCOL"}


def test_classify_unknown_sparse() -> None:
    c = classify_document(filename="x.bin", text="hello")
    assert c.document_type == "UNKNOWN"


def test_package_documents_classified() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    types = {d.document_type for d in pkg.documents}
    assert {"CHECKLIST", "SYNOPSIS", "SMPC", "GOLDEN_PROTOCOL"} <= types


def test_user_selected_not_overwritten_binary() -> None:
    c = classify_document(
        filename="checklist.docx",
        text="рандомизированное",
        user_selected_type="CHECKLIST",
    )
    assert c.document_type == "CHECKLIST"
    assert c.method == "MANUAL"


# ---------------------------------------------------------------------------
# Provenance / hash / versioning (8)
# ---------------------------------------------------------------------------


def test_same_bytes_same_hash() -> None:
    b = (RAW / "checklist.docx").read_bytes()
    assert sha256_bytes(b) == sha256_bytes(b)


def test_changed_bytes_different_hash() -> None:
    b = (RAW / "checklist.docx").read_bytes()
    assert sha256_bytes(b) != sha256_bytes(b + b"x")


def test_idempotent_attach_same_binary() -> None:
    pkg = create_package()
    d1 = attach_document(pkg, path=RAW / "checklist.docx", document_type="CHECKLIST")
    d2 = attach_document(pkg, path=RAW / "checklist.docx", document_type="CHECKLIST")
    assert d1.document_id == d2.document_id
    assert len([d for d in pkg.documents if d.document_type == "CHECKLIST"]) == 1


def test_replace_preserves_previous_version() -> None:
    pkg = create_package()
    old = attach_document(pkg, path=RAW / "synopsis.docx", document_type="SYNOPSIS")
    run_extraction(pkg)
    # "new" file = checklist bytes under force_new_version via replace with different file
    new = replace_document(pkg, old_document_id=old.document_id, new_path=RAW / "checklist.docx", document_type="SYNOPSIS")
    assert old.superseded_by == new.document_id
    assert new.previous_version_id == old.source_version_id
    assert new.source_id == old.source_id
    assert old.source_version_id != new.source_version_id


def test_replace_does_not_delete_old_document() -> None:
    pkg = create_package()
    old = attach_document(pkg, path=RAW / "synopsis.docx", document_type="SYNOPSIS")
    replace_document(pkg, old_document_id=old.document_id, new_path=RAW / "checklist.docx")
    assert any(d.document_id == old.document_id for d in pkg.documents)


def test_source_version_id_present() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False, run_extract=False)
    assert all(d.source_version_id for d in pkg.documents)


def test_candidate_links_source_version() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    assert all(c.source_version_id for c in pkg.candidates)


def test_rerun_extraction_controlled() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    n1 = len(pkg.candidates)
    run_extraction(pkg, replace=True)
    assert len(pkg.candidates) == n1


# ---------------------------------------------------------------------------
# Binary vs text equivalence (6)
# ---------------------------------------------------------------------------


def test_equiv_synopsis_match() -> None:
    bin_pkg = load_real_fixture_package(prefer_text_dump=False)
    txt_pkg = load_real_fixture_package(prefer_text_dump=True)
    s = equivalence_summary(
        compare_candidate_sets(
            binary_candidates=[c.to_dict() for c in bin_pkg.candidates],
            text_candidates=[c.to_dict() for c in txt_pkg.candidates],
            document_type="SYNOPSIS",
        )
    )
    assert s["pass"] is True
    assert s["match_count"] >= 20


def test_equiv_checklist_dose_match() -> None:
    bin_pkg = load_real_fixture_package(prefer_text_dump=False)
    txt_pkg = load_real_fixture_package(prefer_text_dump=True)
    s = equivalence_summary(
        compare_candidate_sets(
            binary_candidates=[c.to_dict() for c in bin_pkg.candidates],
            text_candidates=[c.to_dict() for c in txt_pkg.candidates],
            document_type="CHECKLIST",
        )
    )
    assert s["pass"] is True
    doses = [
        r
        for r in s["results"]
        if r["field_path"] == "reference_product.dose"
    ]
    assert doses and doses[0]["state"] == "MATCH"
    assert doses[0]["binary_value"] == "30 mg"


def test_equiv_smpc_identity_match() -> None:
    bin_pkg = load_real_fixture_package(prefer_text_dump=False)
    txt_pkg = load_real_fixture_package(prefer_text_dump=True)
    # Compare core identity fields only
    core = {
        "reference_product.name",
        "reference_product.dose",
        "reference_product.active_substance",
        "reference_product.dosage_form",
    }
    b = [c.to_dict() for c in bin_pkg.candidates if c.document_type == "SMPC" and c.field_path in core]
    t = [c.to_dict() for c in txt_pkg.candidates if c.document_type == "SMPC" and c.field_path in core]
    s = equivalence_summary(compare_candidate_sets(binary_candidates=b, text_candidates=t))
    assert s["mismatch_count"] == 0


def test_equiv_location_levels_differ_ok() -> None:
    bin_pkg = load_real_fixture_package(prefer_text_dump=False)
    txt_pkg = load_real_fixture_package(prefer_text_dump=True)
    results = compare_candidate_sets(
        binary_candidates=[c.to_dict() for c in bin_pkg.candidates if c.document_type == "CHECKLIST"],
        text_candidates=[c.to_dict() for c in txt_pkg.candidates if c.document_type == "CHECKLIST"],
        document_type="CHECKLIST",
    )
    dose = next(r for r in results if r.field_path == "reference_product.dose")
    assert dose.state == "MATCH"
    assert dose.location_level in {"EXACT", "STRUCTURAL", "SECTION", "DOCUMENT_ONLY"}
    assert dose.binary_location and dose.binary_location.startswith("table=")


def test_equiv_expected_json_exists() -> None:
    sem = json.loads((EXPECTED / "semantic_expectations.json").read_text(encoding="utf-8"))
    conf = json.loads((EXPECTED / "conflict_expectations.json").read_text(encoding="utf-8"))
    assert sem["fields"]["subjects.randomized_n"] == 56
    assert conf["status"] == "OPEN"


def test_equiv_full_package_core_fields() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    sem = json.loads((EXPECTED / "semantic_expectations.json").read_text(encoding="utf-8"))
    by = {c.field_path: c.value for c in pkg.candidates if c.document_type == "SYNOPSIS"}
    for path, expected in sem["fields"].items():
        if path == "sampling.times":
            assert by[path][0] == 0 and (72 in by[path] or 72.0 in by[path])
        elif path == "sponsor.name":
            assert "ПРОМОМЕД" in str(by[path])
        else:
            assert by[path] == expected, path


# ---------------------------------------------------------------------------
# Conflict / coverage (5)
# ---------------------------------------------------------------------------


def test_conflict_binary_package_open() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    c = next(x for x in pkg.conflicts if x["field_path"] == "reference_product.dose")
    assert c["status"] == "OPEN"
    assert set(c["values"]) == {"15 mg", "30 mg"}


def test_conflict_no_auto_resolve_binary() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    assert all(c.get("outcome") is None for c in pkg.conflicts)


def test_full_package_three_inputs_success() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    inputs = [d for d in pkg.documents if d.role == "INPUT"]
    assert len(inputs) == 3
    assert all(d.ingestion_status == "SUCCESS" for d in inputs)
    assert not any(g["code"] == "MISSING_SMPC_REFERENCE_PRODUCT" for g in pkg.knowledge_gaps)


def test_missing_smpc_binary_package() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False, include_smpc=False)
    # still has golden + checklist + synopsis
    assert any(g["code"] == "MISSING_SMPC_REFERENCE_PRODUCT" for g in pkg.knowledge_gaps)
    assert any(t["code"] == "FIND_SMPC_REFERENCE_PRODUCT" for t in pkg.research_tasks)
    assert not any(
        c.document_type == "SMPC" and "contraindic" in (c.notes or "").lower() for c in pkg.candidates
    )


def test_coverage_reference_conflict_binary() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    assert pkg.coverage["domains"]["REFERENCE_PRODUCT"]["state"] == "CONFLICT"
    assert pkg.to_dict()["study_mutated"] is False


# ---------------------------------------------------------------------------
# Negative binary (5+)
# ---------------------------------------------------------------------------


def test_corrupt_docx_fails() -> None:
    r = ingest_docx_bytes(b"PK\x03\x04not-a-real-docx", filename="bad.docx")
    assert r.extraction_status == "FAILED"
    assert r.extracted_text == ""


def test_corrupt_pdf_not_success_clean() -> None:
    with pytest.raises(ValidationError):
        validate_binary_upload(filename="x.pdf", mime_type="application/pdf", content=b"notpdf")


def test_unsupported_mime() -> None:
    with pytest.raises(ValidationError):
        validate_binary_upload(filename="x.exe", mime_type="application/octet-stream", content=b"MZ")


def test_path_traversal_filename() -> None:
    with pytest.raises(ValidationError):
        validate_binary_upload(filename="../../evil.docx", mime_type=None, content=b"PK" + b"0" * 20)


def test_oversized_rejected() -> None:
    from app.domain.document_ingest import MAX_UPLOAD_BYTES

    with pytest.raises(ValidationError):
        validate_binary_upload(
            filename="big.pdf",
            mime_type="application/pdf",
            content=b"%PDF" + b"0" * (MAX_UPLOAD_BYTES + 10),
        )


def test_failed_ingestion_no_candidates() -> None:
    pkg = create_package()
    # Write temp corrupt docx-looking file
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(b"PK\x03\x04corrupt")
        path = Path(tmp.name)
    doc = attach_document(pkg, path=path, document_type="CHECKLIST")
    assert doc.ingestion_status == "FAILED"
    run_extraction(pkg)
    assert pkg.candidates == []
    assert pkg.to_dict()["study_mutated"] is False


# ---------------------------------------------------------------------------
# API multipart binary (5+)
# ---------------------------------------------------------------------------


def test_api_multipart_upload_checklist(client: TestClient) -> None:
    pkg = client.post("/api/study-input/packages", json={}).json()
    data = (RAW / "checklist.docx").read_bytes()
    res = client.post(
        f"/api/study-input/packages/{pkg['package_id']}/documents",
        files={"file": ("checklist.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"document_type": "CHECKLIST", "role": "INPUT"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["ingestion_status"] == "SUCCESS"
    assert body["study_mutated"] is False
    assert (body.get("table_count") or 0) >= 1


def test_api_full_binary_package_flow(client: TestClient) -> None:
    pkg = client.post("/api/study-input/packages", json={}).json()
    pid = pkg["package_id"]
    for fname, dtype, mime in [
        ("checklist.docx", "CHECKLIST", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("synopsis.docx", "SYNOPSIS", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("smpc.pdf", "SMPC", "application/pdf"),
    ]:
        data = (RAW / fname).read_bytes()
        up = client.post(
            f"/api/study-input/packages/{pid}/documents",
            files={"file": (fname, data, mime)},
            data={"document_type": dtype, "role": "INPUT"},
        )
        assert up.status_code == 201, up.text
    ext = client.post(f"/api/study-input/packages/{pid}/extract")
    assert ext.status_code == 200
    assert ext.json()["study_mutated"] is False
    conf = client.get(f"/api/study-input/packages/{pid}/conflicts").json()
    assert any(c["field_path"] == "reference_product.dose" and c["status"] == "OPEN" for c in conf)
    cov = client.get(f"/api/study-input/packages/{pid}/coverage").json()
    assert cov["domains"]["REFERENCE_PRODUCT"]["state"] == "CONFLICT"


def test_api_reject_corrupt_upload(client: TestClient) -> None:
    pkg = client.post("/api/study-input/packages", json={}).json()
    res = client.post(
        f"/api/study-input/packages/{pkg['package_id']}/documents",
        files={"file": ("x.pdf", b"not-a-pdf", "application/pdf")},
        data={"document_type": "SMPC"},
    )
    assert res.status_code == 400


def test_api_ingest_endpoint(client: TestClient) -> None:
    pkg = client.post("/api/study-input/packages", json={}).json()
    data = (RAW / "synopsis.docx").read_bytes()
    up = client.post(
        f"/api/study-input/packages/{pkg['package_id']}/documents",
        files={"file": ("synopsis.docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"document_type": "SYNOPSIS"},
    )
    doc_id = up.json()["document_id"]
    res = client.post(f"/api/study-input/packages/{pkg['package_id']}/documents/{doc_id}/ingest")
    assert res.status_code == 200
    assert res.json()["study_mutated"] is False
    assert res.json()["ingestion"]["status"] == "SUCCESS"


def test_api_ai_off_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["ai_enabled"] is False


# ---------------------------------------------------------------------------
# AI-off / MockAI
# ---------------------------------------------------------------------------


def test_binary_extraction_ai_off_deterministic() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    assert all(c.extraction_method == "DETERMINISTIC" for c in pkg.candidates)


def test_mock_ai_after_binary_still_proposed() -> None:
    pkg = load_real_fixture_package(prefer_text_dump=False)
    created = apply_ai_candidates(
        pkg,
        [
            {
                "field_path": "food.breakfast_type",
                "value": "high-calorie",
                "excerpt": "завтрак",
                "document_type": "SYNOPSIS",
            }
        ],
    )
    assert created[0].status == "PROPOSED"
    assert created[0].extraction_method == "AI"
    assert pkg.to_dict()["study_mutated"] is False


def test_version_0_15_1() -> None:
    assert get_settings().app_version == "0.32.0"


def test_raw_fixture_layout() -> None:
    assert (RAW / "checklist.docx").exists()
    assert (RAW / "synopsis.docx").exists()
    assert (RAW / "smpc.pdf").exists()
    assert (EXTRACTED / "checklist.txt").exists()
    assert (EXPECTED / "semantic_expectations.json").exists()

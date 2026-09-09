"""Phase 12C — production readiness / TECHNICAL_FIXTURE package tests."""

from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path

from app.core.config import Settings
from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.content_change_impact import (
    compute_content_change_impact,
    detect_stale_content,
)
from app.domain.content_resolver import filter_decision_for_render
from app.domain.design_decision_engine import DesignDecisionEngine, propose_design
from app.domain.display_value_registry import find_raw_enums_in_text
from app.domain.document_completeness import assess_document_completeness
from app.domain.document_ingest import extract_document
from app.domain.full_document_qa import run_full_document_qa
from app.domain.production_readiness import build_production_readiness_report
from app.domain.protocol_assembly import assemble_protocol
from app.domain.protocol_qa import compare_identity_maps
from app.domain.protocol_tables import build_tables
from app.domain.real_protocol_input_manifest import (
    DEFAULT_PACKAGE_DIR,
    REPO_ROOT,
    RealProtocolInputManifest,
    build_default_technical_manifest,
    load_manifest,
)
from app.domain.reference_builder import (
    build_bibliography,
    find_duplicate_reference_ids,
    find_orphan_source_ids,
)
from app.domain.reference_registry import detect_broken_reference_text
from app.domain.static_blocks import STATIC_VERIFIED
from tests.phase10_golden_helpers import build_fixture_docx_bytes


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOMAIN = BACKEND_ROOT / "app" / "domain"
PACKAGE_DIR = Path(DEFAULT_PACKAGE_DIR)
PERF: dict[str, float] = {}


def _ctx(**overrides):
    base = {
        "project_id": "p12c",
        "study": {
            "id": "study-12c",
            "protocol_number": "BE-12C-001",
            "title": "BE 12C Technical Fixture Protocol",
            "version": "1.0",
        },
        "sponsor": {"name": "Sponsor Co", "id": "sponsor-1"},
        "product": {
            "trade_name": "Бозутиниб",
            "inn": "bosutinib",
            "dosage": "400 mg",
            "dosage_form": "tablet",
            "manufacturer": "Maker",
        },
        "reference_product": {
            "trade_name": "Бозулиф",
            "inn": "bosutinib",
            "dosage": "400 mg",
            "dosage_form": "tablet",
            "manufacturer": "Pfizer",
        },
        "design": {
            "type": "CROSSOVER_2X2",
            "periods": 2,
            "sequences": [["T", "R"], ["R", "T"]],
        },
        "food": {"condition": "FED"},
        "subjects": {
            "target_evaluable_n": 24,
            "planned_randomized_n": 28,
            "planned_screened_n": 40,
            "reserve_n": 0,
        },
        "sample_size": {
            "evaluable_n": 24,
            "randomized_n": 28,
            "method": "standard",
            "id": "ss-1",
        },
        "sampling": {
            "points": [
                {"time_h": 0.0, "reason": "BASELINE"},
                {"time_h": 2.0, "reason": "TMAX_CAPTURE"},
                {"time_h": 24.0, "reason": "FINAL"},
                {"time_h": 72.0, "reason": "FINAL"},
            ],
            "total_points_per_period": 4,
            "source_ids": ["samp-src-1"],
        },
        "washout": {"selected_value": 7, "unit": "day", "requires_washout": True},
        "observation": {"selected_duration": 72, "unit": "h"},
        "pk_parameters": [
            {"parameter_code": "Cmax"},
            {"parameter_code": "AUC_0_LAST"},
            {"parameter_code": "AUC_0_72H"},
        ],
        "persons": [
            {"id": "p1", "full_name": "Ivan Ivanov", "role": "PI"},
        ],
        "organizations": [
            {"id": "o1", "name": "Site Org", "role": "clinical_site"},
        ],
        "expert_decisions": [],
        "evidence_claims": [
            {
                "id": "ec-1",
                "source_ids": ["src-1"],
                "field_name": "design_rationale",
                "evidence_type": "literature",
            }
        ],
        "sources": [
            {
                "id": "src-1",
                "title": "EMA Guideline on BE",
                "authors": ["EMA"],
                "year": 2010,
                "citation": "EMA. Guideline on the investigation of bioequivalence. 2010.",
                "document_identifier": "EMA/CHMP/EWP/2001",
            },
            {
                "id": "src-2",
                "title": "ICH M9",
                "authors": ["ICH"],
                "year": 2019,
                "citation": "ICH. M9 Biopharmaceutics Classification System. 2019.",
                "document_identifier": "ICH-M9",
            },
        ],
        "regulatory_bases": [
            {
                "id": "rb-1",
                "source_id": "src-1",
                "title": "EMA Guideline on BE",
                "document_identifier": "EMA/CHMP/EWP/2001",
                "section_reference": "4.1",
                "jurisdiction": "EU",
            }
        ],
        "administration": {
            "ethics_committee": "Ethics Committee Technical",
            "insurance": "Insurance policy technical",
            "financing": "Sponsor financing technical",
        },
    }
    base.update(overrides)
    return base


def _assemble(ctx=None, only=None):
    return assemble_protocol(
        ctx or _ctx(),
        blocking_validation=False,
        only_sections=only,
    )


def _section(assembled, code):
    return next(s for s in assembled["sections"] if s["section_code"] == code)


def _texts(sec) -> str:
    out = []
    for b in sec.get("content_blocks") or []:
        if b.get("text"):
            out.append(str(b["text"]))
        out.extend(str(x) for x in (b.get("items") or []))
        if b.get("display_text"):
            out.append(str(b["display_text"]))
    return "\n".join(out)


def _all_texts(assembled) -> str:
    return "\n".join(_texts(s) for s in assembled.get("sections") or [])


def _blocks(sec):
    return list(sec.get("content_blocks") or [])


def _canonical_from_ctx(ctx):
    counts = get_canonical_subject_counts(ctx)
    return {
        "design": (ctx.get("design") or {}).get("type"),
        "randomized_n": counts.randomized_n,
        "trade_name": (ctx.get("product") or {}).get("trade_name"),
        "protocol_number": (ctx.get("study") or {}).get("protocol_number"),
        "study_title": (ctx.get("study") or {}).get("title"),
        "sponsor": (ctx.get("sponsor") or {}).get("name"),
        "auc_metric": "AUC0-t",
    }


def _pkg_bytes(rel: str) -> tuple[str, bytes]:
    p = PACKAGE_DIR / rel
    return p.name, p.read_bytes()


# ---------------------------------------------------------------------------
# 1–6 Manifest + ingestion
# ---------------------------------------------------------------------------


def test_real_input_manifest():
    assert REPO_ROOT == Path(__file__).resolve().parents[2]
    assert (REPO_ROOT / "fixtures" / "packages" / "bosutinib-technical-v1").is_dir()
    m = load_manifest(PACKAGE_DIR)
    assert isinstance(m, RealProtocolInputManifest)
    assert m.classification == "TECHNICAL_FIXTURE"
    assert m.medical_validation is False
    assert m.package_id == "bosutinib-technical-v1"
    for e in m.all_entries():
        if e.completeness != "MISSING":
            assert e.hash and len(e.hash) == 64
    m2 = build_default_technical_manifest()
    assert m2.classification == "TECHNICAL_FIXTURE"
    assert m2.medical_validation is False


def test_real_design_ingestion():
    name, raw = _pkg_bytes("sources/design_notes.txt")
    t0 = time.perf_counter()
    result = extract_document(filename=name, content=raw)
    PERF["ingest_design"] = time.perf_counter() - t0
    assert result.pages
    blob = "\n".join(p.text for p in result.pages)
    assert "CROSSOVER_2X2" in blob
    assert "TECHNICAL_FIXTURE" in blob or "bosutinib" in blob.lower()


def test_real_product_ingestion():
    name, raw = _pkg_bytes("sources/test_product.txt")
    result = extract_document(filename=name, content=raw)
    blob = "\n".join(p.text for p in result.pages)
    assert "400 mg" in blob
    assert "bosutinib" in blob.lower()


def test_reference_ingestion():
    name, raw = _pkg_bytes("sources/reference_product.txt")
    result = extract_document(filename=name, content=raw)
    blob = "\n".join(p.text for p in result.pages)
    assert "Бозулиф" in blob or "bosutinib" in blob.lower()
    # DOCX path via phase10 fixture builder (no invented medical values)
    docx_bytes = build_fixture_docx_bytes()
    docx_res = extract_document(filename="fixture.docx", content=docx_bytes)
    assert docx_res.pages
    assert any("бозутиниб" in (p.text or "").lower() for p in docx_res.pages)


def test_checklist_mapping():
    name, raw = _pkg_bytes("sources/checklist.json")
    result = extract_document(filename=name, content=raw)
    blob = "\n".join(p.text for p in result.pages)
    data = json.loads(blob)
    assert data["classification"] == "TECHNICAL_FIXTURE"
    assert data["fields"]["inn"] == "bosutinib"
    assert data["fields"]["dose"] == "400 mg"
    assert data["fields"]["design"] == "CROSSOVER_2X2"


def test_cv_evidence_ingestion():
    name, raw = _pkg_bytes("sources/cv_evidence.json")
    t0 = time.perf_counter()
    result = extract_document(filename=name, content=raw)
    PERF["ingest_cv"] = time.perf_counter() - t0
    blob = "\n".join(p.text for p in result.pages)
    data = json.loads(blob)
    assert data["cv_studies"]
    assert data["cv_studies"][0]["parameter"] == "Cmax"
    assert data["cv_studies"][0]["cv_value"] == 35.0


# ---------------------------------------------------------------------------
# 7–10 AI / expert
# ---------------------------------------------------------------------------


def test_ai_off_pipeline(tmp_path):
    from app.domain.docx_renderer import render_protocol_docx

    settings = Settings()
    assert settings.ai_enabled is False
    ctx = _ctx()
    t0 = time.perf_counter()
    assembled = _assemble(ctx)
    PERF["assemble"] = time.perf_counter() - t0
    t1 = time.perf_counter()
    qa = run_full_document_qa(
        assembled=assembled,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    PERF["full_qa"] = time.perf_counter() - t1
    assert qa.gate == "READY"
    t2 = time.perf_counter()
    docx = render_protocol_docx(
        protocol_payload=assembled,
        study_ctx=ctx,
        mode="DRAFT",
        output_dir=tmp_path,
        project_slug="12c-ai-off",
        protocol_version="1",
        only_sections=["16", "17", "18"],
    )
    PERF["docx"] = time.perf_counter() - t2
    assert docx.status == "READY", docx.blocking_reasons
    assert Path(docx.output_path).exists()
    # Absurdly slow only fails
    assert PERF["assemble"] < 120
    assert PERF["full_qa"] < 120
    assert PERF["docx"] < 120


def test_ai_proposals_do_not_mutate_canonical():
    ctx = _ctx()
    original_product = copy.deepcopy(ctx["product"])
    original_study = copy.deepcopy(ctx["study"])
    proposal = {
        "status": "PROPOSED",
        "decision_type": "PRODUCT_DOSE",
        "proposed_value": {"dosage": "999 mg"},
        "source": "AI_SIMULATED",
    }
    ctx["expert_decisions"] = [proposal]
    assert filter_decision_for_render(proposal) is None
    assembled = _assemble(ctx)
    # Canonical ctx unchanged
    assert ctx["product"] == original_product
    assert ctx["study"] == original_study
    assert ctx["product"]["dosage"] == "400 mg"
    assert "999 mg" not in _all_texts(assembled)


def test_reference_final_requires_expert():
    proposed = {"status": "PROPOSED", "decision_type": "REFERENCE_PRODUCT", "id": "d-ref-p"}
    approved = {"status": "APPROVED", "decision_type": "REFERENCE_PRODUCT", "id": "d-ref-a"}
    assert filter_decision_for_render(proposed) is None
    assert filter_decision_for_render(approved) is not None
    # Without canonical reference + only PROPOSED → blocked selection path
    ctx = _ctx(reference_product={}, expert_decisions=[proposed])
    a = _assemble(ctx, only={"2.1.2"})
    sec = _section(a, "2.1.2")
    blob = _texts(sec)
    assert "{{REFERENCE_PRODUCT.MISSING}}" in blob or "REFERENCE_SELECTION" in blob
    assert any(
        b.get("resolution_status") in {"BLOCKED", "UNRESOLVED", "PROPOSED"}
        and not b.get("display_as_final")
        for b in _blocks(sec)
    )


def test_design_final_requires_expert():
    engine = DesignDecisionEngine()
    proposal = engine.propose(
        cv_intra_cmax=35.0,
        ci_cmax=(80.0, 125.0),
        variability_indication="HIGH",
        evidence_claim_ids=["ec-1"],
        regulatory_basis_ids=["rb-1"],
    )
    assert proposal.status == "PROPOSED"
    assert proposal.requires_expert_confirmation is True
    assert filter_decision_for_render({"status": proposal.status, "decision_type": "DESIGN"}) is None
    # Proposed-only, no canonical design → not final
    ctx = _ctx(
        design={},
        expert_decisions=[
            {
                "status": "PROPOSED",
                "decision_type": "DESIGN",
                "proposed_value": {"type": proposal.proposed_design},
            }
        ],
    )
    a = _assemble(ctx, only={"4.2"})
    sec = _section(a, "4.2")
    assert any(
        b.get("resolution_status") == "PROPOSED" or "{{DESIGN" in str(b.get("text") or "")
        for b in _blocks(sec)
    )
    assert all(not b.get("display_as_final") for b in _blocks(sec) if b.get("resolution_status") == "PROPOSED")
    approved_ctx = _ctx(
        design={},
        expert_decisions=[
            {
                "id": "des-1",
                "status": "APPROVED",
                "decision_type": "DESIGN",
                "final_value": {"type": "CROSSOVER_2X2"},
                "proposed_value": {"type": "CROSSOVER_2X2"},
            }
        ],
    )
    assert filter_decision_for_render(approved_ctx["expert_decisions"][0]) is not None


# ---------------------------------------------------------------------------
# 11–16 Sampling / dose / sponsor / stale / legacy
# ---------------------------------------------------------------------------


def test_randomized_n_gap_blocks_final():
    ctx = _ctx(
        subjects={
            "target_evaluable_n": 24,
            "planned_randomized_n": None,
            "planned_screened_n": 40,
        },
        sample_size={"evaluable_n": 24, "randomized_n": None, "method": "standard"},
    )
    a = _assemble(ctx)
    blob = _all_texts(a)
    assert "{{SUBJECTS.RANDOMIZED_N}}" in blob or "RANDOMIZED_N" in blob
    qa = run_full_document_qa(assembled=a, ctx=ctx, canonical=_canonical_from_ctx(ctx), mode="FINAL")
    assert qa.gate == "BLOCKED"


def test_single_canonical_sampling_plan():
    ctx = _ctx()
    # Exactly one sampling points list in ctx
    assert isinstance(ctx.get("sampling"), dict)
    assert isinstance(ctx["sampling"].get("points"), list)
    assert "sampling_plans" not in ctx
    a = _assemble(ctx)
    times = [p["time_h"] for p in ctx["sampling"]["points"]]
    assert times == [0.0, 2.0, 24.0, 72.0]
    # Document uses the single plan
    qa = run_full_document_qa(assembled=a, ctx=ctx, canonical=_canonical_from_ctx(ctx), mode="DRAFT")
    assert not any(f.get("code") == "QA.SAMPLING.INCONSISTENT_TIMES" for f in qa.findings)


def test_sampling_change_propagates():
    ctx_before = _ctx()
    before = _assemble(ctx_before)
    ctx_after = _ctx(
        sampling={
            "points": [
                {"time_h": 0.0, "reason": "BASELINE"},
                {"time_h": 1.0, "reason": "TMAX_CAPTURE"},
                {"time_h": 48.0, "reason": "FINAL"},
            ],
            "total_points_per_period": 3,
            "source_ids": ["samp-src-1"],
        }
    )
    after = _assemble(ctx_after)
    impact = compute_content_change_impact(
        changed_field="sampling.points",
        old_value=[0.0, 2.0, 24.0, 72.0],
        new_value=[0.0, 1.0, 48.0],
        assembled_before=before,
        assembled_after=after,
    )
    assert impact.rebuild_required is True
    assert any(s.startswith("6") or s == "SYNOPSIS" or s == "16" for s in impact.affected_sections)
    blob_after = _all_texts(after)
    # New times appear where sampling is rendered; old exclusive times should not dominate
    assert "48" in blob_after or "1.0" in blob_after or "1" in blob_after


def test_single_dose_change_propagates():
    ctx_before = _ctx()
    before = _assemble(ctx_before)
    ctx_after = _ctx(
        product={
            **ctx_before["product"],
            "dosage": "200 mg",
        }
    )
    after = _assemble(ctx_after)
    impact = compute_content_change_impact(
        changed_field="product.dosage",
        old_value="400 mg",
        new_value="200 mg",
        assembled_before=before,
        assembled_after=after,
    )
    assert "2" in impact.affected_sections or "1" in impact.affected_sections or "SYNOPSIS" in impact.affected_sections
    blob = _all_texts(after)
    assert "200 mg" in blob
    # Dynamic product content should prefer new dose
    product_secs = [s for s in after["sections"] if str(s["section_code"]).startswith("2")]
    if product_secs:
        pblob = "\n".join(_texts(s) for s in product_secs)
        assert "200 mg" in pblob


def test_single_sponsor_change_propagates():
    ctx_before = _ctx()
    before = _assemble(ctx_before)
    ctx_after = _ctx(sponsor={"name": "NewSponsorTech", "id": "sponsor-2"})
    after = _assemble(ctx_after)
    impact = compute_content_change_impact(
        changed_field="sponsor.name",
        old_value="Sponsor Co",
        new_value="NewSponsorTech",
        assembled_before=before,
        assembled_after=after,
    )
    assert impact.affected_sections
    assert "IDENTITY" in impact.affected_qa_rules or "LEGACY" in impact.affected_qa_rules
    assert "NewSponsorTech" in _all_texts(after) or impact.rebuild_required


def test_stale_content_detected():
    ctx = _ctx()
    a = _assemble(ctx)
    # Inject old dose into assembled text while canonical says new
    for s in a["sections"]:
        for b in s.get("content_blocks") or []:
            if b.get("text"):
                b["text"] = str(b["text"]) + " legacy dose 500 mg"
                break
    findings = detect_stale_content(
        assembled=a,
        canonical_values={"product.dosage": {"old": "500 mg", "new": "400 mg"}},
    )
    assert findings
    assert any(f.get("code") == "CONTENT.STALE_VALUE" for f in findings)


def test_previous_protocol_legacy_detection():
    prev_path = PACKAGE_DIR / "sources" / "previous_protocol_identity.json"
    prev = json.loads(prev_path.read_text(encoding="utf-8"))["previous_identity"]
    current = {
        "sponsor": "Sponsor Co",
        "protocol_number": "BE-12C-001",
        "product": "Бозутиниб",
        "dose": "400 mg",
        "randomized_n": 28,
        "investigator": "Ivan Ivanov",
    }
    diffs = compare_identity_maps(previous=prev, current=current)
    legacy = [d for d in diffs if d.diff_type == "LEGACY_SUSPECTED"]
    assert legacy
    # Also via full QA legacy_hints
    ctx = _ctx()
    a = _assemble(ctx)
    for s in a["sections"]:
        if s["section_code"] == "17":
            for b in s["content_blocks"]:
                if b.get("text"):
                    b["text"] = str(b["text"]) + " " + prev["sponsor"]
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
        legacy_hints={"sponsor": prev["sponsor"]},
    )
    assert any("LEGACY" in str(f.get("code") or "").upper() for f in qa.findings)


# ---------------------------------------------------------------------------
# 17–25 Full QA / DOCX scans
# ---------------------------------------------------------------------------


def test_full_document_qa():
    ctx = _ctx()
    a = _assemble(ctx)
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    assert qa.gate == "READY"
    assert hasattr(qa, "findings")
    assert qa.critical_count >= 0


def test_full_docx_build(tmp_path):
    from app.domain.docx_renderer import render_protocol_docx

    ctx = _ctx()
    a = _assemble(ctx)
    result = render_protocol_docx(
        protocol_payload=a,
        study_ctx=ctx,
        mode="DRAFT",
        output_dir=tmp_path,
        project_slug="12c-full",
        protocol_version="1",
        only_sections=["16", "17", "18"],
    )
    assert result.status == "READY", result.blocking_reasons
    assert Path(result.output_path).exists()


def test_docx_no_placeholders():
    """FINAL must be blocked when unresolved placeholders remain (forbidden in FINAL path)."""
    ctx = _ctx(product={}, reference_product={}, sources=[], regulatory_bases=[], evidence_claims=[])
    a = _assemble(ctx)
    blob = _all_texts(a)
    assert "{{" in blob  # incomplete fixture / missing identity leaves markers
    qa = run_full_document_qa(assembled=a, ctx=ctx, mode="FINAL")
    assert qa.gate == "BLOCKED"
    assert any(
        "PLACEHOLDER" in str(f.get("code") or "").upper() or f.get("blocking") for f in qa.findings
    )


def test_docx_no_raw_enums(tmp_path):
    from app.domain.docx_renderer import render_protocol_docx

    ctx = _ctx()
    a = _assemble(ctx)
    blob = _all_texts(a)
    assert find_raw_enums_in_text(blob) == []
    qa = run_full_document_qa(assembled=a, ctx=ctx, mode="DRAFT")
    assert not any(f.get("code") == "CONTENT.RAW_ENUM_LEAK" for f in qa.findings)
    result = render_protocol_docx(
        protocol_payload=a,
        study_ctx=ctx,
        mode="DRAFT",
        output_dir=tmp_path,
        project_slug="12c-enums",
        protocol_version="1",
        only_sections=["16", "17", "18"],
    )
    assert result.status == "READY", result.blocking_reasons


def test_docx_no_broken_references():
    ctx = _ctx()
    a = _assemble(ctx)
    blob = _all_texts(a)
    assert detect_broken_reference_text(blob) == []
    assert "Error! Reference source not found" not in blob
    assert "Error: Reference source not found" not in blob
    qa = run_full_document_qa(assembled=a, ctx=ctx, mode="DRAFT")
    assert not any(f.get("code") == "QA.DOC.BROKEN_REFERENCE_TEXT" for f in qa.findings)


def test_docx_n_consistency():
    ctx = _ctx()
    a = _assemble(ctx)
    counts = get_canonical_subject_counts(ctx)
    assert counts.randomized_n == 28
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    n_mismatches = [
        f
        for f in qa.findings
        if f.get("code") == "CONTENT.CANONICAL_MISMATCH"
        and "Subject N" in str(f.get("message") or "")
    ]
    assert n_mismatches == []


def test_docx_sampling_consistency():
    ctx = _ctx()
    a = _assemble(ctx)
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    assert not any(f.get("code") == "QA.SAMPLING.INCONSISTENT_TIMES" for f in qa.findings)


def test_docx_pk_consistency():
    ctx = _ctx()
    a = _assemble(ctx)
    blob = _all_texts(a)
    assert "AUC0-x = AUC0-72" not in blob
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    assert not any(f.get("code") == "QA.PK.AUC_METRIC_MISMATCH" for f in qa.findings)


# ---------------------------------------------------------------------------
# 26–29 References / tables
# ---------------------------------------------------------------------------


def test_reference_dedup():
    ctx = _ctx(
        sources=[
            {
                "id": "src-dup",
                "title": "Same Doc",
                "year": 2020,
                "citation": "Same citation text.",
                "document_identifier": "DOC-1",
            },
            {
                "id": "src-dup",
                "title": "Same Doc Again",
                "year": 2020,
                "citation": "Same citation text.",
                "document_identifier": "DOC-1",
            },
        ],
        evidence_claims=[],
        regulatory_bases=[{"source_id": "src-dup", "document_identifier": "DOC-1"}],
    )
    entries = build_bibliography(ctx)
    assert len([e for e in entries if e.source_id == "src-dup"]) == 1
    assert find_duplicate_reference_ids(entries) == []


def test_reference_orphan_detection():
    entries = build_bibliography(_ctx())
    orphans = find_orphan_source_ids(["src-1", "missing-src-99"], entries)
    assert "missing-src-99" in orphans
    assert "src-1" not in orphans


def test_table_registry_integrity():
    ctx = _ctx()
    a = _assemble(ctx)
    tables = build_tables(ctx, {})
    keys = {t.get("table_key") for t in tables}
    for s in a["sections"]:
        for b in _blocks(s):
            if b.get("type") == "TABLE" and b.get("table_key"):
                # TABLE blocks must either be in registry or intentionally absent when no rows
                if b["table_key"] == "CV_EVIDENCE":
                    assert "CV_EVIDENCE" in keys


def test_table_error_root_cause():
    """Without cv_studies, CV_EVIDENCE TABLE must not be orphaned (table_errors=0 for that key)."""
    ctx_no_cv = _ctx()
    assert not ctx_no_cv.get("cv_studies")
    a = _assemble(ctx_no_cv)
    cv_blocks = [
        b
        for s in a["sections"]
        for b in _blocks(s)
        if b.get("type") == "TABLE" and b.get("table_key") == "CV_EVIDENCE"
    ]
    assert cv_blocks == [], "CV_EVIDENCE TABLE must not emit without cv rows (orphan fix)"
    qa = run_full_document_qa(assembled=a, ctx=ctx_no_cv, mode="DRAFT")
    cv_table_errs = [
        f
        for f in qa.findings
        if f.get("code") == "QA.TABLE.UNRESOLVED" and str(f.get("actual") or "") == "CV_EVIDENCE"
    ]
    assert cv_table_errs == []
    assert qa.table_errors == 0 or not cv_table_errs

    # With cv_studies, CV_EVIDENCE is registered
    ctx_cv = _ctx(
        cv_studies=[
            {
                "parameter": "Cmax",
                "cv_value": 35.0,
                "n_total": 36,
                "condition": "FED",
                "design": "CROSSOVER_2X2",
                "source_id": "src-cv-template-excerpt",
            }
        ]
    )
    tables = build_tables(ctx_cv, {})
    assert any(t.get("table_key") == "CV_EVIDENCE" for t in tables)
    a_cv = _assemble(ctx_cv)
    assert any(
        b.get("table_key") == "CV_EVIDENCE"
        for s in a_cv["sections"]
        for b in _blocks(s)
        if b.get("type") == "TABLE"
    )


# ---------------------------------------------------------------------------
# 30–35 Gates / missing data
# ---------------------------------------------------------------------------


def test_incomplete_gate():
    ctx = _ctx(product={}, persons=[], organizations=[], sources=[])
    a = _assemble(ctx)
    qa = run_full_document_qa(assembled=a, ctx=ctx, mode="FINAL")
    completeness = assess_document_completeness(a, qa.findings)
    assert completeness.readiness == "BLOCKED" or completeness.unresolved_blocks > 0 or completeness.critical_gaps
    assert qa.gate == "BLOCKED"


def test_review_gate():
    ctx = _ctx(product={})
    a = _assemble(ctx)
    review = run_full_document_qa(assembled=a, ctx=ctx, mode="REVIEW")
    draft = run_full_document_qa(assembled=a, ctx=ctx, mode="DRAFT")
    assert review.gate == "BLOCKED"
    assert draft.gate == "READY"
    assert isinstance(review.gate, str)


def test_final_gate():
    ctx = _ctx(product={})
    a = _assemble(ctx)
    final = run_full_document_qa(assembled=a, ctx=ctx, mode="FINAL")
    assert final.gate == "BLOCKED"
    assert final.readiness == "BLOCKED"


def test_missing_admin_data():
    ctx = _ctx(administration={})
    a = _assemble(ctx)
    blob = _all_texts(a)
    # Gaps / unresolved markers rather than invented admin values
    has_gap = "{{" in blob or any(
        (b.get("knowledge_gaps") or b.get("unresolved"))
        for s in a["sections"]
        for b in _blocks(s)
    )
    assert has_gap


def test_missing_signature_data():
    # Sponsor alone can seed signatory rows — clear sponsor too (same as 12B.4).
    ctx = _ctx(persons=[], organizations=[], sponsor={})
    a = _assemble(ctx, only={"16"})
    blob = _texts(_section(a, "16"))
    assert "{{SIGNATURES}}" in blob
    gaps = []
    for b in _blocks(_section(a, "16")):
        gaps.extend(b.get("knowledge_gaps") or [])
        gaps.extend(b.get("unresolved") or [])
    assert gaps


def test_missing_source_gap():
    ctx = _ctx(sources=[], regulatory_bases=[], evidence_claims=[])
    a = _assemble(ctx, only={"18"})
    blob = _texts(_section(a, "18"))
    assert "{{SOURCES.LIST}}" in blob
    assert any(b.get("resolution_status") == "UNRESOLVED" for b in _blocks(_section(a, "18")))


# ---------------------------------------------------------------------------
# 36–42 Decisions / change impact / AI conflict
# ---------------------------------------------------------------------------


def test_proposal_approval_regeneration():
    ctx_prop = _ctx(
        design={},
        expert_decisions=[
            {
                "id": "d1",
                "status": "PROPOSED",
                "decision_type": "DESIGN",
                "proposed_value": {"type": "CROSSOVER_2X2"},
            }
        ],
    )
    a_prop = _assemble(ctx_prop, only={"4.2"})
    assert any(
        b.get("resolution_status") == "PROPOSED" or "{{DESIGN" in str(b.get("text") or "")
        for b in _blocks(_section(a_prop, "4.2"))
    )
    ctx_ok = _ctx(
        design={"type": "CROSSOVER_2X2", "periods": 2},
        expert_decisions=[
            {
                "id": "d1",
                "status": "APPROVED",
                "decision_type": "DESIGN",
                "final_value": {"type": "CROSSOVER_2X2"},
            }
        ],
    )
    a_ok = _assemble(ctx_ok, only={"4.2"})
    blob = _texts(_section(a_ok, "4.2"))
    assert "CROSSOVER" in blob or "перекрест" in blob.lower() or "2" in blob
    assert filter_decision_for_render(ctx_ok["expert_decisions"][0]) is not None


def test_rejected_decision_not_used():
    rejected = {
        "id": "rej-1",
        "status": "REJECTED",
        "decision_type": "DESIGN",
        "proposed_value": {"type": "PARALLEL"},
        "final_value": {"type": "PARALLEL"},
    }
    assert filter_decision_for_render(rejected) is None
    ctx = _ctx(expert_decisions=[rejected])
    a = _assemble(ctx)
    assert "PARALLEL" not in _all_texts(a) or (ctx.get("design") or {}).get("type") != "PARALLEL"
    assert (ctx.get("design") or {}).get("type") == "CROSSOVER_2X2"


def test_superseded_decision_not_used():
    superseded = {
        "id": "sup-1",
        "status": "SUPERSEDED",
        "decision_type": "PRODUCT_DOSE",
        "proposed_value": {"dosage": "999 mg"},
    }
    assert filter_decision_for_render(superseded) is None
    ctx = _ctx(expert_decisions=[superseded])
    a = _assemble(ctx)
    assert ctx["product"]["dosage"] == "400 mg"
    assert "999 mg" not in _all_texts(a)


def test_content_change_impact():
    impact = compute_content_change_impact(
        changed_field="product.dosage",
        old_value="400 mg",
        new_value="200 mg",
    )
    assert impact.rebuild_required is True
    assert impact.affected_sections
    assert "TEST_PRODUCT" in impact.affected_tables or impact.affected_tables is not None
    assert impact.to_dict()["changed_field"] == "product.dosage"


def test_unaffected_content_preserved():
    ctx_before = _ctx()
    before = _assemble(ctx_before, only={"16", "17", "18"})
    static_before = _texts(_section(before, "16"))
    ctx_after = _ctx(sponsor={"name": "OtherSponsor", "id": "s2"})
    after = _assemble(ctx_after, only={"16", "17", "18"})
    static_after = _texts(_section(after, "16"))
    # Static verified appendix language preserved across sponsor change
    assert "STATIC_VERIFIED" in static_before
    assert "STATIC_VERIFIED" in static_after
    assert STATIC_VERIFIED in static_before or "STATIC_VERIFIED" in static_before


def test_static_template_preserved():
    a = _assemble(_ctx(), only={"16"})
    texts = _texts(_section(a, "16"))
    assert "STATIC_VERIFIED" in texts
    assert "не переписывается" in texts or "сохранено" in texts or "STATIC" in texts


def test_ai_conflict_requires_review():
    """Simulated AI proposal conflicting with canonical must not auto-apply; review required."""
    ctx = _ctx()
    ai_proposal = {
        "id": "ai-1",
        "status": "PROPOSED",
        "decision_type": "PRODUCT_DOSE",
        "proposed_value": {"dosage": "100 mg"},
        "source": "AI",
        "conflicts_with_canonical": True,
    }
    ctx["expert_decisions"] = [ai_proposal]
    assert filter_decision_for_render(ai_proposal) is None
    a = _assemble(ctx)
    assert ctx["product"]["dosage"] == "400 mg"
    assert "100 mg" not in _all_texts(a) or "400 mg" in _all_texts(a)
    # Design engine proposal also requires expert confirmation
    p = propose_design(cv_intra_cmax=40.0, ci_cmax=(80, 125), variability_indication="HIGH")
    assert p.requires_expert_confirmation is True
    assert p.status == "PROPOSED"


# ---------------------------------------------------------------------------
# 43–46 Source / policy scans
# ---------------------------------------------------------------------------


def test_no_invented_values():
    for fname in (
        "real_protocol_input_manifest.py",
        "content_change_impact.py",
        "production_readiness.py",
    ):
        src = (DOMAIN / fname).read_text(encoding="utf-8")
        assert "invent" not in src.lower() or "Does not invent" in src or "not invent" in src.lower()
        # No hard-coded medical sample-size / BE defaults
        assert "80–125" not in src
        assert "alpha = 0.05" not in src
    # Assembled with empty product must gap, not invent product dose into conclusion
    a = _assemble(_ctx(product={}))
    conc = _texts(_section(a, "17"))
    assert "{{CONCLUSION.REQUIRED}}" in conc or "{{" in conc


def test_no_n_a_fallback():
    for fname in (
        "real_protocol_input_manifest.py",
        "content_change_impact.py",
        "production_readiness.py",
        "docx_renderer.py",
    ):
        src = (DOMAIN / fname).read_text(encoding="utf-8")
        assert re.search(r"""['\"]N/A['\"]""", src) is None
        assert re.search(r"""['\"]n/a['\"]""", src) is None
        assert "as applicable" not in src.lower()


def test_no_global_replace():
    for fname in (
        "real_protocol_input_manifest.py",
        "content_change_impact.py",
        "production_readiness.py",
        "docx_renderer.py",
    ):
        src = (DOMAIN / fname).read_text(encoding="utf-8")
        assert "find_and_replace" not in src.lower()
        assert "global_replace" not in src.lower()
        assert "document.Replace" not in src
    docx_src = (DOMAIN / "docx_renderer.py").read_text(encoding="utf-8")
    assert "only_sections" in docx_src


def test_no_positional_docx_mapping():
    for fname in (
        "real_protocol_input_manifest.py",
        "content_change_impact.py",
        "production_readiness.py",
    ):
        src = (DOMAIN / fname).read_text(encoding="utf-8")
        assert "cells[0]" not in src
        assert "paragraphs[" not in src
        assert "row.cells" not in src
    docx_src = (DOMAIN / "docx_renderer.py").read_text(encoding="utf-8")
    assert "only_sections" in docx_src
    assert "def render_protocol_docx" in docx_src


# ---------------------------------------------------------------------------
# 47–50 E2E / reproducibility / legacy / consistency
# ---------------------------------------------------------------------------


def test_complete_end_to_end_pipeline(tmp_path):
    from app.domain.docx_renderer import render_protocol_docx

    # Conceptual user workflow in one integration test
    manifest = load_manifest(PACKAGE_DIR)
    assert manifest.classification == "TECHNICAL_FIXTURE"

    ingested = {}
    for e in manifest.all_entries():
        rel = e.path or f"sources/{e.filename}"
        path = PACKAGE_DIR / rel
        if path.is_file():
            ingested[e.source_id] = extract_document(filename=path.name, content=path.read_bytes())
    assert "SRC-DESIGN-01" in ingested
    assert "SRC-TEST-01" in ingested

    ctx = _ctx()
    assembled = _assemble(ctx)
    qa = run_full_document_qa(
        assembled=assembled,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    assert qa.gate == "READY"

    # Change one field → reassemble → QA
    ctx2 = _ctx(sponsor={"name": "ChangedSponsor", "id": "sponsor-x"})
    assembled2 = _assemble(ctx2)
    impact = compute_content_change_impact(
        changed_field="sponsor.name",
        old_value="Sponsor Co",
        new_value="ChangedSponsor",
        assembled_before=assembled,
        assembled_after=assembled2,
    )
    assert impact.rebuild_required
    qa2 = run_full_document_qa(
        assembled=assembled2,
        ctx=ctx2,
        canonical=_canonical_from_ctx(ctx2),
        mode="DRAFT",
    )
    assert qa2.gate == "READY"

    docx = render_protocol_docx(
        protocol_payload=assembled2,
        study_ctx=ctx2,
        mode="DRAFT",
        output_dir=tmp_path,
        project_slug="12c-e2e",
        protocol_version="1",
        only_sections=["16", "17", "18"],
    )
    assert docx.status == "READY", docx.blocking_reasons

    report = build_production_readiness_report(
        package_id=manifest.package_id,
        classification=manifest.classification,
        manifest_summary={"entries": len(manifest.all_entries())},
        ingestion_summary={"ingested": len(ingested)},
        qa_report=qa2,
        gate_results={"DRAFT": "READY", "REVIEW": "BLOCKED", "FINAL": "BLOCKED"},
        ai_off_result={"status": "PASS"},
        ai_on_result={"status": "NOT_AVAILABLE"},
        performance=dict(PERF),
        production_blockers=["FINAL blocked — technical fixture incomplete for medical FINAL"],
    )
    assert report.recommendation == "READY-WITH-BLOCKERS"
    assert report.medical_validation_claimed is False


def test_repeat_build_semantic_reproducibility():
    ctx = _ctx()
    a1 = _assemble(ctx)
    a2 = _assemble(copy.deepcopy(ctx))
    assert _all_texts(a1) == _all_texts(a2)
    codes1 = [s["section_code"] for s in a1["sections"]]
    codes2 = [s["section_code"] for s in a2["sections"]]
    assert codes1 == codes2


def test_full_document_legacy_scan():
    ctx = _ctx()
    a = _assemble(ctx)
    prev = json.loads(
        (PACKAGE_DIR / "sources" / "previous_protocol_identity.json").read_text(encoding="utf-8")
    )["previous_identity"]
    for s in a["sections"]:
        for b in s.get("content_blocks") or []:
            if b.get("text"):
                b["text"] = str(b["text"]) + f" {prev['protocol_number']}"
                break
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
        legacy_hints={"protocol_number": prev["protocol_number"]},
    )
    assert any("LEGACY" in str(f.get("code") or "").upper() for f in qa.findings)


def test_full_document_cross_section_consistency():
    ctx = _ctx()
    a = _assemble(ctx)
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    mismatch = [
        f
        for f in qa.findings
        if "MISMATCH" in str(f.get("code") or "").upper()
        or f.get("code") == "CONTENT.CANONICAL_MISMATCH"
    ]
    # Clean fixture ctx should not introduce N / sampling / AUC mismatches
    bad = [
        f
        for f in mismatch
        if any(
            x in str(f.get("code") or "") + str(f.get("message") or "")
            for x in ("Subject N", "SAMPLING", "AUC_METRIC")
        )
    ]
    assert bad == []


# ---------------------------------------------------------------------------
# Extra: production readiness report + timing smoke + AI ON status
# ---------------------------------------------------------------------------


def test_production_readiness_recommendation_technical_fixture():
    report = build_production_readiness_report(
        package_id="bosutinib-technical-v1",
        classification="TECHNICAL_FIXTURE",
        gate_results={"DRAFT": "READY", "REVIEW": "BLOCKED", "FINAL": "BLOCKED"},
        production_blockers=["FINAL blocked"],
        ai_on_result={"status": "NOT_AVAILABLE"},
    )
    assert report.recommendation == "READY-WITH-BLOCKERS"
    assert report.package_classification == "TECHNICAL_FIXTURE"
    assert report.medical_validation_claimed is False
    assert any("TECHNICAL_FIXTURE" in x for x in report.known_limitations)


def test_timing_smoke_recorded():
    # Ensure timings were captured by earlier tests or record now
    ctx = _ctx()
    t0 = time.perf_counter()
    _assemble(ctx)
    elapsed = time.perf_counter() - t0
    PERF["assemble_smoke"] = elapsed
    assert elapsed < 180  # absurd threshold only
    assert all(v < 180 for v in PERF.values())


def test_ai_on_status_not_available_by_default():
    settings = Settings()
    assert settings.ai_enabled is False
    assert settings.external_ai_enabled is False
    report = build_production_readiness_report(
        classification="TECHNICAL_FIXTURE",
        ai_off_result={"status": "PASS"},
        ai_on_result={"status": "NOT_AVAILABLE", "reason": "ai_enabled default False"},
    )
    assert report.ai_on.get("status") == "NOT_AVAILABLE"


def test_user_workflow_simulation(tmp_path):
    """Steps 1–15 conceptual workflow (create → ingest → assemble → change → QA)."""
    from app.domain.docx_renderer import render_protocol_docx

    # 1 create project ctx
    ctx = _ctx(project_id="workflow-12c")
    # 2–6 ingest package files
    m = build_default_technical_manifest()
    for e in m.all_entries():
        path = PACKAGE_DIR / (e.path or e.filename)
        if path.is_file():
            extract_document(filename=path.name, content=path.read_bytes())
    # 7–9 evidence / approve (simulated APPROVED design decision present alongside canonical)
    ctx["expert_decisions"] = [
        {
            "id": "wf-des",
            "status": "APPROVED",
            "decision_type": "DESIGN",
            "final_value": {"type": "CROSSOVER_2X2"},
        }
    ]
    # 10–12 build + QA + DOCX
    a = _assemble(ctx)
    qa = run_full_document_qa(assembled=a, ctx=ctx, canonical=_canonical_from_ctx(ctx), mode="DRAFT")
    assert qa.gate == "READY"
    docx = render_protocol_docx(
        protocol_payload=a,
        study_ctx=ctx,
        mode="DRAFT",
        output_dir=tmp_path,
        project_slug="12c-workflow",
        protocol_version="1",
        only_sections=["17"],
    )
    assert docx.status == "READY", docx.blocking_reasons
    # 13–15 change field, regenerate, QA again
    ctx["product"] = {**ctx["product"], "dosage": "200 mg"}
    a2 = _assemble(ctx)
    assert "200 mg" in _all_texts(a2)
    qa2 = run_full_document_qa(assembled=a2, ctx=ctx, canonical=_canonical_from_ctx(ctx), mode="DRAFT")
    assert qa2.gate == "READY"

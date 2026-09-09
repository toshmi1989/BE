"""Phase 12B.4 - appendices / conclusion / literature + full-document finalization tests."""

from __future__ import annotations

import re
from pathlib import Path

from app.domain.appendix_inventory import build_appendix_inventory
from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.content_core_templates import CORE_12B4_SECTION_CODES
from app.domain.content_resolver import filter_decision_for_render
from app.domain.display_value_registry import find_raw_enums_in_text
from app.domain.document_completeness import assess_document_completeness
from app.domain.full_document_qa import run_full_document_qa
from app.domain.protocol_assembly import GENERATORS, assemble_protocol
from app.domain.protocol_generators_12b4 import CORE_12B4_GENERATORS
from app.domain.reference_builder import (
    BibliographyEntry,
    build_bibliography,
    find_duplicate_reference_ids,
    find_orphan_source_ids,
)
from app.domain.reference_registry import detect_broken_reference_text
from app.domain.static_blocks import STATIC_VERIFIED


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOMAIN = BACKEND_ROOT / "app" / "domain"


def _ctx(**overrides):
    base = {
        "project_id": "p12b4",
        "study": {
            "id": "study-12b4",
            "protocol_number": "BE-12B4-001",
            "title": "BE 12B4 Full Document",
            "version": "1.0",
        },
        "sponsor": {"name": "Sponsor Co", "id": "sponsor-1"},
        "product": {
            "trade_name": "TestDrug",
            "inn": "testdrug",
            "dosage": "100 mg",
            "dosage_form": "tablet",
            "manufacturer": "Maker",
        },
        "reference_product": {
            "trade_name": "RefDrug",
            "inn": "testdrug",
            "dosage": "100 mg",
            "dosage_form": "tablet",
        },
        "design": {
            "type": "CROSSOVER_2X2",
            "periods": 2,
            "sequences": [["T", "R"], ["R", "T"]],
        },
        "food": {"condition": "FASTING"},
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
            ],
            "total_points_per_period": 3,
            "source_ids": ["samp-src-1"],
        },
        "washout": {"selected_value": 7, "unit": "day", "requires_washout": True},
        "observation": {"selected_duration": 24, "unit": "h"},
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
    }
    base.update(overrides)
    return base

def _assemble(ctx=None, only=None):
    return assemble_protocol(
        ctx or _ctx(),
        blocking_validation=False,
        only_sections=only if only is not None else CORE_12B4_SECTION_CODES,
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


def test_core_12b4_section_codes():
    assert CORE_12B4_SECTION_CODES == frozenset({"16", "17", "18"})


def test_generators_registered():
    for key in ("appendices", "conclusion", "literature"):
        assert key in CORE_12B4_GENERATORS
        assert key in GENERATORS
        assert GENERATORS[key] is CORE_12B4_GENERATORS[key]


def test_assemble_emits_sections_16_17_18():
    a = _assemble()
    codes = {s["section_code"] for s in a["sections"]}
    assert {"16", "17", "18"} <= codes


def test_filter_decision_rejects_proposed():
    assert filter_decision_for_render({"status": "PROPOSED", "decision_type": "X"}) is None
    assert filter_decision_for_render({"status": "APPROVED", "decision_type": "X"}) is not None


def test_full_document_has_no_broken_references():
    ctx = _ctx()
    a = _assemble(ctx)
    blob = _all_texts(a)
    assert detect_broken_reference_text(blob) == []
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    assert "Error! Reference source not found" not in blob
    assert not any(f.get("code") == "QA.DOC.BROKEN_REFERENCE_TEXT" for f in qa.findings)


def test_full_document_has_no_forbidden_placeholders():
    a = _assemble()
    blob = _all_texts(a)
    for phrase in (
        "Error: Reference source not found",
        "Error! Reference source not found",
    ):
        assert phrase.lower() not in blob.lower()
    assert not re.search(r"(?i)(?<![A-Z0-9_])TODO(?![A-Z0-9_])", blob)
    assert not re.search(r"(?i)(?<![A-Z0-9_])TBD(?![A-Z0-9_])", blob)
    qa = run_full_document_qa(assembled=a, ctx=_ctx(), mode="DRAFT")
    assert not any(f.get("code") == "QA.DOC.FORBIDDEN_PLACEHOLDER" for f in qa.findings)


def test_full_document_has_no_raw_enums():
    a = _assemble()
    blob = _all_texts(a)
    assert find_raw_enums_in_text(blob) == []
    qa = run_full_document_qa(assembled=a, ctx=_ctx(), mode="DRAFT")
    assert not any(f.get("code") == "CONTENT.RAW_ENUM_LEAK" for f in qa.findings)


def test_full_document_has_no_global_replace():
    gen_src = (DOMAIN / "protocol_generators_12b4.py").read_text(encoding="utf-8")
    qa_src = (DOMAIN / "full_document_qa.py").read_text(encoding="utf-8")
    docx_src = (DOMAIN / "docx_renderer.py").read_text(encoding="utf-8")
    assert "only_sections" in docx_src
    for text in (gen_src, qa_src):
        assert "find_and_replace" not in text.lower()
        assert "global_replace" not in text.lower()
        assert "document.Replace" not in text
    assert "content.replace(" not in gen_src
    assert "text.replace(" not in gen_src
    assert "str.replace" not in gen_src


def test_full_document_has_no_positional_mapping():
    gen_src = (DOMAIN / "protocol_generators_12b4.py").read_text(encoding="utf-8")
    assert "cells[0]" not in gen_src
    assert "cells[1]" not in gen_src
    assert "cell[0]" not in gen_src
    assert "paragraphs[" not in gen_src
    assert "row.cells" not in gen_src


def test_appendix_uses_canonical_data():
    ctx = _ctx()
    inv = build_appendix_inventory(ctx=ctx)
    assert inv
    a = _assemble(ctx)
    sec = _section(a, "16")
    inv_blocks = [b for b in _blocks(sec) if b.get("block_code") == "APP.INVENTORY"]
    assert inv_blocks
    b = inv_blocks[0]
    assert b.get("resolution_status") == "RESOLVED"
    assert b.get("appendix_inventory")
    assert any(
        str(i.get("type")) in {"STATIC_VERIFIED", "FORM", "DYNAMIC_CANONICAL"}
        for i in b["appendix_inventory"]
    )
    static_blocks = [
        x
        for x in _blocks(sec)
        if x.get("content_type") == "STATIC_VERIFIED" or x.get("origin") == STATIC_VERIFIED
    ]
    assert static_blocks
    assert any("STATIC_VERIFIED" in str(x.get("text") or "") for x in static_blocks)


def test_conclusion_does_not_invent_results():
    a = _assemble()
    text = _texts(_section(a, "17"))
    assert "планируется" in text.lower()
    assert "результат исследования" not in text.lower()
    assert "результаты показали" not in text.lower()
    assert "эффективность подтверждена" not in text.lower()
    assert "безопасность подтверждена" not in text.lower()
    assert "получен результат" not in text.lower()
    assert "результат" not in text.lower()


def test_conclusion_no_invented_efficacy_words():
    text = _texts(_section(_assemble(), "17"))
    for bad in ("эффективност", "подтверждена безопасность", "pk показал", "cmax превысил"):
        assert bad not in text.lower()


def test_references_are_source_backed():
    ctx = _ctx()
    entries = build_bibliography(ctx)
    assert entries
    assert all(e.source_id or e.document_identifier or e.citation for e in entries)
    a = _assemble(ctx)
    lit = _section(a, "18")
    list_blocks = [b for b in _blocks(lit) if b.get("block_code") == "SOURCES.LIST"]
    assert list_blocks
    b = list_blocks[0]
    assert b.get("source_ids")
    assert set(b["source_ids"]).issubset({"src-1", "src-2"})
    assert b.get("bibliography")
    for row in b["bibliography"]:
        assert row.get("citation") or row.get("title")
        assert row.get("source_id") or row.get("document_identifier")


def test_duplicate_reference_deduplicated():
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
            {
                "id": "src-other",
                "title": "Other",
                "year": 2021,
                "citation": "Other citation.",
                "document_identifier": "DOC-2",
            },
        ],
        regulatory_bases=[
            {
                "source_id": "src-dup",
                "title": "Same Doc",
                "document_identifier": "DOC-1",
            }
        ],
        evidence_claims=[],
    )
    entries = build_bibliography(ctx)
    assert len([e for e in entries if e.source_id == "src-dup"]) == 1
    assert find_duplicate_reference_ids(entries) == []
    dup = [
        BibliographyEntry("REF-001", "a", "c1", "t", None, 2020, None, None),
        BibliographyEntry("REF-001", "b", "c2", "t2", None, 2021, None, None),
    ]
    assert find_duplicate_reference_ids(dup) == ["REF-001"]


def test_orphan_reference_detected():
    entries = build_bibliography(_ctx())
    orphans = find_orphan_source_ids(["src-1", "missing-src-99"], entries)
    assert "missing-src-99" in orphans
    assert "src-1" not in orphans


def test_randomized_n_consistent_document_wide():
    ctx = _ctx()
    a = assemble_protocol(ctx, blocking_validation=False)
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
    conc = _texts(_section(_assemble(ctx), "17"))
    assert "28" in conc


def test_sampling_consistent_document_wide():
    ctx = _ctx()
    a = assemble_protocol(ctx, blocking_validation=False)
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    samp = [f for f in qa.findings if f.get("code") == "QA.SAMPLING.INCONSISTENT_TIMES"]
    assert samp == []


def test_auc_semantics_consistent_document_wide():
    ctx = _ctx()
    a = assemble_protocol(ctx, blocking_validation=False)
    blob = _all_texts(a)
    assert "AUC0-x = AUC0-72" not in blob
    assert "AUC0-72 = AUC0-x" not in blob
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    assert not any(f.get("code") == "QA.PK.AUC_METRIC_MISMATCH" for f in qa.findings)


def test_legacy_template_value_detected():
    ctx = _ctx()
    a = _assemble(ctx)
    for s in a["sections"]:
        if s["section_code"] == "17":
            for b in s["content_blocks"]:
                if b.get("text"):
                    b["text"] = str(b["text"]) + " OldSponsorLegacyXYZ"
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
        legacy_hints={"sponsor": "OldSponsorLegacyXYZ"},
    )
    legacy = [f for f in qa.findings if "LEGACY" in str(f.get("code") or "").upper()]
    assert legacy
    assert any(
        "OldSponsorLegacyXYZ" in str(f.get("actual") or f.get("message") or "")
        for f in legacy
    )


def test_final_gate_blocks_critical_gap():
    ctx = _ctx(product={})
    a = _assemble(ctx)
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="FINAL",
    )
    assert qa.gate == "BLOCKED"
    assert qa.readiness == "BLOCKED"
    assert any(
        f.get("blocking") or str(f.get("severity")).upper() == "CRITICAL"
        for f in qa.findings
    )


def test_final_gate_blocks_unresolved_required_content():
    ctx = _ctx(
        product={},
        reference_product={},
        sources=[],
        regulatory_bases=[],
        evidence_claims=[],
    )
    a = _assemble(ctx)
    assert "{{CONCLUSION.REQUIRED}}" in _texts(_section(a, "17"))
    assert "{{SOURCES.LIST}}" in _texts(_section(a, "18"))
    qa = run_full_document_qa(assembled=a, ctx=ctx, mode="FINAL")
    assert qa.gate == "BLOCKED"
    codes = {f.get("code") for f in qa.findings}
    assert "CONTENT.PLACEHOLDER_UNRESOLVED" in codes


def test_review_gate_is_explicit():
    ctx = _ctx(product={})
    a = _assemble(ctx)
    qa = run_full_document_qa(assembled=a, ctx=ctx, mode="REVIEW")
    assert qa.gate == "BLOCKED"
    assert isinstance(qa.gate, str)
    draft = run_full_document_qa(assembled=a, ctx=ctx, mode="DRAFT")
    assert draft.gate == "READY"


def test_draft_can_show_review_markers():
    ctx = _ctx(sources=[], regulatory_bases=[], evidence_claims=[])
    a = _assemble(ctx)
    lit = _texts(_section(a, "18"))
    assert "{{SOURCES.LIST}}" in lit
    qa = run_full_document_qa(assembled=a, ctx=ctx, mode="DRAFT")
    assert qa.gate == "READY"
    assert any(
        "{{SOURCES.LIST}}" in str(b.get("text") or "")
        or "{{SOURCES.LIST}}" in str(b.get("unresolved") or [])
        for b in _blocks(_section(a, "18"))
    )


def test_static_appendix_preserved():
    inv = build_appendix_inventory(ctx=_ctx())
    forms = [
        i
        for i in inv
        if str(i.type) in {"STATIC_VERIFIED", "FORM"} and (i.block_id or "").startswith("APP.")
    ]
    assert forms
    a = _assemble()
    texts = _texts(_section(a, "16"))
    assert "STATIC_VERIFIED" in texts
    assert "не переписывается" in texts or "сохранено" in texts


def test_full_docx_build(tmp_path):
    from app.domain.docx_renderer import render_protocol_docx

    ctx = _ctx()
    a = _assemble(ctx)
    result = render_protocol_docx(
        protocol_payload=a,
        study_ctx=ctx,
        mode="DRAFT",
        output_dir=tmp_path,
        project_slug="12b4-full",
        protocol_version="1",
        only_sections=["16", "17", "18"],
    )
    assert result.status == "READY", result.blocking_reasons
    assert result.output_path is not None
    assert Path(result.output_path).exists()
    assert result.filename


def test_conclusion_requires_fields():
    a = _assemble(_ctx(product={}))
    sec = _section(a, "17")
    assert "{{CONCLUSION.REQUIRED}}" in _texts(sec)
    assert any(b.get("resolution_status") == "UNRESOLVED" for b in _blocks(sec))
    gaps = []
    for b in _blocks(sec):
        gaps.extend(b.get("knowledge_gaps") or [])
    assert any(g.get("domain") == "CONCLUSION" and g.get("blocking") for g in gaps)


def test_conclusion_requires_design_display():
    a = _assemble(_ctx(design={}))
    assert "{{CONCLUSION.REQUIRED}}" in _texts(_section(a, "17"))


def test_conclusion_ok_with_study_title_without_reference():
    a = _assemble(_ctx(reference_product={}))
    text = _texts(_section(a, "17"))
    assert "{{CONCLUSION.REQUIRED}}" not in text
    assert "TestDrug" in text
    assert "планируется" in text
    assert "BE 12B4" in text or "исследовании" in text


def test_bibliography_empty_shows_gap():
    ctx = _ctx(sources=[], regulatory_bases=[], evidence_claims=[])
    assert build_bibliography(ctx) == []
    a = _assemble(ctx)
    sec = _section(a, "18")
    assert "{{SOURCES.LIST}}" in _texts(sec)
    gaps = []
    for b in _blocks(sec):
        gaps.extend(b.get("knowledge_gaps") or [])
    assert any(g.get("domain") == "SOURCES" for g in gaps)


def test_bibliography_dedupes_regulatory_same_source():
    entries = build_bibliography(_ctx())
    src1 = [e for e in entries if e.source_id == "src-1"]
    assert len(src1) == 1
    assert (
        "evidence:design_rationale" in src1[0].usage_locations
        or "regulatory_basis" in src1[0].usage_locations
    )


def test_bibliography_deterministic_order():
    e1 = build_bibliography(_ctx())
    e2 = build_bibliography(_ctx())
    assert [x.reference_id for x in e1] == [x.reference_id for x in e2]
    assert [x.source_id for x in e1] == [x.source_id for x in e2]
    assert e1[0].reference_id.startswith("REF-")


def test_appendix_inventory_has_static_verified_app_forms():
    inv = build_appendix_inventory(ctx=_ctx())
    app_forms = [
        i
        for i in inv
        if (i.block_id or "").startswith("APP.")
        and str(i.type) in {"STATIC_VERIFIED", "FORM"}
    ]
    assert app_forms
    assert any(i.block_id == "APP.T18_T33" for i in app_forms)
    assert any(i.status == STATIC_VERIFIED or i.type == "FORM" for i in app_forms)


def test_appendix_inventory_includes_signatures_slot():
    inv = build_appendix_inventory(ctx=_ctx())
    assert any(i.block_id == "SIGNATURES" for i in inv)


def test_appendix_signatures_resolved_when_persons_present():
    a = _assemble()
    sig = [b for b in _blocks(_section(a, "16")) if b.get("block_code") == "APP.SIGNATURES"]
    assert sig
    assert sig[0].get("resolution_status") == "RESOLVED"
    assert sig[0].get("table_key") == "SIGNATURES"


def test_appendix_signatures_gap_when_missing_people():
    a = _assemble(_ctx(persons=[], organizations=[], sponsor={}))
    texts = _texts(_section(a, "16"))
    assert "{{SIGNATURES}}" in texts


def test_document_completeness_blocked_when_draft_blocked():
    assembled = {"status": "BLOCKED", "sections": []}
    result = assess_document_completeness(assembled, [])
    assert result.readiness == "BLOCKED"
    assert any("BLOCKED" in h for h in result.gate_hints)


def test_document_completeness_ready_when_clean():
    assembled = {
        "status": "READY_FOR_REVIEW",
        "sections": [
            {
                "section_code": "17",
                "content_blocks": [
                    {
                        "resolution_status": "RESOLVED",
                        "content_type": "CANONICAL_VALUE",
                        "text": "ok",
                    }
                ],
            }
        ],
    }
    result = assess_document_completeness(assembled, [])
    assert result.readiness == "READY"
    assert result.resolved_blocks == 1


def test_document_completeness_counts_unresolved():
    assembled = {
        "status": "DRAFT",
        "sections": [
            {
                "section_code": "18",
                "content_blocks": [
                    {
                        "resolution_status": "UNRESOLVED",
                        "unresolved": ["{{SOURCES.LIST}}"],
                        "text": "{{SOURCES.LIST}}",
                        "knowledge_gaps": [
                            {
                                "domain": "SOURCES",
                                "question": "No sources",
                                "importance": "HIGH",
                                "blocking": True,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    result = assess_document_completeness(assembled, [])
    assert result.unresolved_blocks >= 1
    assert result.critical_gaps
    assert result.readiness in {"BLOCKED", "READY_WITH_WARNINGS"}


def test_full_qa_draft_never_forces_final():
    ctx = _ctx(product={})
    a = _assemble(ctx)
    qa = run_full_document_qa(assembled=a, ctx=ctx, mode="DRAFT")
    assert qa.gate == "READY"
    final = run_full_document_qa(assembled=a, ctx=ctx, mode="FINAL")
    assert final.gate == "BLOCKED"


def test_full_qa_detects_forbidden_phrase_injection():
    a = _assemble()
    for s in a["sections"]:
        if s["section_code"] == "16":
            s["content_blocks"].append(
                {
                    "type": "TEXT",
                    "text": "Error! Reference source not found",
                    "resolution_status": "RESOLVED",
                }
            )
    qa = run_full_document_qa(assembled=a, ctx=_ctx(), mode="DRAFT")
    assert any(f.get("code") == "QA.DOC.FORBIDDEN_PLACEHOLDER" for f in qa.findings)


def test_full_qa_detects_raw_enum_injection():
    a = _assemble()
    for s in a["sections"]:
        if s["section_code"] == "17":
            s["content_blocks"].append(
                {
                    "type": "TEXT",
                    "text": "Design CROSSOVER_2X2 leaked",
                    "resolution_status": "RESOLVED",
                }
            )
    qa = run_full_document_qa(assembled=a, ctx=_ctx(), mode="FINAL")
    assert any(f.get("code") == "CONTENT.RAW_ENUM_LEAK" for f in qa.findings)
    assert qa.gate == "BLOCKED"


def test_detect_broken_reference_helper():
    hits = detect_broken_reference_text("see Error! Reference source not found here")
    assert hits
    assert detect_broken_reference_text("normal appendix text") == []


def test_find_raw_enums_helper():
    assert "FASTING" in find_raw_enums_in_text("condition FASTING used")
    assert find_raw_enums_in_text("натощак") == []


def test_targeted_docx_only_sections_16_17_18(tmp_path):
    from app.domain.docx_renderer import render_protocol_docx

    ctx = _ctx()
    full = assemble_protocol(ctx, blocking_validation=False)
    result = render_protocol_docx(
        protocol_payload=full,
        study_ctx=ctx,
        mode="DRAFT",
        output_dir=tmp_path,
        project_slug="12b4-targeted",
        protocol_version="1",
        only_sections=["16", "17", "18"],
    )
    assert result.status == "READY", result.blocking_reasons
    assert Path(result.output_path).stat().st_size > 0


def test_full_docx_draft_when_identity_present(tmp_path):
    from app.domain.docx_renderer import render_protocol_docx

    ctx = _ctx()
    assert (ctx["study"] or {}).get("protocol_number")
    assert (ctx["product"] or {}).get("trade_name")
    a = assemble_protocol(ctx, blocking_validation=False)
    result = render_protocol_docx(
        protocol_payload=a,
        study_ctx=ctx,
        mode="DRAFT",
        output_dir=tmp_path,
        project_slug="12b4-draft-full",
        protocol_version="1",
    )
    assert result.status == "READY", result.blocking_reasons


def test_only_sections_present_in_docx_and_qa_sources():
    docx = (DOMAIN / "docx_renderer.py").read_text(encoding="utf-8")
    assert "only_sections" in docx
    assert "def render_protocol_docx" in docx
    qa = (DOMAIN / "full_document_qa.py").read_text(encoding="utf-8")
    assert "run_full_document_qa" in qa
    assert "FINAL" in qa
    assert "Does not force FINAL" in qa or "never force" in qa.lower()


def test_literature_numbered_list_items_from_sources():
    a = _assemble()
    items = []
    for b in _blocks(_section(a, "18")):
        if b.get("block_code") == "SOURCES.LIST":
            items = list(b.get("items") or [])
    assert items
    assert any("EMA" in it or "Guideline" in it or "ICH" in it for it in items)


def test_conclusion_includes_periods_and_n_when_known():
    text = _texts(_section(_assemble(), "17"))
    assert "период" in text.lower() or "2" in text
    assert "28" in text
    assert "TestDrug" in text
    assert "RefDrug" in text


def test_appendix_reference_block_when_forms_present():
    a = _assemble()
    refs = [b for b in _blocks(_section(a, "16")) if b.get("type") == "REFERENCE"]
    assert refs
    assert refs[0].get("target_type") == "appendix"


def test_api_golden_generate_sections_16_18(client):
    pid = client.post("/api/projects", json={"name": "12B4-sec"}).json()["id"]
    client.put(
        f"/api/projects/{pid}/study",
        json={"protocol_number": "BE-12B4-G", "title": "Golden 12B4", "version": "1.0"},
    )
    client.put(
        f"/api/projects/{pid}/product",
        json={"trade_name": "TestDrug", "inn": "x", "dosage": "100 mg", "dosage_form": "tablet"},
    )
    client.put(
        f"/api/projects/{pid}/reference-product",
        json={"trade_name": "RefDrug", "inn": "x", "dosage": "100 mg", "dosage_form": "tablet"},
    )
    client.post(
        f"/api/projects/{pid}/design",
        json={"type": "CROSSOVER_2X2", "periods": 2, "sequences": [["T", "R"], ["R", "T"]]},
    )
    gen = client.post(
        f"/api/projects/{pid}/content/generate-sections-16-18",
        json={"persist": False, "mode": "DRAFT"},
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert body["mutates_study"] is False
    codes = {s.get("section_code") for s in body["sections"]}
    assert {"16", "17", "18"} <= codes
    assert "qa_report" in body
    assert "completeness" in body


def test_api_golden_generate_full_document(client):
    pid = client.post("/api/projects", json={"name": "12B4-full"}).json()["id"]
    client.put(
        f"/api/projects/{pid}/study",
        json={"protocol_number": "BE-12B4-F", "title": "Full 12B4", "version": "1.0"},
    )
    client.put(
        f"/api/projects/{pid}/product",
        json={"trade_name": "TestDrug", "inn": "x", "dosage": "100 mg", "dosage_form": "tablet"},
    )
    client.put(
        f"/api/projects/{pid}/reference-product",
        json={"trade_name": "RefDrug", "inn": "x", "dosage": "100 mg", "dosage_form": "tablet"},
    )
    client.post(
        f"/api/projects/{pid}/design",
        json={"type": "CROSSOVER_2X2", "periods": 2, "sequences": [["T", "R"], ["R", "T"]]},
    )
    client.post(f"/api/projects/{pid}/food", json={"condition": "FASTING"})
    client.post(
        f"/api/projects/{pid}/subjects",
        json={
            "target_evaluable_n": 24,
            "planned_randomized_n": 28,
            "reserve_n": 0,
            "planned_screened_n": 40,
        },
    )
    gen = client.post(
        f"/api/projects/{pid}/content/generate-full-document",
        json={"persist": False, "mode": "DRAFT"},
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert body["mutates_study"] is False
    assert body["sections"]
    assert body.get("qa_report")
    assert body.get("gate") in {"READY", "BLOCKED"}
    assert body.get("readiness") in {"READY", "READY_WITH_WARNINGS", "BLOCKED"}


def test_api_docx_targeted_16_17_18(client):
    pid = client.post("/api/projects", json={"name": "12B4-docx"}).json()["id"]
    client.put(
        f"/api/projects/{pid}/study",
        json={"protocol_number": "BE-12B4-D", "title": "Docx 12B4", "version": "1.0"},
    )
    client.put(
        f"/api/projects/{pid}/product",
        json={"trade_name": "TestDrug", "inn": "x", "dosage": "100 mg", "dosage_form": "tablet"},
    )
    client.put(
        f"/api/projects/{pid}/reference-product",
        json={"trade_name": "RefDrug", "inn": "x", "dosage": "100 mg", "dosage_form": "tablet"},
    )
    client.post(
        f"/api/projects/{pid}/design",
        json={"type": "CROSSOVER_2X2", "periods": 2, "sequences": [["T", "R"], ["R", "T"]]},
    )
    client.post(
        f"/api/projects/{pid}/content/generate-sections-16-18",
        json={"persist": True, "mode": "DRAFT"},
    )
    docx = client.post(
        f"/api/projects/{pid}/protocol/docx/build",
        json={"mode": "DRAFT", "only_sections": ["16", "17", "18"]},
    )
    assert docx.status_code == 200, docx.text
    assert docx.json()["status"] == "READY", docx.json()


def test_section_tree_codes_16_17_18_titles():
    from app.domain.protocol_sections import SECTION_BY_CODE

    assert SECTION_BY_CODE["16"].generator == "appendices"
    assert SECTION_BY_CODE["17"].generator == "conclusion"
    assert SECTION_BY_CODE["17"].title
    assert SECTION_BY_CODE["18"].generator == "literature"


def test_n_mismatch_flagged_when_injected():
    ctx = _ctx()
    a = _assemble(ctx)
    for s in a["sections"]:
        if s["section_code"] == "17":
            s["content_blocks"].append(
                {
                    "type": "TEXT",
                    "text": "рандомизированных субъектов: 99",
                    "resolution_status": "RESOLVED",
                }
            )
    qa = run_full_document_qa(
        assembled=a,
        ctx=ctx,
        canonical=_canonical_from_ctx(ctx),
        mode="DRAFT",
    )
    assert any(f.get("code") == "CONTENT.CANONICAL_MISMATCH" for f in qa.findings)

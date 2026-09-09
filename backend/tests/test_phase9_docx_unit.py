"""Phase 9 DOCX renderer unit tests."""

from __future__ import annotations

from pathlib import Path

from app.domain.docx_profile import TEMPLATE_CHECKSUM_SHA256, get_template_profile
from app.domain.docx_renderer import (
    _assign_table_numbers,
    _gate_mode,
    _resolve_reference_display,
    render_protocol_docx,
)
from app.domain.docx_validation import validate_docx_file
from app.domain.document_ingest import sha256_hex


def test_template_profile_checksum() -> None:
    profile = get_template_profile()
    path = profile.template_path()
    assert path.exists()
    assert sha256_hex(path.read_bytes()) == TEMPLATE_CHECKSUM_SHA256
    assert profile.file_checksum == TEMPLATE_CHECKSUM_SHA256


def test_table_numbering_dynamic() -> None:
    tables = [
        {"table_key": "B", "order": 2},
        {"table_key": "A", "order": 1},
    ]
    nums = _assign_table_numbers(tables)
    assert nums["A"] == 1
    assert nums["B"] == 2
    assert _resolve_reference_display(
        {"target_type": "table", "target_id": "A"}, nums
    ) == "см. Таблицу 1"


def test_final_blocks_without_sponsor() -> None:
    reasons = _gate_mode(
        "FINAL",
        draft_status="DRAFT",
        unresolved=["{{SPONSOR.NAME}}"],
        consistency={"evaluable_n": 24, "design": "CROSSOVER_2X2"},
        study={"protocol_number": "BE-001"},
        product={"trade_name": "T"},
        reference={"trade_name": "R"},
        sponsor=None,
    )
    assert any("sponsor" in r for r in reasons)


def test_draft_blocks_missing_protocol_number() -> None:
    reasons = _gate_mode(
        "DRAFT",
        draft_status="DRAFT",
        unresolved=[],
        consistency={},
        study={},
        product={"trade_name": "T"},
        reference={"trade_name": "R"},
        sponsor=None,
    )
    assert "missing protocol_number" in reasons


def test_render_draft_docx(tmp_path: Path) -> None:
    payload = {
        "status": "DRAFT",
        "sections": [
            {
                "section_code": "4.4.2",
                "title": "Blood sampling",
                "order": 442,
                "parent_section": "4.4",
                "status": "GENERATED",
                "generation_status": "OK",
                "content_blocks": [
                    {
                        "type": "TEXT",
                        "text": "Sampling plan includes 2 points.",
                        "items": [],
                        "unresolved": [],
                    },
                    {
                        "type": "TABLE",
                        "table_key": "BLOOD_SAMPLING",
                        "display_text": "Таблица 1",
                        "items": [],
                        "unresolved": [],
                    },
                ],
                "source_ids": [],
                "warnings": [],
            },
            {
                "section_code": "9.2",
                "title": "Sample size",
                "order": 920,
                "parent_section": "9",
                "status": "GENERATED",
                "generation_status": "OK",
                "content_blocks": [
                    {
                        "type": "TEXT",
                        "text": "N=24 evaluable.",
                        "origin": "CALCULATED",
                        "rule_id": "STATISTICS.SAMPLE_SIZE",
                        "items": [],
                        "unresolved": [],
                    }
                ],
                "source_ids": [],
                "warnings": [],
            },
        ],
        "tables": [
            {
                "table_key": "BLOOD_SAMPLING",
                "order": 1,
                "columns": ["#", "Time (h)", "Reason"],
                "rows": [[1, 0, "predose"], [2, 2, "tmax"]],
                "section_code": "4.4.2",
                "title": "Blood sampling",
            },
            {
                "table_key": "TEST_PRODUCT",
                "order": 2,
                "columns": ["Attribute", "Value"],
                "rows": [["Trade name", "Bosutinib-T"], ["Dosage", "400 mg"]],
                "section_code": "2.1.1",
                "title": "Test product",
            },
            {
                "table_key": "REFERENCE_PRODUCT",
                "order": 3,
                "columns": ["Attribute", "Value"],
                "rows": [["Trade name", "Bosulif"], ["Dosage", "400 mg"]],
                "section_code": "2.1.2",
                "title": "Reference",
            },
        ],
        "references": [
            {
                "source_section": "4.4.2",
                "target_type": "table",
                "target_id": "BLOOD_SAMPLING",
                "display_text": "см. таблицу",
            }
        ],
        "consistency_snapshot": {
            "design": "CROSSOVER_2X2",
            "evaluable_n": 24,
            "food_condition": "FED",
        },
        "build_report": {"unresolved_fields": []},
    }
    ctx = {
        "study": {"protocol_number": "BE-BOS-001", "title": "Bosutinib BE", "version": "1"},
        "product": {"trade_name": "Bosutinib-T", "inn": "bosutinib", "dosage": "400 mg"},
        "reference_product": {"trade_name": "Bosulif", "inn": "bosutinib", "dosage": "400 mg"},
        "sponsor": None,
    }
    result = render_protocol_docx(
        protocol_payload=payload,
        study_ctx=ctx,
        mode="DRAFT",
        output_dir=tmp_path,
        project_slug="bosutinib",
        protocol_version="1",
    )
    assert result.status == "READY", result.blocking_reasons
    assert result.output_path and result.output_path.exists()
    assert result.checksum
    assert result.table_numbers["BLOOD_SAMPLING"] == 1
    # template not modified
    profile = get_template_profile()
    assert sha256_hex(profile.template_path().read_bytes()) == TEMPLATE_CHECKSUM_SHA256

    report = validate_docx_file(result.output_path, allow_unresolved=True)
    assert report.table_count == 33
    assert report.paragraph_count > 0
    assert "word/document.xml"  # opened OK
    # no invented placeholders
    from docx import Document

    blob = "\n".join(p.text for p in Document(str(result.output_path)).paragraphs)
    assert "примерно" not in blob.lower()


def test_final_blocked_when_unresolved(tmp_path: Path) -> None:
    payload = {
        "status": "DRAFT",
        "sections": [
            {
                "section_code": "1.2",
                "title": "Sponsor",
                "order": 120,
                "content_blocks": [
                    {"type": "TEXT", "text": "{{SPONSOR.NAME}}", "items": [], "unresolved": ["{{SPONSOR.NAME}}"]}
                ],
                "source_ids": [],
                "warnings": [],
                "status": "UNRESOLVED",
                "generation_status": "UNRESOLVED",
            }
        ],
        "tables": [],
        "references": [],
        "consistency_snapshot": {"design": "CROSSOVER_2X2", "evaluable_n": 24},
        "build_report": {"unresolved_fields": ["{{SPONSOR.NAME}}"]},
    }
    ctx = {
        "study": {"protocol_number": "BE-001"},
        "product": {"trade_name": "T"},
        "reference_product": {"trade_name": "R"},
        "sponsor": None,
    }
    result = render_protocol_docx(
        protocol_payload=payload,
        study_ctx=ctx,
        mode="FINAL",
        output_dir=tmp_path,
    )
    assert result.status == "BLOCKED"
    assert result.output_path is None

"""Phase 8 protocol assembly unit tests — no DOCX."""

from __future__ import annotations

from app.domain.protocol_assembly import assemble_protocol
from app.domain.protocol_conditions import conditions_pass, eval_condition
from app.domain.protocol_consistency import find_unresolved_markers, scan_forbidden_placeholders
from app.domain.protocol_sections import SECTION_TREE, mapping_as_list
from app.domain.protocol_text_blocks import TEXT_BLOCKS


def _minimal_ctx(**overrides):
    ctx = {
        "project_id": "p1",
        "study": {"protocol_number": "BE-001", "title": "Minimal", "version": "1"},
        "product": {"trade_name": "Test", "inn": "x", "dosage": "100 mg", "source_ids": ["s1"]},
        "reference_product": {
            "trade_name": "Ref",
            "inn": "x",
            "dosage": "100 mg",
            "purchased_status": "UNKNOWN",
            "source_ids": ["s2"],
        },
        "design": {
            "type": "CROSSOVER_2X2",
            "periods": 2,
            "sequences": [["T", "R"], ["R", "T"]],
            "treatments": ["T", "R"],
            "food_condition": "FED",
            "source_ids": [],
        },
        "food": {"condition": "FED", "meal_type": "HIGH_CALORIE"},
        "subjects": {"target_evaluable_n": 24, "planned_randomized_n": 28, "planned_screened_n": 40},
        "eligibility": {"inclusion": [{"number": 1, "text": "HV"}], "non_inclusion": [], "exclusion": []},
        "analytes": [
            {
                "id": "a1",
                "name": "bosutinib",
                "type": "PARENT",
                "tmax_min": 2,
                "tmax_max": 3,
                "tmax_unit": "h",
                "half_life_min": 10,
                "half_life_max": 12,
            }
        ],
        "pk_parameters": [
            {
                "analyte_id": "a1",
                "parameter_code": "Tmax",
                "range_min": 2,
                "range_max": 3,
                "unit": "h",
            }
        ],
        "washout": {"selected_value": 5, "unit": "day", "calculated_minimum": 5},
        "observation": {"selected_duration": 36, "selected_unit": "h"},
        "sampling": {"points": [{"time_h": 0, "reason": "predose"}, {"time_h": 2, "reason": "tmax"}]},
        "sample_size": {
            "evaluable_n": 24,
            "randomized_n": 28,
            "dropout_pct": 10,
            "cv_used": 25,
            "parameter": "Cmax",
        },
        "cv_selection": {"selected_cv": 25, "parameter": "Cmax", "selection_method": "SINGLE_STUDY"},
        "cv_studies": [],
        "sources": [{"id": "s1", "type": "SmPC", "title": "Label"}],
        "blood_volume": {},
        "statistical_config": {},
        "evidence_summary": {"count": 0},
    }
    ctx.update(overrides)
    return ctx


def test_section_tree_and_mapping_backend_only() -> None:
    assert any(s.section_code == "4.4.2" for s in SECTION_TREE)
    assert any(s.section_code == "9.2" for s in SECTION_TREE)
    assert any(s.section_code == "SYNOPSIS" for s in SECTION_TREE)
    rows = mapping_as_list()
    samp = next(r for r in rows if r["section_code"] == "4.4.2")
    assert samp["template_key"] == "SAMPLING_PLAN"
    assert "sampling" in samp["required_data"]


def test_conditional_design_and_food() -> None:
    ctx = _minimal_ctx()
    assert eval_condition("design == CROSSOVER_2X2", ctx)
    assert eval_condition("food == FED", ctx)
    assert conditions_pass(("design_crossover_2x2",), ctx)
    ctx_par = _minimal_ctx(design={"type": "PARALLEL", "periods": 1, "treatments": ["T", "R"]})
    assert eval_condition("design == PARALLEL", ctx_par)
    assert not eval_condition("crossover", ctx_par)


def test_build_minimal_protocol() -> None:
    result = assemble_protocol(_minimal_ctx(), blocking_validation=False)
    assert result["generator_version"]
    assert result["sections"]
    assert result["tables"]
    assert result["canonical_fingerprint"]
    codes = {s["section_code"] for s in result["sections"]}
    assert "SYNOPSIS" in codes
    assert "4.4.2" in codes
    assert "9.2" in codes


def test_build_complete_2x2_deterministic() -> None:
    ctx = _minimal_ctx()
    a = assemble_protocol(ctx, blocking_validation=False)
    b = assemble_protocol(ctx, blocking_validation=False)
    assert a["canonical_fingerprint"] == b["canonical_fingerprint"]
    assert a["status"] == b["status"]
    assert len(a["sections"]) == len(b["sections"])
    assert [t["table_key"] for t in a["tables"]] == [t["table_key"] for t in b["tables"]]


def test_fed_vs_fasting_blocks() -> None:
    fed = assemble_protocol(_minimal_ctx(), blocking_validation=False)
    fasting = assemble_protocol(
        _minimal_ctx(food={"condition": "FASTING", "meal_type": None}, design={
            "type": "CROSSOVER_2X2",
            "periods": 2,
            "sequences": [["T", "R"], ["R", "T"]],
            "treatments": ["T", "R"],
            "food_condition": "FASTING",
        }),
        blocking_validation=False,
    )
    fed_food = next(s for s in fed["sections"] if s["section_code"] == "6.2.1")
    fast_food = next(s for s in fasting["sections"] if s["section_code"] == "6.2.1")
    fed_text = " ".join(str(b.get("text") or "") for b in fed_food["content_blocks"])
    fast_text = " ".join(str(b.get("text") or "") for b in fast_food["content_blocks"])
    assert "FED" in fed_text or "пищи" in fed_text.lower() or "food" in fed_text.lower()
    assert "FASTING" in fast_text or "натощак" in fast_text.lower()


def test_multiple_analytes_conditional() -> None:
    ctx = _minimal_ctx(
        analytes=[
            {"id": "a1", "name": "parent", "type": "PARENT", "tmax_min": 1, "tmax_max": 2},
            {"id": "a2", "name": "metab", "type": "ACTIVE_METABOLITE", "tmax_min": 2, "tmax_max": 4},
        ]
    )
    assert eval_condition("analyte_count > 1", ctx)
    result = assemble_protocol(ctx, blocking_validation=False)
    sec = next(s for s in result["sections"] if s["section_code"] == "7.1")
    blob = str(sec["content_blocks"])
    assert "parent" in blob and "metab" in blob


def test_missing_reference_unresolved() -> None:
    ctx = _minimal_ctx(reference_product=None)
    result = assemble_protocol(ctx, blocking_validation=False)
    ref = next(s for s in result["sections"] if s["section_code"] == "2.1.2")
    assert ref["generation_status"] == "UNRESOLVED" or any(
        "{{REFERENCE" in str(b) for b in ref["content_blocks"]
    )
    assert result["status"] in {"DRAFT", "BLOCKED"}


def test_missing_pk_and_sampling() -> None:
    ctx = _minimal_ctx(pk_parameters=[], analytes=[], sampling={"points": []})
    result = assemble_protocol(ctx, blocking_validation=False)
    codes = {i.get("code") for i in result["build_report"]["blocking_issues"]}
    assert "MISSING_REQUIRED_DATA" in codes or result["status"] == "BLOCKED"


def test_blocking_validation_prevents_ready() -> None:
    result = assemble_protocol(
        _minimal_ctx(),
        blocking_validation=True,
        validation_issues=[{"blocking": True, "rule_id": "X", "message": "bad", "field": "design"}],
    )
    assert result["status"] == "BLOCKED"


def test_table_numbering_dynamic() -> None:
    result = assemble_protocol(_minimal_ctx(), blocking_validation=False)
    numbers = [t["display_number"] for t in result["tables"]]
    assert numbers == list(range(1, len(numbers) + 1))
    assert all("Таблица" not in t["title"] for t in result["tables"])
    # content references use computed number
    for s in result["sections"]:
        for b in s["content_blocks"]:
            if b.get("type") == "TABLE" and b.get("table_number"):
                assert isinstance(b["table_number"], int)


def test_cross_references_and_source_attribution() -> None:
    result = assemble_protocol(_minimal_ctx(), blocking_validation=False)
    assert result["references"]
    assert any(r["target_type"] in {"section", "table", "appendix"} for r in result["references"])
    src_secs = [s for s in result["sections"] if s["source_ids"]]
    assert src_secs
    calc = result["build_report"]["calculated_values"]
    assert calc
    assert any(c.get("rule_id") for c in calc)


def test_no_forbidden_placeholders() -> None:
    result = assemble_protocol(_minimal_ctx(), blocking_validation=False)
    blob = str(result)
    assert "ХХ" not in blob
    assert "примерно" not in blob.lower()
    assert scan_forbidden_placeholders("value XXX here")


def test_unresolved_markers() -> None:
    assert "{{SPONSOR.NAME}}" in find_unresolved_markers("Спонсор: {{SPONSOR.NAME}}")


def test_text_blocks_versioned() -> None:
    assert "CROSSOVER_DESCRIPTION" in TEXT_BLOCKS
    assert TEXT_BLOCKS["SAMPLE_SIZE_RATIONALE"].version == "v1"


def test_snapshot_reproducibility() -> None:
    ctx = _minimal_ctx()
    a = assemble_protocol(ctx, blocking_validation=False)
    b = assemble_protocol(ctx, blocking_validation=False)
    assert a["build_report"]["snapshot_fingerprint"] == b["build_report"]["snapshot_fingerprint"]

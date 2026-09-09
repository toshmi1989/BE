"""Phase 11A — Canonical consistency, registries, display values."""

from __future__ import annotations

from app.domain.canonical_consistency import validate_canonical_consistency
from app.domain.canonical_sampling import get_canonical_sampling_plan
from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.display_value_registry import (
    find_raw_enums_in_text,
    resolve_display,
)
from app.domain.eligibility_render import render_eligibility_list
from app.domain.placeholder_registry import classify_placeholder, extract_placeholders
from app.domain.product_mapping import (
    build_test_product_rows,
    field_for_label,
    product_values_by_field,
)
from app.domain.protocol_conditions import build_variable_map
from app.domain.protocol_tables import build_tables
from app.domain.reference_registry import build_reference_registry, detect_broken_reference_text
from app.domain.study_snapshot import build_canonical_snapshot, build_consistency_snapshot
from app.domain.table_registry import build_table_registry


def _base_ctx(**overrides):
    ctx = {
        "project_id": "p1",
        "study": {"protocol_number": "BE-TEST", "title": "Test"},
        "product": {
            "trade_name": "Бозутиниб",
            "inn": "bosutinib",
            "manufacturer": "ООО Тест",
            "dosage": "400 mg",
            "dosage_form": "tablet",
        },
        "reference_product": {
            "trade_name": "Бозулиф",
            "inn": "bosutinib",
            "manufacturer": "Pfizer",
            "dosage": "400 mg",
            "dosage_form": "tablet",
            "purchased_status": "UNKNOWN",
        },
        "design": {
            "type": "CROSSOVER_2X2",
            "periods": 2,
            "sequences": [["T", "R"], ["R", "T"]],
        },
        "food": {"condition": "FED", "meal_type": "HIGH_CALORIE", "calories": 900, "fat_percent": 50},
        "subjects": {
            "target_evaluable_n": 32,
            "planned_randomized_n": 36,
            "planned_screened_n": 36,
            "reserve_n": 0,
        },
        "sample_size": {
            "evaluable_n": 32,
            "randomized_n": 36,
            "screened_n": 36,
            "selected_cv": 30,
            "parameter": "Cmax",
            "inputs_snapshot": {"dropout_pct": 10},
        },
        "sampling": {
            "points": [
                {"time_h": 0.0, "reason": "BASELINE"},
                {"time_h": 6.0, "reason": "TMAX_CAPTURE"},
                {"time_h": 72.0, "reason": "FINAL"},
            ],
            "total_points_per_period": 3,
            "final_observation_h": 72,
            "status": "PROPOSED",
            "rationale": "test",
        },
        "observation": {"selected_duration": 72, "unit": "h"},
        "analytes": [{"id": "a1", "name": "bosutinib", "type": "PARENT"}],
        "pk_parameters": [
            {"analyte_id": "a1", "parameter_code": "Tmax", "range_min": 6, "range_max": 6}
        ],
        "eligibility": {
            "inclusion": [{"id": "1", "text": "Возраст 18–45", "sort_order": 1}],
            "non_inclusion": [],
            "exclusion": [{"id": "2", "text": "Беременность", "sort_order": 1}],
        },
        "cv_selection": {"selected_cv": 30, "parameter": "Cmax"},
        "blood_volume": {"sampling_points_per_period": 3},
    }
    ctx.update(overrides)
    return ctx


def test_canonical_snapshot_reproducible():
    ctx = _base_ctx()
    a = build_canonical_snapshot(ctx)
    b = build_canonical_snapshot(ctx)
    assert a.fingerprint() == b.fingerprint()
    assert a.randomized_n == 36
    assert a.schema_version == "2"


def test_subject_plan_is_canonical_over_sample_size():
    ctx = _base_ctx(
        subjects={
            "target_evaluable_n": 24,
            "planned_randomized_n": 28,
            "planned_screened_n": 40,
            "reserve_n": 0,
        },
        sample_size={"evaluable_n": 32, "randomized_n": 36, "screened_n": 36},
    )
    counts = get_canonical_subject_counts(ctx)
    assert counts.randomized_n == 28
    assert counts.source == "subject_plan"
    assert counts.diverges_from_sample_size is True
    snap = build_consistency_snapshot(ctx)
    assert snap["randomized_n"] == 28


def test_n_consistency_across_variables_and_tables():
    ctx = _base_ctx()
    consistency = build_consistency_snapshot(ctx)
    variables = build_variable_map(ctx, consistency)
    tables = build_tables(ctx, consistency)
    assert variables["randomized_n"] == 36
    assert variables["evaluable_n"] == 32
    syn_n = next(t for t in tables if t["table_key"] == "SYNOPSIS_N")
    meta = next(t for t in tables if t["table_key"] == "STUDY_METADATA")
    assert any("36" in str(c) for row in syn_n["rows"] for c in row)
    assert any("36" in str(c) for row in meta["rows"] for c in row)
    report = validate_canonical_consistency(
        ctx, consistency=consistency, sections=[], tables=tables
    )
    subjects_domain = next(d for d in report.domains if d.domain == "SUBJECTS")
    assert subjects_domain.status == "PASS"


def test_sampling_canonical_single_source():
    ctx = _base_ctx()
    plan = get_canonical_sampling_plan(ctx)
    assert plan.points_per_period == 3
    assert plan.points[2]["reason"] == "FINAL"
    assert plan.points[2]["reason_display"]  # humanized
    assert "TERMINAL_PHASE" not in plan.points[2]["reason_display"]
    assert "FINAL" not in plan.points[2]["reason_display"]
    consistency = build_consistency_snapshot(ctx)
    tables = build_tables(ctx, consistency)
    blood = next(t for t in tables if t["table_key"] == "BLOOD_SAMPLING")
    times = [row[1] for row in blood["rows"]]
    assert times == [0.0, 6.0, 72.0]
    # no raw TERMINAL_PHASE / FINAL enum in reason column
    reasons = " ".join(str(row[2]) for row in blood["rows"])
    assert "TERMINAL_PHASE" not in reasons
    assert "FINAL" not in reasons or "финальн" in reasons.lower()


def test_product_field_mapping_manufacturer_not_inn():
    rows = build_test_product_rows(
        {
            "trade_name": "Бозутиниб",
            "manufacturer": "ООО Тест",
            "inn": "bosutinib",
            "dosage": "400 mg",
            "dosage_form": "tablet",
        }
    )
    by_label = {r[0]: r[1] for r in rows}
    assert by_label["Производитель"] == "ООО Тест"
    assert by_label["МНН"] == "bosutinib"
    assert by_label["Дозировка"] == "400 mg"
    assert field_for_label("Производитель:") == "manufacturer"
    assert field_for_label("МНН") == "inn"
    vals = product_values_by_field(
        {"trade_name": "X", "manufacturer": "M", "inn": "I"}, is_reference=False
    )
    assert vals["manufacturer"] == "M"
    assert vals["inn"] == "I"


def test_reference_purchased_humanized():
    ctx = _base_ctx()
    consistency = build_consistency_snapshot(ctx)
    tables = build_tables(ctx, consistency)
    ref = next(t for t in tables if t["table_key"] == "REFERENCE_PRODUCT")
    blob = " ".join(str(c) for row in ref["rows"] for c in row)
    assert "UNKNOWN" not in blob
    assert "неизвестен" in blob.lower() or "закупк" in blob.lower()


def test_food_and_design_display_no_raw_enums_in_variables():
    ctx = _base_ctx()
    variables = build_variable_map(ctx, build_consistency_snapshot(ctx))
    assert variables["design_type"] != "CROSSOVER_2X2"
    assert "перекр" in variables["design_type"].lower() or "2×2" in variables["design_type"]
    assert variables["food_condition"] != "FED"
    assert variables["meal_type"] != "HIGH_CALORIE"
    assert find_raw_enums_in_text(str(variables["design_type"])) == []
    assert find_raw_enums_in_text(str(variables["food_condition"])) == []


def test_eligibility_render_ordering_and_empty():
    items = render_eligibility_list(
        [
            {"id": "b", "text": "Second", "sort_order": 2},
            {"id": "a", "text": "First", "sort_order": 1},
        ]
    )
    assert items[0].startswith("1. First")
    assert items[1].startswith("2. Second")
    assert render_eligibility_list([]) == []
    assert render_eligibility_list([], empty_placeholder="{{ELIGIBILITY.EXCLUSION}}") == [
        "{{ELIGIBILITY.EXCLUSION}}"
    ]


def test_enum_display_resolution():
    assert "перекр" in resolve_display("CROSSOVER_2X2", context="design").lower()
    assert resolve_display("FED", context="food")
    assert "терминальн" in resolve_display("TERMINAL_PHASE", context="sampling_reason").lower()


def test_placeholder_classification():
    c = classify_placeholder("{{SPONSOR.NAME}}")
    assert c.blocks_final is True
    markers = extract_placeholders({"a": "x {{STUDY.PROTOCOL_NUMBER}} y"})
    assert "{{STUDY.PROTOCOL_NUMBER}}" in markers


def test_broken_reference_detection():
    assert detect_broken_reference_text("Error! Reference source not found")
    reg = build_reference_registry(
        [{"target_type": "table", "target_id": "MISSING"}],
        table_registry=build_table_registry([]),
    )
    assert reg.unresolved()


def test_table_registry_numbering_and_omit():
    tables = [
        {"table_key": "A", "title": "A", "section_code": "1", "order": 2, "status": "GENERATED"},
        {"table_key": "B", "title": "B", "section_code": "2", "order": 1, "status": "GENERATED"},
        {
            "table_key": "C",
            "title": "C",
            "section_code": "3",
            "order": 3,
            "status": "CONDITIONAL_OMITTED",
        },
    ]
    reg = build_table_registry(tables)
    assert reg.number_for("B") == 1
    assert reg.number_for("A") == 2
    assert reg.number_for("C") == 0 or reg.by_key()["C"].actual_number == 0
    assert reg.display_text("B") == "Таблица 1"


def test_divergence_report_error():
    ctx = _base_ctx(
        subjects={
            "target_evaluable_n": 24,
            "planned_randomized_n": 46,
            "planned_screened_n": 50,
        },
        sample_size={"evaluable_n": 32, "randomized_n": 36, "screened_n": 36},
    )
    report = validate_canonical_consistency(ctx, sections=[], tables=[])
    subjects = next(d for d in report.domains if d.domain == "SUBJECTS")
    assert subjects.status == "ERROR"
    assert "46" in subjects.message and "36" in subjects.message


def test_assembled_protocol_no_raw_enums_and_n_aligned():
    from app.domain.protocol_assembly import assemble_protocol

    ctx = _base_ctx()
    out = assemble_protocol(ctx, blocking_validation=False)
    blob_parts = []
    for s in out["sections"]:
        for b in s.get("content_blocks") or []:
            if b.get("text"):
                blob_parts.append(str(b["text"]))
            for item in b.get("items") or []:
                blob_parts.append(str(item))
    for t in out["tables"]:
        for row in t.get("rows") or []:
            blob_parts.extend(str(c) for c in row)
    blob = "\n".join(blob_parts)
    raw = find_raw_enums_in_text(blob)
    # Allow none of the protocol enums
    assert "CROSSOVER_2X2" not in raw
    assert "FED" not in raw
    assert "HIGH_CALORIE" not in raw
    assert "TERMINAL_PHASE" not in raw
    assert str(out["consistency_snapshot"]["randomized_n"]) in blob
    assert out["document_consistency"]["ok"] or not any(
        d["domain"] == "SUBJECTS" and d["status"] == "ERROR"
        for d in out["document_consistency"]["domains"]
    )

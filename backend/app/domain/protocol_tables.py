"""Dynamic protocol tables — numbered at assembly time via table_key."""

from __future__ import annotations

from typing import Any

from app.domain.canonical_sampling import get_canonical_sampling_plan
from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.display_value_registry import resolve_display
from app.domain.org_render import signature_table_rows
from app.domain.product_mapping import build_reference_product_rows, build_test_product_rows
from app.domain.synopsis_fill import build_synopsis_admin_rows, build_synopsis_n_metric_rows


def build_tables(ctx: dict, consistency: dict) -> list[dict[str, Any]]:
    """Return ordered table specs (table_key, not hardcoded 'Таблица N')."""
    tables: list[dict[str, Any]] = []
    order = 0

    study = ctx.get("study") or {}
    product = ctx.get("product") or {}
    reference = ctx.get("reference_product") or {}
    design = ctx.get("design") or {}
    food = ctx.get("food") or {}
    analytes = ctx.get("analytes") or []
    pk = ctx.get("pk_parameters") or []
    sources = ctx.get("sources") or []
    selection = ctx.get("cv_selection") or {}
    cv_studies = ctx.get("cv_studies") or []
    subjects_c = get_canonical_subject_counts(ctx)
    sampling_c = get_canonical_sampling_plan(ctx)

    def add(
        key: str,
        title: str,
        section_code: str,
        columns: list[str],
        rows: list[list[Any]],
        source_ids: list[str] | None = None,
        *,
        fill_mode: str = "LABEL",
        classification: str = "DYNAMIC",
    ) -> None:
        nonlocal order
        order += 1
        tables.append(
            {
                "table_key": key,
                "title": title,
                "section_code": section_code,
                "order": order,
                "columns": columns,
                "rows": rows,
                "source_ids": source_ids or [],
                "status": "GENERATED",
                "display_number": order,
                "fill_mode": fill_mode,
                "classification": classification,
            }
        )

    design_code = design.get("type")
    design_display = (
        resolve_display(design_code, context="design_short", fallback="{{DESIGN.TYPE}}")
        if design_code
        else "{{DESIGN.TYPE}}"
    )
    food_code = food.get("condition") or design.get("food_condition")
    food_display = (
        resolve_display(food_code, context="food", fallback="{{FOOD.CONDITION}}")
        if food_code
        else "{{FOOD.CONDITION}}"
    )

    add(
        "STUDY_METADATA",
        "Study metadata",
        "SYNOPSIS",
        ["Field", "Value"],
        [
            ["Protocol number", study.get("protocol_number") or "{{STUDY.PROTOCOL_NUMBER}}"],
            ["Title", study.get("title") or study.get("short_title") or "{{STUDY.TITLE}}"],
            ["Design", design_display],
            ["Food", food_display],
            [
                "Evaluable N",
                subjects_c.evaluable_n
                if subjects_c.evaluable_n is not None
                else "{{SUBJECTS.EVALUABLE_N}}",
            ],
            [
                "Randomized N",
                subjects_c.randomized_n
                if subjects_c.randomized_n is not None
                else "{{SUBJECTS.RANDOMIZED_N}}",
            ],
        ],
    )

    add(
        "TEST_PRODUCT",
        "Test product",
        "2.1.1",
        ["Attribute", "Value"],
        build_test_product_rows(product),
        list(product.get("source_ids") or []) if isinstance(product.get("source_ids"), list) else [],
    )

    add(
        "REFERENCE_PRODUCT",
        "Reference product",
        "2.1.2",
        ["Attribute", "Value"],
        build_reference_product_rows(reference),
        list(reference.get("source_ids") or []) if isinstance(reference.get("source_ids"), list) else [],
    )

    pk_rows = []
    for p in pk:
        pk_rows.append(
            [
                p.get("parameter_code") or "{{PK.CODE}}",
                p.get("analyte_id") or "",
                p.get("range_min"),
                p.get("range_max"),
                p.get("unit") or "",
            ]
        )
    if not pk_rows and analytes:
        for a in analytes:
            pk_rows.append(
                [
                    "Tmax",
                    a.get("name"),
                    a.get("tmax_min"),
                    a.get("tmax_max"),
                    a.get("tmax_unit") or "h",
                ]
            )
    if not pk_rows:
        pk_rows = [["{{PK.PARAMETER}}", "{{ANALYTE}}", None, None, ""]]
    add(
        "PK_PARAMETERS",
        "PK parameters",
        "4.1",
        ["Parameter", "Analyte", "Min", "Max", "Unit"],
        pk_rows,
        fill_mode="REBUILD",
    )

    points = sampling_c.points
    samp_rows = [
        [
            i + 1,
            p.get("time_h"),
            p.get("reason_display")
            or resolve_display(
                p.get("reason"), context="sampling_reason", fallback=str(p.get("reason") or "")
            ),
        ]
        for i, p in enumerate(points)
    ]
    if not samp_rows:
        samp_rows = [["{{SAMPLING.POINT}}", "{{SAMPLING.TIME_H}}", ""]]
    add(
        "BLOOD_SAMPLING",
        "Blood sampling",
        "4.4.2",
        ["#", "Time (h)", "Reason"],
        samp_rows,
        fill_mode="REBUILD",
    )

    add(
        "SYNOPSIS_N",
        "Subject numbers",
        "SYNOPSIS",
        ["Metric", "Value"],
        build_synopsis_n_metric_rows(ctx, consistency) + build_synopsis_admin_rows(ctx),
    )

    # T04 signatures — DYNAMIC when person/sponsor data present
    sig_rows: list[list[Any]] = signature_table_rows(ctx)
    if sig_rows:
        add(
            "SIGNATURES",
            "Signatures",
            "1.8",
            ["Field", "Value"],
            sig_rows,
            fill_mode="LABEL",
            classification="DYNAMIC",
        )
    else:
        add(
            "SIGNATURES",
            "Signatures",
            "1.8",
            ["Field", "Value"],
            [],
            fill_mode="PRESERVE",
            classification="CONDITIONAL",
        )

    # T08 schedule — STATIC_VERIFIED for standard 2-period crossover; else PRESERVE
    periods = design.get("periods") or 2
    is_crossover = bool(design_code and "CROSSOVER" in str(design_code).upper())
    if is_crossover and int(periods) == 2:
        add(
            "SCHEDULE_OF_ASSESSMENTS",
            "Schedule of assessments",
            "4.2",
            ["Процедура", "Скрининг", "Период 1", "Период 2", "Завершение"],
            [],
            fill_mode="PRESERVE",
            classification="STATIC_VERIFIED",
        )
    else:
        add(
            "SCHEDULE_OF_ASSESSMENTS",
            "Schedule of assessments",
            "4.2",
            ["Процедура"],
            [["{{SCHEDULE.MISMATCH}}"]],
            fill_mode="PRESERVE",
            classification="CONDITIONAL",
        )

    # T12 meal timing — CONDITIONAL on food
    meal_type = str(food.get("meal_type") or "").upper()
    food_u = str(food_code or "").upper()
    if food_u in {"FED", "FED_STATE"} and meal_type in {"HIGH_CALORIE", "HIGH-CALORIE", ""}:
        add(
            "MEAL_TIMING",
            "Meal timing",
            "6.2.1",
            ["Phase", "Timing", "Action"],
            [],
            fill_mode="PRESERVE",
            classification="STATIC_VERIFIED",
        )
    elif food_u in {"FASTING", "FASTED"}:
        water = food.get("water_volume_ml") or 200
        rows = [
            ["До приема препарата", "не менее чем за 10 часов", "голодание"],
            ["", "за 1 час", f"прием {water} мл воды"],
            ["Во время дозирования", "совместно с препаратом", f"прием {water} мл воды"],
            ["После приема препарата", "через 4 часа", "прием пищи разрешён"],
        ]
        add(
            "MEAL_TIMING",
            "Meal timing",
            "6.2.1",
            ["Phase", "Timing", "Action"],
            rows,
            fill_mode="REBUILD",
            classification="DYNAMIC",
        )
    else:
        add(
            "MEAL_TIMING",
            "Meal timing",
            "6.2.1",
            ["Phase", "Timing", "Action"],
            [["{{FOOD.MEAL_TIMING}}", "", ""]],
            fill_mode="PRESERVE",
            classification="CONDITIONAL",
        )

    cv_rows = []
    for c in cv_studies:
        cv_rows.append(
            [
                c.get("parameter"),
                c.get("cv_value"),
                c.get("n_total"),
                resolve_display(c.get("condition"), context="food", fallback=str(c.get("condition") or ""))
                if c.get("condition")
                else "",
                resolve_display(
                    c.get("design"), context="design_short", fallback=str(c.get("design") or "")
                )
                if c.get("design")
                else "",
            ]
        )
    if selection:
        cv_rows.append(
            [
                "Выбранный CV",
                selection.get("selected_cv"),
                resolve_display(
                    selection.get("selection_method"),
                    context="selection_method",
                    fallback=str(selection.get("selection_method") or ""),
                ),
                "",
                "",
            ]
        )
    if cv_rows:
        add(
            "CV_EVIDENCE",
            "CV evidence",
            "9.2",
            ["Parameter", "CV%", "N", "Condition", "Design"],
            cv_rows,
            fill_mode="REBUILD",
        )

    if sources:
        src_rows = []
        for s in sources:
            authors = s.get("authors") or []
            if isinstance(authors, list):
                authors_s = ", ".join(str(a) for a in authors)
            else:
                authors_s = str(authors)
            type_disp = (
                resolve_display(s.get("type"), context="source_type", fallback=str(s.get("type") or ""))
                if s.get("type")
                else ""
            )
            src_rows.append(
                [
                    type_disp,
                    s.get("title") or "",
                    authors_s,
                    s.get("year") or "",
                    s.get("url") or "",
                ]
            )
        add(
            "SOURCES",
            "Sources",
            "18",
            ["Type", "Title", "Authors", "Year", "URL"],
            src_rows,
            [str(s.get("id")) for s in sources if s.get("id")],
            fill_mode="REBUILD",
            classification="DYNAMIC",
        )

    return tables

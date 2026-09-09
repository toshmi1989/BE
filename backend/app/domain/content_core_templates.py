"""Phase 12B.1 — core section codes + deterministic text templates.

No medical invention. Templates require resolved canonical fields.
"""

from __future__ import annotations

from typing import Any

# Sections in scope for Phase 12B.1 (from SECTION_TREE — do not invent numbers)
CORE_12B1_SECTION_CODES: frozenset[str] = frozenset(
    {
        "1.1",
        "1.2",
        "1.3",
        "1.4",
        "1.5",
        "1.6",
        "1.7",
        "1.8",
        "1.9",
        "2.1",
        "2.1.1",
        "2.1.2",
        "2.2",
        "2.3",
        "2.4",
        "2.5",
        "2.6",
        "2.9",
        "2.10",
        "2.11",
        "2.12",
        "3",
        "4.1",
        "4.2",
        "4.3",
        "4.4",
        "4.4.1",
        "4.4.2",
        "4.5",
        "4.6",
        "4.8",
        "4.8.1",
        "4.8.2",
        "4.8.3",
        "4.9",
        "SYNOPSIS",
    }
)

# Sections in scope for Phase 12B.2 (SECTION_TREE 5–8 — do not invent numbers)
CORE_12B2_SECTION_CODES: frozenset[str] = frozenset(
    {
        "5",
        "5.1",
        "5.2",
        "5.3",
        "6",
        "6.1",
        "6.1.1",
        "6.1.2",
        "6.1.3",
        "6.1.4",
        "6.1.5",
        "6.1.6",
        "6.1.7",
        "6.1.8",
        "6.1.9",
        "6.1.10",
        "6.2",
        "6.2.1",
        "6.2.2",
        "6.2.3",
        "6.3",
        "6.3.1",
        "7",
        "7.1",
        "7.2",
        "7.3",
        "7.3.1",
        "7.3.2",
        "7.3.3",
        "7.3.4",
        "8",
        "8.1",
        "8.2",
        "8.2.1",
        "8.2.2",
        "8.2.3",
        "8.3",
        "8.4",
        "8.5",
    }
)

CORE_12B2_GENERATOR_KEYS: frozenset[str] = frozenset(
    {
        "inclusion",
        "non_inclusion",
        "exclusion",
        "procedures_timeline",
        "treatment_detail",
        "washout_procedure",
        "food_restrictions",
        "period_1",
        "period_2",
        "sample_prep",
        "contraception",
        "eval_parameters",
        "eval_methods_timing",
        "bioanalysis",
        "analytical_method",
        "bio_validation",
        "sample_analysis",
        "run_acceptance",
        "safety_standard",
        "safety_methods",
        "physical_exam",
        "vital_signs",
        "safety_labs",
        "ae_framework",
        "ae_followup",
        "pregnancy",
    }
)

# Sections in scope for Phase 12B.3 (SECTION_TREE 9–15 — do not invent numbers)
CORE_12B3_SECTION_CODES: frozenset[str] = frozenset(
    {
        "9",
        "9.1",
        "9.2",
        "9.3",
        "9.4",
        "9.5",
        "9.6",
        "9.7",
        "9.7.1",
        "9.7.1.1",
        "9.7.1.2",
        "9.7.2",
        "9.7.3",
        "9.7.4",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
    }
)

CORE_12B3_GENERATOR_KEYS: frozenset[str] = frozenset(
    {
        "statistical_method",
        "sample_size",
        "alpha",
        "be_criteria",
        "stopping_rules",
        "missing_data_policy",
        "sap_deviations",
        "analysis_populations",
        "statistical_analysis",
        "descriptive_stats",
        "anova_methods",
        "outliers",
        "safety_analysis",
        "data_access",
        "standard_text",
        "financing_insurance",
        "publications",
    }
)

# Sections in scope for Phase 12B.4 (SECTION_TREE 16–18 — do not invent numbers)
CORE_12B4_SECTION_CODES: frozenset[str] = frozenset({"16", "17", "18"})

CORE_12B4_GENERATOR_KEYS: frozenset[str] = frozenset(
    {
        "appendices",
        "conclusion",
        "literature",
    }
)

# Generators we enhance in 12B.1 (overlay on existing)
CORE_12B1_GENERATOR_KEYS: frozenset[str] = frozenset(
    {
        "protocol_metadata",
        "sponsor",
        "test_product",
        "reference_product",
        "objectives",
        "design",
        "randomization",
        "treatment",
        "stages",
        "sampling_plan",
        "participation_duration",
        "washout_rationale",
        "study_conditions",
        "subjects_rationale",
        "reference_justification",
        "observation_rationale",
        "synopsis",
    }
)


def be_objective_template(
    *,
    design_display: str | None,
    test_name: str | None,
    reference_name: str | None,
) -> str | None:
    """Return objective text only when all required fields are present."""
    if not design_display or not test_name or not reference_name:
        return None
    return (
        f"Оценить биоэквивалентность лекарственного препарата {test_name} "
        f"в сравнении с препаратом {reference_name} в дизайне {design_display}."
    )


def study_title_template(
    *,
    design_display: str | None,
    test_name: str | None,
    reference_name: str | None,
) -> str | None:
    if not design_display or not test_name or not reference_name:
        return None
    return (
        f"{design_display} исследование биоэквивалентности лекарственного препарата "
        f"{test_name} в сравнении с {reference_name}"
    )


def sampling_summary_lines(
    *,
    points: list[dict[str, Any]],
    analytes: list[dict[str, Any]] | None,
    tmax: Any = None,
    last_point: Any = None,
    points_per_period: int | None = None,
) -> list[str]:
    """Structured sampling summary — no narrative invention."""
    lines: list[str] = []
    names = []
    for a in analytes or []:
        n = a.get("name") or a.get("code") or a.get("analyte_name")
        if n:
            names.append(str(n))
    if names:
        lines.append("Аналиты: " + ", ".join(names) + ".")
    times = sorted(
        float(p["time_h"])
        for p in points
        if p.get("time_h") is not None
    )
    n_pts = points_per_period if points_per_period is not None else (len(times) if times else None)
    if n_pts is not None:
        lines.append(f"Число точек отбора на период: {n_pts}.")
    if times:
        lines.append(
            "Запланированные точки отбора (ч): "
            + ", ".join(str(t) if t != int(t) else str(int(t)) for t in times)
            + "."
        )
    if tmax is not None:
        lines.append(f"Tmax (канонический вход): {tmax}.")
    if last_point is not None:
        lines.append(f"Последняя точка: {last_point}.")
    elif times:
        lines.append(f"Последняя точка: {times[-1]}.")
    return lines

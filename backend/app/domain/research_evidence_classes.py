"""Phase 15.2 — Research & Analogue Evidence Engine constants."""

from __future__ import annotations

RESEARCH_TASK_TYPES: tuple[str, ...] = (
    "FIND_SMPC_REFERENCE_PRODUCT",
    "FIND_CVINTRA_LITERATURE",
    "FIND_HALF_LIFE_PK",
    "FIND_TMAX_PK",
    "FIND_MEAL_COMPOSITION",
    "FIND_ANALOGUE_STUDY",
    "FIND_REGULATORY_EVIDENCE",
    "OTHER",
)

RESEARCH_TASK_STATUSES: tuple[str, ...] = (
    "OPEN",
    "SEARCHING",
    "RESULTS_AVAILABLE",
    "REVIEW_REQUIRED",
    "COMPLETED",
    "BLOCKED",
    "CANCELLED",
)

QUERY_TYPES: tuple[str, ...] = (
    "IDENTITY",
    "PK",
    "CV",
    "DESIGN",
    "FOOD",
    "ANALOGUE",
    "REGULATORY",
    "SAFETY",
    "OTHER",
)

PROVIDER_KINDS: tuple[str, ...] = (
    "WEB",
    "LOCAL_DOCUMENTS",
    "INTERNAL_LIBRARY",
    "REGULATORY_SOURCE",
    "PUBLICATION",
    "MOCK",
)

SOURCE_RESULT_TYPES: tuple[str, ...] = (
    "SMPC",
    "REGULATORY",
    "PUBLICATION",
    "CLINICAL_STUDY",
    "PROTOCOL",
    "REVIEW",
    "DATABASE",
    "OTHER",
)

EXTRACTION_METHODS: tuple[str, ...] = ("DETERMINISTIC", "AI", "MANUAL")

VERIFICATION_STATUSES: tuple[str, ...] = ("PROPOSED", "VERIFIED", "REJECTED")

USABILITY_STATES: tuple[str, ...] = (
    "USABLE_FOR_DECISION",
    "NOT_USABLE_FOR_DECISION",
    "REQUIRES_REVIEW",
)

PRIORITIES: tuple[str, ...] = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

STATISTIC_TYPES: tuple[str, ...] = (
    "MEAN",
    "MEDIAN",
    "RANGE",
    "GEOMETRIC_MEAN",
    "POINT",
    "UNKNOWN",
)

VARIABILITY_TYPES: tuple[str, ...] = (
    "WITHIN_SUBJECT",
    "BETWEEN_SUBJECT",
    "UNKNOWN",
)

PK_PARAMETERS: tuple[str, ...] = (
    "Cmax",
    "AUC",
    "AUC0-t",
    "AUC0-inf",
    "Tmax",
    "t_half",
    "OTHER",
)

MATCH_DIMS: tuple[str, ...] = (
    "ACTIVE_SUBSTANCE",
    "DOSAGE_FORM",
    "DOSE",
    "POPULATION",
    "DESIGN",
    "CONDITION",
    "ROUTE",
    "ANALYTE",
    "REGULATORY_CONTEXT",
)

MATCH_VALUES: tuple[str, ...] = ("MATCH", "PARTIAL", "MISMATCH", "UNKNOWN")

# Gap code → task type + priority (from decision dependency blockers)
GAP_TO_TASK: dict[str, dict[str, str]] = {
    "MISSING_TMAX_FOR_SAMPLING": {
        "task_type": "FIND_TMAX_PK",
        "priority": "CRITICAL",
        "query_type": "PK",
        # Claim path remains pk.Tmax (legacy); semantically this is expected/planning Tmax
        "field_path": "pk.Tmax",
        "planning_role": "expected_tmax",
    },
    "MISSING_HALF_LIFE_FOR_WASHOUT": {
        "task_type": "FIND_HALF_LIFE_PK",
        "priority": "CRITICAL",
        "query_type": "PK",
        "field_path": "pk.t_half",
        "planning_role": "expected_t_half",
    },
    "MISSING_CVINTRA": {
        "task_type": "FIND_CVINTRA_LITERATURE",
        "priority": "HIGH",
        "query_type": "CV",
        "field_path": "cv_intra",
    },
    "MISSING_MEAL_COMPOSITION": {
        "task_type": "FIND_MEAL_COMPOSITION",
        "priority": "MEDIUM",
        "query_type": "FOOD",
        "field_path": "food.calorie_target",
    },
    "MISSING_SMPC_REFERENCE_PRODUCT": {
        "task_type": "FIND_SMPC_REFERENCE_PRODUCT",
        "priority": "HIGH",
        "query_type": "IDENTITY",
        "field_path": "reference_product.name",
    },
    "MISSING_ANALYTE": {
        "task_type": "OTHER",
        "priority": "HIGH",
        "query_type": "PK",
        "field_path": "bioanalysis.analyte",
    },
}

TASK_TYPE_LABELS_RU: dict[str, str] = {
    "FIND_SMPC_REFERENCE_PRODUCT": "Официальная информация о препарате (SmPC)",
    "FIND_CVINTRA_LITERATURE": "CVintra (внутрииндивидуальная вариабельность)",
    "FIND_HALF_LIFE_PK": "Период полувыведения (t½)",
    "FIND_TMAX_PK": "Tmax",
    "FIND_MEAL_COMPOSITION": "Состав завтрака / пищи",
    "FIND_ANALOGUE_STUDY": "Аналоговые исследования",
    "FIND_REGULATORY_EVIDENCE": "Регуляторные источники",
    "OTHER": "Прочее",
}

"""Study Input Package vocabulary — Phase 14.

No medical decision algorithms. Controlled field paths + document types.
"""

from __future__ import annotations

DOCUMENT_TYPES: tuple[str, ...] = (
    "CHECKLIST",
    "SYNOPSIS",
    "DESIGN",
    "SMPC",
    "PREVIOUS_PROTOCOL",
    "REGULATORY",
    "PUBLICATION",
    "OTHER",
    "UNKNOWN",
    "GOLDEN_PROTOCOL",
)

PACKAGE_STATUSES: tuple[str, ...] = (
    "DRAFT",
    "EXTRACTING",
    "READY_FOR_REVIEW",
    "REVIEW_REQUIRED",
    "READY_FOR_ASSEMBLY",
    "BLOCKED",
)

CANDIDATE_STATUSES: tuple[str, ...] = (
    "PROPOSED",
    "REVIEW_REQUIRED",
    "VERIFIED",
    "REJECTED",
)

EXTRACTION_METHODS: tuple[str, ...] = (
    "DETERMINISTIC",
    "AI",
    "MANUAL",
)

CONFLICT_RESOLUTION_STATUSES: tuple[str, ...] = (
    "OPEN",
    "UNDER_REVIEW",
    "RESOLVED",
    "DISMISSED",
)

CONFLICT_OUTCOMES: tuple[str, ...] = (
    "SELECT_VALUE",
    "KEEP_BOTH_WITH_CONTEXT",
    "REQUIRES_EXTERNAL_EVIDENCE",
    "DATA_ENTRY_ERROR",
)

COVERAGE_STATES: tuple[str, ...] = (
    "MISSING",
    "PRESENT",
    "PARTIAL",
    "CONFLICT",
    "REVIEW_REQUIRED",
    "VERIFIED",
    "NOT_APPLICABLE",
)

# Controlled field paths (extract only when present in sources)
FIELD_PATHS: tuple[str, ...] = (
    "study.title",
    "study.protocol_number",
    "study.version",
    "study.version_date",
    "sponsor.name",
    "sponsor.address",
    "sponsor.phone",
    "cro.name",
    "cro.address",
    "cro.phone",
    "cro.responsible_person",
    "investigator.name",
    "investigator.position",
    "investigator.phone",
    "test_product.name",
    "test_product.dose",
    "test_product.dosage_form",
    "test_product.manufacturer",
    "test_product.active_substance",
    "test_product.composition",
    "reference_product.name",
    "reference_product.dose",
    "reference_product.dosage_form",
    "reference_product.marketing_authorization_holder",
    "reference_product.manufacturer",
    "reference_product.active_substance",
    "design.randomized",
    "design.open_label",
    "design.crossover",
    "design.periods",
    "design.sequences",
    "design.groups",
    "design.conditions",
    "design.population",
    "design.adaptive",
    "subjects.type",
    "subjects.sex",
    "subjects.age_min",
    "subjects.age_max",
    "subjects.screened_n",
    "subjects.randomized_n",
    "subjects.group_allocation",
    "treatment.sequence",
    "treatment.fasting",
    "treatment.fed",
    "treatment.dose",
    "washout.duration",
    "washout.unit",
    "washout.rationale",
    "sampling.times",
    "sampling.total_points",
    "sampling.pre_dose_point",
    "sampling.endpoint",
    "food.condition",
    "food.breakfast_type",
    "food.breakfast_timing",
    "bioanalysis.analyte",
    "bioanalysis.matrix",
    "bioanalysis.method",
    "bioanalysis.laboratory",
    "pk.parameters",
    "pk.primary_parameters",
    "pk.Cmax",
    "pk.Tmax",
    "pk.t_half",
    "pk.AUC_endpoint",
    "statistics.method",
    "statistics.transformation",
    "statistics.confidence_interval",
    "statistics.acceptance_interval",
    "safety.monitoring",
    "safety.adverse_events",
    "safety.ECG",
    "safety.lab_tests",
)

FIELD_PATH_SET = frozenset(FIELD_PATHS)

COVERAGE_DOMAINS: dict[str, tuple[str, ...]] = {
    "ADMINISTRATIVE": (
        "study.protocol_number",
        "sponsor.name",
        "cro.name",
    ),
    "TEST_PRODUCT": (
        "test_product.name",
        "test_product.dose",
        "test_product.dosage_form",
    ),
    "REFERENCE_PRODUCT": (
        "reference_product.name",
        "reference_product.dose",
        "reference_product.dosage_form",
    ),
    "DESIGN": (
        "design.randomized",
        "design.crossover",
        "design.periods",
        "design.sequences",
        "design.groups",
        "design.conditions",
    ),
    "SUBJECTS": (
        "subjects.sex",
        "subjects.age_min",
        "subjects.age_max",
        "subjects.screened_n",
        "subjects.randomized_n",
        "subjects.group_allocation",
    ),
    "TREATMENT": ("treatment.fasting", "treatment.fed"),
    "SAMPLING": ("sampling.times", "sampling.total_points"),
    "WASHOUT": ("washout.duration", "washout.unit"),
    "FOOD": ("food.condition",),
    "PK": ("pk.parameters", "pk.Cmax", "pk.AUC_endpoint"),
    "BIOANALYSIS": ("bioanalysis.analyte", "bioanalysis.method"),
    "SAFETY": ("safety.monitoring", "safety.adverse_events"),
    "STATISTICS": (
        "statistics.method",
        "statistics.transformation",
        "statistics.confidence_interval",
        "statistics.acceptance_interval",
    ),
}

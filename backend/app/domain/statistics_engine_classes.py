"""Phase 15.5 — Deterministic Statistics Engine constants."""

from __future__ import annotations

STATISTICS_ENGINE_VERSION = "STATISTICS_ENGINE.v1"
METHODOLOGY_VERSION = "0.20.0"

PLAN_STATUSES: tuple[str, ...] = (
    "DRAFT",
    "REVIEW_REQUIRED",
    "APPROVED",
    "REJECTED",
    "SUPERSEDED",
    "BLOCKED",
)

PARAMETER_ROLES: tuple[str, ...] = (
    "PRIMARY_BE",
    "SECONDARY_PK",
    "DESCRIPTIVE",
    "SAFETY",
    "NOT_ANALYZED_FOR_BE",
)

TRANSFORMATIONS: tuple[str, ...] = ("NONE", "LOG")

# Only methods with an explicit implementation path
SUPPORTED_MODELS: tuple[str, ...] = ("ANOVA_LOG_2X2",)

# Canonical 2×2 ANOVA model terms already used in the codebase / protocol narrative
ANOVA_2X2_MODEL_TERMS: tuple[str, ...] = (
    "treatment",
    "sequence",
    "period",
    "subject_within_sequence",
)

UNSUPPORTED_DESIGN_MODELS: dict[str, str] = {
    "REPLICATE_CROSSOVER": "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW",
    "REPLICATE_2X2X4": "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW",
    "ADAPTIVE_DESIGN": "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW",
    "ADAPTIVE": "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW",
    "PARALLEL_DESIGN": "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW",
    "PARALLEL": "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW",
}

SUPPORTED_DESIGNS_FOR_ANOVA_2X2: frozenset[str] = frozenset(
    {"STANDARD_2X2_CROSSOVER", "CROSSOVER_2X2", "2X2_CROSSOVER"}
)

# Controlled PK parameter vocabulary
SUPPORTED_PARAMETERS: tuple[str, ...] = (
    "Cmax",
    "AUC0-t",
    "AUC0-inf",
    "AUC0-72",
    "AUC0-x",
    "Tmax",
    "t1/2",
    "kel",
    "AUCextr",
)

# Parameters that may receive LOG + ANOVA when role is PRIMARY_BE / SECONDARY_PK
LOG_ANOVA_ELIGIBLE: frozenset[str] = frozenset(
    {"Cmax", "AUC0-t", "AUC0-inf", "AUC0-72", "AUC0-x", "AUCextr"}
)

# Never auto-apply LOG-ANOVA
DESCRIPTIVE_ONLY_DEFAULT: frozenset[str] = frozenset({"Tmax", "t1/2", "kel"})

ESTIMATE_KINDS: tuple[str, ...] = (
    "GEOMETRIC_MEAN_RATIO_TEST_REFERENCE",
    "NONE",
)

DESCRIPTIVE_STATS: tuple[str, ...] = (
    "N",
    "Mean",
    "SD",
    "CV%",
    "Min",
    "Median",
    "Max",
    "Geometric Mean",
)

TMAX_SUMMARY_DEFAULT: tuple[str, ...] = ("Median", "Range", "Min", "Max")

ANALYSIS_POPULATIONS: tuple[str, ...] = (
    "ALL_RANDOMIZED",
    "PK_ANALYSIS_SET",
    "SAFETY_SET",
    "PER_PROTOCOL",
)

SOURCE_ROLES: tuple[str, ...] = (
    "CURRENT_STUDY_FACT",
    "STATISTICAL_RECOMMENDATION",
    "STATISTICAL_PLAN",
    "EXPERT_DECISION",
    "REGULATORY_REQUIREMENT",
    "VERIFIED_RULE",
    "VERIFIED_EVIDENCE",
    "EXPLICIT_CONFIGURATION",
    "PROPOSED_EVIDENCE",  # never authoritative
)

REVIEW_ACTIONS: tuple[str, ...] = (
    "APPROVE",
    "REJECT",
    "MODIFY",
    "REQUEST_MORE_INFORMATION",
)

BLOCKER_CODES: tuple[str, ...] = (
    "MISSING_PRIMARY_PK_PARAMETER",
    "MISSING_ACCEPTANCE_INTERVAL",
    "MISSING_CONFIDENCE_LEVEL",
    "MISSING_STATISTICAL_MODEL",
    "MISSING_ANALYSIS_POPULATION_RULE",
    "MISSING_TRANSFORMATION",
    "MISSING_PROVENANCE",
    "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW",
    "REQUIRES_EXPERT_SELECTION",
    "REQUIRES_EXPERT_DECISION",
    "PROPOSED_EVIDENCE_NOT_AUTHORITATIVE",
    "CONFLICTING_ENDPOINT_DEFINITIONS",
    "CONFLICTING_ACCEPTANCE_INTERVALS",
    "UNSUPPORTED_PARAMETER",
    "TMAX_INFERENTIAL_NOT_IMPLEMENTED",
    "NO_OBSERVED_DATA_NO_FABRICATED_GMR",
    "NO_OBSERVED_DATA_NO_FABRICATED_CI",
    "AI_CANNOT_SELECT_METHOD",
    "AI_CANNOT_APPROVE",
)

# Display labels for UI (never show raw enums in Russian UI)
ROLE_LABELS_RU: dict[str, str] = {
    "PRIMARY_BE": "Primary BE",
    "SECONDARY_PK": "Secondary PK",
    "DESCRIPTIVE": "Descriptive",
    "SAFETY": "Safety",
    "NOT_ANALYZED_FOR_BE": "Not analyzed for BE",
}

TRANSFORM_LABELS: dict[str, str] = {
    "NONE": "None",
    "LOG": "Logarithmic",
}

MODEL_LABELS: dict[str, str] = {
    "ANOVA_LOG_2X2": "ANOVA for 2×2 crossover",
}

CANONICAL_ANALYSIS_METHOD_ALIAS = "ANOVA_TOST_90CI"  # existing stats_rules vocabulary

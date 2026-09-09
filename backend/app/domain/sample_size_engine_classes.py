"""Phase 15.4 — Sample Size Engine constants (no medical defaults)."""

from __future__ import annotations

SAMPLE_SIZE_ENGINE_VERSION = "SAMPLE_SIZE_ENGINE.v1"
CALCULATION_VERSION = "0.19.0"

# Fully supported design for authoritative calculation
SUPPORTED_DESIGNS: tuple[str, ...] = ("STANDARD_2X2_CROSSOVER",)

# Map Phase 15.4 design labels → existing calculator design_type
DESIGN_TO_CALCULATOR: dict[str, str] = {
    "STANDARD_2X2_CROSSOVER": "CROSSOVER_2X2",
    "CROSSOVER_2X2": "CROSSOVER_2X2",  # alias for existing code
}

UNSUPPORTED_DESIGNS: tuple[str, ...] = (
    "REPLICATE_CROSSOVER",
    "REPLICATE_2X2X4",
    "ADAPTIVE_DESIGN",
    "ADAPTIVE",
    "PARALLEL_DESIGN",
    "PARALLEL",
)

# PK parameters eligible for sample-size scenarios
SAMPLE_SIZE_PK_PARAMETERS: tuple[str, ...] = (
    "Cmax",
    "AUC",
    "AUC0-t",
    "AUC0-inf",
)

INFLATION_METHODS: tuple[str, ...] = (
    "DIVIDE_BY_RETAINMENT_RATE",
    "NONE",
)

ROUNDING_RULES: tuple[str, ...] = (
    "CEIL_EVEN_2X2",  # never round down; even N for balanced 2×2
    "CEIL_INTEGER",
)

CALCULATION_STATUSES: tuple[str, ...] = (
    "CALCULATED",
    "BLOCKED",
    "PENDING_REVIEW",
    "ACCEPTED",
    "REJECTED",
    "SUPERSEDED",
)

RECOMMENDATION_OPTIONS: tuple[str, ...] = (
    "USE_CURRENT_N",
    "INCREASE_N",
    "DECREASE_N",
    "REQUIRES_EXPERT_DECISION",
)

REVIEW_DECISIONS: tuple[str, ...] = (
    "ACCEPT_CALCULATION",
    "REJECT_CALCULATION",
    "ACCEPT_CURRENT_N",
    "REQUEST_RECALCULATION",
)

INPUT_SOURCE_KINDS: tuple[str, ...] = (
    "EVIDENCE_MEASUREMENT",
    "VERIFIED_STUDY_FACT",
    "EXPERT_INPUT",
    "EXPLICIT_CONFIGURATION",
    "PROJECT_DEFAULT",
    "SYNOPSIS",
)

# Blocking / gate reason codes
BLOCKER_CODES: tuple[str, ...] = (
    "MISSING_VERIFIED_CVINTRA",
    "MISSING_CVINTRA_CMAX",
    "MISSING_CVINTRA_AUC",
    "MISSING_EXPECTED_RATIO",
    "MISSING_POWER",
    "MISSING_ALPHA",
    "MISSING_DROPOUT_ASSUMPTION",
    "MISSING_BE_LIMITS",
    "MISSING_DESIGN",
    "MISSING_PARAMETER",
    "MISSING_PROVENANCE",
    "INVALID_NUMERIC_RANGE",
    "METHOD_NOT_IMPLEMENTED_REQUIRES_REVIEW",
    "MULTIPLE_ELIGIBLE_INPUTS_REQUIRES_EXPERT_SELECTION",
    "MULTIPLE_CONFLICTING_CVINTRA",
    "CV_NOT_ELIGIBLE",
    "CV_PROPOSED_NOT_ALLOWED",
    "CV_REJECTED_NOT_ALLOWED",
    "CV_BETWEEN_SUBJECT_NOT_ALLOWED",
    "CV_UNKNOWN_TYPE_NOT_ALLOWED",
    "CV_MISSING_PK_PARAMETER",
    "CV_LOW_APPLICABILITY",
    "CV_NOT_USABLE",
    "REQUIRES_EXPERT_SELECTION",
    "SAMPLE_SIZE_DISCREPANCY",
)

ELIGIBLE_APPLICABILITY: frozenset[str] = frozenset({"DIRECT", "HIGH", "MODERATE"})
INELIGIBLE_APPLICABILITY: frozenset[str] = frozenset({"LOW", "NOT_APPLICABLE"})

CANONICAL_CALCULATOR = "app.domain.sample_size.Crossover2x2SampleSizeCalculator"
CANONICAL_METHOD_ID = "CROSSOVER_2X2_TOST_NCT"
CANONICAL_ALGORITHM = "BE_TOST_2X2_NCT.v1"

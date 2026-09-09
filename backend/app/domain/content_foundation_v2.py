"""Phase 12A.2 — content foundation constants (extends Phase 12A).

Additive catalogs only. No medical thresholds or invented defaults.
"""

from __future__ import annotations

from app.domain.content_foundation_constants import (  # re-export
    CONTENT_BLOCK_STATUSES,
    CONTENT_SECTION_TYPES,
    CONTENT_SOURCE_CLASSES,
    PROCEDURE_CATEGORIES as _PROCEDURE_CATEGORIES_V1,
    PROCEDURE_STAGES,
)

# Extended procedure categories (Phase 12A.2) — keeps Phase 12A codes
PROCEDURE_CATEGORIES = tuple(
    dict.fromkeys(
        (
            *_PROCEDURE_CATEGORIES_V1,
            "ADMISSION",
            "RANDOMIZATION",
            "FASTING",
            "BLOOD_SAMPLING",
            "VITAL_SIGNS",
            "LABORATORY",
            "DRUG_ACCOUNTABILITY",
            "SAMPLE_PROCESSING",
            "SAMPLE_STORAGE",
            "BIOANALYSIS",
            "SAFETY_ASSESSMENT",
            "DISCHARGE",
        )
    )
)

TIME_ANCHORS = (
    "SCREENING",
    "ADMISSION",
    "DOSE",
    "PRE_DOSE",
    "POST_DOSE",
    "SAMPLING",
    "DISCHARGE",
    "FOLLOW_UP",
    "OTHER",
)

DEPENDENCY_TYPES = (
    "REQUIRES",
    "PRECEDES",
    "CONDITIONAL",
    "MUTUALLY_EXCLUSIVE",
)

CONTENT_BLOCK_TYPES = (
    "STATIC_VERIFIED",
    "CANONICAL_VALUE",
    "PROCEDURE",
    "CONDITION",
    "EVIDENCE_DERIVED",
    "EXPERT_DECISION",
    "GENERATED_TEXT",
    "TABLE",
    "REFERENCE",
    "CONDITIONAL",
    "PLACEHOLDER",
)

CONTENT_STATIC_DYNAMIC = (
    "STATIC_VERIFIED",
    "DYNAMIC_CANONICAL",
    "CONDITIONAL",
    "EVIDENCE_DERIVED",
    "EXPERT_DECISION",
)

# ContentResolver source priority (highest first)
CONTENT_SOURCE_PRIORITY = (
    "CANONICAL",
    "APPROVED_EXPERT_DECISION",
    "VERIFIED_EVIDENCE_OR_RULE",
    "PROPOSED_EVIDENCE_OR_RULE",
    "MISSING",
)

CONTENT_VALIDATION_CODES = (
    "CONTENT.MISSING_SOURCE",
    "CONTENT.PROPOSED_AS_FINAL",
    "CONTENT.KNOWLEDGE_GAP_OPEN",
    "CONTENT.CANONICAL_MISMATCH",
    "CONTENT.EXPERT_DECISION_INVALID",
    "CONTENT.STALE_DECISION",
    "CONTENT.STALE_EVIDENCE",
    "CONTENT.LEGACY_TEMPLATE_VALUE",
)

PHASE12A2_CONTENT_FOUNDATION_VERSION = "CONTENT.FOUNDATION.v2"

# Procedure → section mapping registry (not hardcoded inside DOCX generator)
PROCEDURE_SECTION_MAP: dict[str, tuple[str, ...]] = {
    "DOSING": ("4.6", "6.1"),
    "SAMPLING": ("4.4.2", "6.1.1", "6.1.4"),
    "BLOOD_SAMPLING": ("4.4.2", "6.1.1"),
    "MEAL": ("6.2.1", "4.4"),
    "FASTING": ("6.2.1",),
    "WASHOUT": ("6.1.5",),
    "SAFETY": ("8.1", "8.2"),
    "SAFETY_ASSESSMENT": ("8.1", "8.2"),
    "VITALS": ("8.2.2",),
    "VITAL_SIGNS": ("8.2.2",),
    "ECG": ("8.2",),
    "LAB": ("8.2.3",),
    "LABORATORY": ("8.2.3",),
    "PHYSICAL_EXAM": ("8.2.1",),
    "BIOANALYSIS": ("7.3.1", "6.1.9"),
    "SAMPLE_PROCESSING": ("6.1.9",),
    "SCREENING": ("6.1.2",),
    "FOLLOW_UP": ("6.3.1", "8.4"),
    "FINAL": ("6.1.7",),
}

__all__ = [
    "PROCEDURE_CATEGORIES",
    "PROCEDURE_STAGES",
    "TIME_ANCHORS",
    "DEPENDENCY_TYPES",
    "CONTENT_BLOCK_TYPES",
    "CONTENT_STATIC_DYNAMIC",
    "CONTENT_SOURCE_PRIORITY",
    "CONTENT_VALIDATION_CODES",
    "CONTENT_SOURCE_CLASSES",
    "CONTENT_BLOCK_STATUSES",
    "CONTENT_SECTION_TYPES",
    "PROCEDURE_SECTION_MAP",
    "PHASE12A2_CONTENT_FOUNDATION_VERSION",
]

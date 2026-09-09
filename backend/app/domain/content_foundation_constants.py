"""Phase 12A — procedure / bioanalysis / safety / content provenance constants.

No clinical thresholds or medical defaults live here.
"""

from __future__ import annotations

# Procedure categories
PROCEDURE_CATEGORIES = (
    "SCREENING",
    "HOSPITALIZATION",
    "ADMISSION",
    "RANDOMIZATION",
    "DOSING",
    "SAMPLING",
    "BLOOD_SAMPLING",
    "MEAL",
    "FASTING",
    "VITALS",
    "VITAL_SIGNS",
    "ECG",
    "LAB",
    "LABORATORY",
    "PHYSICAL_EXAM",
    "SAFETY",
    "SAFETY_ASSESSMENT",
    "WASHOUT",
    "FOLLOW_UP",
    "DRUG_ACCOUNTABILITY",
    "SAMPLE_PROCESSING",
    "SAMPLE_STORAGE",
    "BIOANALYSIS",
    "DISCHARGE",
    "FINAL",
    "OTHER",
)

PROCEDURE_STAGES = (
    "SCREENING",
    "PERIOD_1",
    "WASHOUT",
    "PERIOD_2",
    "FOLLOW_UP",
    "FINAL",
)

# Field / content source classification (bioanalysis & content blocks)
CONTENT_SOURCE_CLASSES = (
    "SOURCE_DERIVED",
    "USER",
    "STATIC_VERIFIED",
    "EXPERT_REQUIRED",
    "UNRESOLVED",
    "CALCULATED",
    "RULE_DERIVED",
    "TEMPLATE",
)

CONTENT_BLOCK_STATUSES = (
    "VERIFIED",
    "PROPOSED",
    "NEEDS_REVIEW",
    "UNRESOLVED",
    "DRAFT",
)

EXPERT_RULE_VERIFICATION = (
    "UNVERIFIED",
    "PROPOSED",
    "VERIFIED",
    "REJECTED",
)

# Content matrix section types
CONTENT_SECTION_TYPES = (
    "DYNAMIC",
    "CONDITIONAL",
    "STATIC_VERIFIED",
    "EXPERT_REQUIRED",
    "UNRESOLVED",
    "NEEDS_REVIEW",
)

PHASE12A_CONTENT_FOUNDATION_VERSION = "CONTENT.FOUNDATION.v1"

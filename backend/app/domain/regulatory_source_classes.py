"""Regulatory source classes & verification states — Phase 13.1.

Classification only. No automatic ranking resolution. No medical decisions.
"""

from __future__ import annotations

SOURCE_CLASSES: tuple[str, ...] = (
    "EEC_REGULATORY",
    "FDA_GUIDANCE",
    "EMA_GUIDANCE",
    "REGULATORY_REPORT",
    "SMPC_OHLP",
    "SCIENTIFIC_ARTICLE",
    "EXPERT_INTERVIEW",
    "OTHER",
)

# Source / claim / basis verification — NEVER auto-promote to VERIFIED on ingest
SOURCE_VERIFICATION_STATUSES: tuple[str, ...] = (
    "UNVERIFIED",
    "EXTRACTED",
    "REVIEW_REQUIRED",
    "VERIFIED",
    "REJECTED",
    "SUPERSEDED",
)

CLAIM_KINDS: tuple[str, ...] = (
    "RAW_EXTRACT",
    "NORMALIZED_CLAIM",
    "REGULATORY_CLAIM",
    "STUDY_FACT",
    "MEDICAL_RULE_CANDIDATE",
    "EXPERT_INTERVIEW_CLAIM",
)

CONFIDENCE_LEVELS: tuple[str, ...] = ("LOW", "MEDIUM", "HIGH")

CONFLICT_TYPES: tuple[str, ...] = (
    "VALUE_CONFLICT",
    "DEFINITION_CONFLICT",
    "POPULATION_CONFLICT",
    "JURISDICTION_CONFLICT",
    "VERSION_CONFLICT",
    "TIME_CONFLICT",
    "METHODOLOGY_CONFLICT",
)

REVIEW_ITEM_STATUSES: tuple[str, ...] = (
    "PENDING",
    "IN_REVIEW",
    "APPROVED",
    "REJECTED",
)

EVIDENCE_DOMAINS: tuple[str, ...] = (
    "REFERENCE",
    "DESIGN",
    "FOOD",
    "SAMPLING",
    "WASHOUT",
    "ANALYTE",
    "PK",
    "STATISTICS",
    "ELIGIBILITY",
    "SAFETY",
    "ETHICS",
    "REPORTING",
)


def is_regulatory_document_class(source_class: str) -> bool:
    return source_class in {
        "EEC_REGULATORY",
        "FDA_GUIDANCE",
        "EMA_GUIDANCE",
        "REGULATORY_REPORT",
        "SMPC_OHLP",
    }


def is_interview_class(source_class: str) -> bool:
    return source_class == "EXPERT_INTERVIEW"


def assert_not_auto_verified(status: str, *, context: str = "") -> None:
    """Guard: callers must not treat EXTRACTED as VERIFIED."""
    if status == "VERIFIED":
        raise ValueError(
            f"VERIFIED status requires explicit expert review workflow{': ' + context if context else ''}"
        )

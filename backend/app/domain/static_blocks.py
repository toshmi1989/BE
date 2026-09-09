"""STATIC_VERIFIED vs LEGACY_UNCONTROLLED / DYNAMIC template blocks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

STATIC_VERIFIED = "STATIC_VERIFIED"
LEGACY_UNCONTROLLED = "LEGACY_UNCONTROLLED"
DYNAMIC = "DYNAMIC"


@dataclass(frozen=True)
class StaticBlock:
    block_id: str
    section_code: str
    template_version: str
    source: str
    verified_status: str  # STATIC_VERIFIED | LEGACY_UNCONTROLLED | DYNAMIC
    notes: str = ""


# Intentionally static SOP / form blocks from BE_Protocol_Template_v2.0
STATIC_BLOCKS: tuple[StaticBlock, ...] = (
    StaticBlock("ABBR.T02", "ABBR", "v2.0", "template glossary T02", STATIC_VERIFIED),
    StaticBlock("SAFE.T13", "8.2.2", "v2.0", "vital sign deviation scale T13", STATIC_VERIFIED),
    StaticBlock("SAFE.T14", "8.3.3", "v2.0", "AE severity scale T14", STATIC_VERIFIED),
    StaticBlock("SAFE.T15", "8.3.4", "v2.0", "causality scale T15", STATIC_VERIFIED),
    StaticBlock("SAFE.T16", "8.3.5", "v2.0", "seriousness criteria T16", STATIC_VERIFIED),
    StaticBlock("LAB.T09", "4.2", "v2.0", "clinical lab panels T09", STATIC_VERIFIED, notes="Not overwritten — not PK analyte table"),
    StaticBlock(
        "SCHED.T08",
        "4.2",
        "v2.0",
        "schedule of assessments T08",
        STATIC_VERIFIED,
        notes="Preserved for 2-period crossover; CONDITIONAL mismatch otherwise",
    ),
    StaticBlock(
        "MEAL.T12_FED",
        "6.2.1",
        "v2.0",
        "high-calorie fed meal timing T12",
        STATIC_VERIFIED,
        notes="Preserved when FED+HIGH_CALORIE; FASTING rebuilds dynamically",
    ),
    StaticBlock("APP.T18_T33", "16", "v2.0", "appendix AE/SAE/pregnancy forms T18–T33", STATIC_VERIFIED),
    StaticBlock(
        "SAFE.8.3_SCALES",
        "8.3.3",
        "v2.0",
        "AE scale tables under 8.3.x",
        STATIC_VERIFIED,
        notes="Narrative 8.3 replaced; scale tables T14–T16 preserved",
    ),
    StaticBlock("ADMIN.10.2", "10.2", "v2.0", "protocol compliance boilerplate", STATIC_VERIFIED),
    StaticBlock("ADMIN.10.3", "10.3", "v2.0", "protocol deviations boilerplate", STATIC_VERIFIED),
    StaticBlock("ADMIN.10.4", "10.4", "v2.0", "data retention boilerplate", STATIC_VERIFIED),
    # Phase 11B: former LEGACY blocks now actively replaced
    StaticBlock(
        "DYN.P0_SECTIONS",
        "1-9,18",
        "v2.0",
        "P0 section bodies replaced from ProtocolDraft",
        DYNAMIC,
        notes="See ACTIVE_SECTION_CODES / PHASE11B_LEGACY_BLOCK_AUDIT.md",
    ),
    StaticBlock(
        "DYN.P1_ADMIN",
        "1.2-1.9,14,15",
        "v2.0",
        "P1 administrative sections replaced from canonical sponsor/org/person data",
        DYNAMIC,
        notes="Phase 11C — sponsor, investigators, signatures, insurance, financing, publication",
    ),
    StaticBlock(
        "DYN.SYNOPSIS_SUBJECT_N",
        "SYNOPSIS",
        "v2.0",
        "T03 subject-count cells rewritten from SubjectPlan; admin labels from Sponsor/Person/Org",
        DYNAMIC,
        notes="Phase 11C-H — LEGACY.SYNOPSIS_N46 controlled; TOC page-number 46 classified separately",
    ),
    StaticBlock(
        "FOUNDATION.P12A",
        "6-8,7.3",
        "v2.0",
        "ProcedureSchedule / BioanalysisPlan / SafetyPlan / ExpertRule framework",
        DYNAMIC,
        notes="Phase 12A technical foundation — no mass P2 DOCX rewrite; expert rules empty catalog",
    ),
    # Residual non-subject 46 (TOC page numbers) — not SubjectPlan risk
    StaticBlock(
        "TOC.PAGE_NUMBERS",
        "TOC",
        "v2.0",
        "Word TOC page numbers may show digit 46",
        STATIC_VERIFIED,
        notes="Not a subject-count; excluded from legacy subject-N gate",
    ),
)


def list_static_blocks(*, status: str | None = None) -> list[dict[str, Any]]:
    rows = []
    for b in STATIC_BLOCKS:
        if status and b.verified_status != status:
            continue
        rows.append(
            {
                "block_id": b.block_id,
                "section_code": b.section_code,
                "template_version": b.template_version,
                "source": b.source,
                "verified_status": b.verified_status,
                "notes": b.notes,
            }
        )
    return rows


def legacy_uncontrolled_blocks() -> list[StaticBlock]:
    return [b for b in STATIC_BLOCKS if b.verified_status == LEGACY_UNCONTROLLED]

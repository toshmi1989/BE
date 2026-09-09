"""Configurable source-type ranking for future Research Engine (domain only)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRankRule:
    source_type: str
    priority_score: int
    notes: str


# Higher score = preferred. Not a regulatory verification — configuration only.
SOURCE_RANKING: tuple[SourceRankRule, ...] = (
    SourceRankRule("SmPC", 100, "Official product label / SmPC"),
    SourceRankRule("REGULATORY_GUIDELINE", 95, "EAEU / EMA / FDA BE guideline"),
    SourceRankRule("PRODUCT_SPECIFIC_GUIDELINE", 90, "Molecule-specific BE guide"),
    SourceRankRule("REGISTRATION_DOSSIER", 85, "Registration / CTD extracts"),
    SourceRankRule("PEER_REVIEWED_BE_STUDY", 80, "Published BE / PK study"),
    SourceRankRule("PEER_REVIEWED_PK", 75, "Published PK / ADME"),
    SourceRankRule("INTERNAL_REPORT", 60, "Sponsor / CRO internal report"),
    SourceRankRule("EXPERT_NOTE", 40, "Expert judgment note"),
    SourceRankRule("OTHER", 10, "Unclassified"),
)

SOURCE_RANKING_VERSION = "SRC.RANK.v1"


def priority_for(source_type: str) -> int:
    for rule in SOURCE_RANKING:
        if rule.source_type == source_type:
            return rule.priority_score
    return priority_for("OTHER")


def ranking_as_dict() -> dict:
    return {
        "version": SOURCE_RANKING_VERSION,
        "rules": [
            {
                "source_type": r.source_type,
                "priority_score": r.priority_score,
                "notes": r.notes,
            }
            for r in SOURCE_RANKING
        ],
    }

"""CriteriaRuleSet / Safety / Source priority — Phase 12A.1 foundation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CriteriaEvaluationResult:
    applied_rules: list[str] = field(default_factory=list)
    standard_note: str = ""
    drug_specific_overlays: list[dict[str, Any]] = field(default_factory=list)
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_criteria(
    *,
    smpc_evidence_claim_ids: list[str] | None = None,
    has_cyp_mentions: bool = False,
    has_contraindications: bool = False,
    has_smoking_enzyme_link: bool = False,
    contraception_days_from_smpc: int | None = None,
    tmax_h: float | None = None,
) -> CriteriaEvaluationResult:
    rules = ["CRIT-01", "CRIT-02"]
    overlays: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    if has_cyp_mentions:
        rules.append("CRIT-03")
        overlays.append(
            {
                "type": "CYP",
                "note": "CYP inhibitors/inducers mentioned — concrete lists must come from SmPC evidence, not hardcoded.",
                "evidence_claim_ids": list(smpc_evidence_claim_ids or []),
            }
        )
    if has_contraindications:
        rules.append("CRIT-04")
        overlays.append({"type": "CONTRAINDICATION", "evidence_claim_ids": list(smpc_evidence_claim_ids or [])})
    if tmax_h is not None:
        rules.append("CRIT-05")
        overlays.append(
            {
                "type": "VOMITING_WINDOW_PROPOSED",
                "expression": "2 * tmax",
                "tmax_h": tmax_h,
                "proposed_window_h": 2.0 * float(tmax_h),
                "status": "PROPOSED",
            }
        )
    if has_smoking_enzyme_link:
        rules.append("CRIT-06")
    rules.append("CRIT-07")
    if contraception_days_from_smpc is None:
        gaps.append(
            {
                "domain": "ELIGIBILITY",
                "question": "Contraception period not provided from SmPC evidence.",
                "importance": "MEDIUM",
                "blocking": False,
                "related_rule_id": "CRIT-07",
            }
        )
    else:
        overlays.append(
            {
                "type": "CONTRACEPTION",
                "days": contraception_days_from_smpc,
                "source": "SMPC_EVIDENCE",
            }
        )
    return CriteriaEvaluationResult(
        applied_rules=sorted(set(rules)),
        standard_note="Standard criteria are conceptual; drug-specific overlays require SmPC provenance.",
        drug_specific_overlays=overlays,
        knowledge_gaps=gaps,
    )


@dataclass
class SourcePriorityProfile:
    ordered_classes: list[str] = field(
        default_factory=lambda: [
            "EEC_DECISION_85",
            "FDA",
            "EMA",
            "REGULATORY_REPORT",
            "SCIENTIFIC_ARTICLE",
        ]
    )
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_source_priority_profile() -> SourcePriorityProfile:
    return SourcePriorityProfile(
        knowledge_gaps=[
            {
                "domain": "SOURCE",
                "question": "Formal source conflict resolution algorithm needs expert confirmation.",
                "importance": "HIGH",
                "blocking": False,
                "related_rule_id": "SOURCE-01",
            }
        ]
    )


def safety_foundation_note() -> dict[str, Any]:
    return {
        "rule": "SAFETY-01",
        "status": "PROPOSED",
        "note": "Standard BE safety set exists conceptually — checklist not invented.",
        "knowledge_gaps": [
            {
                "domain": "SAFETY",
                "question": "Reference safety protocol after June 2026 has not yet been formalized.",
                "importance": "MEDIUM",
                "blocking": False,
                "related_rule_id": "SAFETY-01",
            }
        ],
    }

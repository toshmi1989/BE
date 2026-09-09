"""Evidence matrix + recommendation helpers — Phase 15.0 / 15.1."""

from __future__ import annotations

from typing import Any

from app.domain.decision_classes import display_option
from app.domain.decision_models import DecisionEvidence, DecisionRecommendation, require_evidence_for_recommendation


def evidence(
    *,
    evidence_type: str,
    support_level: str,
    option: str | None = None,
    excerpt: str,
    status: str = "PROPOSED",
    source_id: str | None = None,
    claim_id: str | None = None,
    rule_id: str | None = None,
    value_id: str | None = None,
    location: str | None = None,
    relevance: str = "MEDIUM",
    notes: str | None = None,
    decision_source_type: str | None = None,
    applicability: str = "UNKNOWN",
    applicability_reason: str = "",
) -> DecisionEvidence:
    from app.domain.decision_applicability import classify_decision_input_source

    src = decision_source_type or classify_decision_input_source(evidence_type=evidence_type)
    return DecisionEvidence(
        evidence_type=evidence_type,
        support_level=support_level,
        option=option,
        excerpt=excerpt,
        status=status,
        source_id=source_id,
        claim_id=claim_id,
        rule_id=rule_id,
        value_id=value_id,
        location=location,
        relevance=relevance,
        notes=notes,
        decision_source_type=src,
        applicability=applicability,
        applicability_reason=applicability_reason,
    )


def build_option_matrix_row(
    *,
    option: str,
    evidence: list[DecisionEvidence],
    recommendation_status: str,
    missing: list[str],
) -> dict[str, Any]:
    related = [e for e in evidence if e.option in {None, option} or e.option == option]
    supporting = [e for e in related if e.support_level == "SUPPORTS"]
    contradicting = [e for e in related if e.support_level == "CONTRADICTS"]
    direct_support = [
        e
        for e in supporting
        if e.applicability in {"DIRECT", "HIGH", "MODERATE"}
        or e.decision_source_type == "CURRENT_STUDY_FACT"
    ]
    verified_present = any(e.is_verified for e in supporting)
    proposed_present = any(not e.is_verified for e in supporting)
    return {
        "option": option,
        "option_label": display_option(option),
        "recommendation_status": recommendation_status,
        "evidence_present": bool(supporting or contradicting),
        "evidence_verified": verified_present,
        "evidence_missing": list(missing),
        "evidence_conflicting": bool(contradicting),
        "supporting": [
            {
                "id": e.id,
                "type": e.evidence_type,
                "status": e.status,
                "verification_status": e.status,
                "applicability": e.applicability,
                "applicability_reason": e.applicability_reason,
                "decision_source_type": e.decision_source_type,
                "support_level": e.support_level,
                "excerpt": e.excerpt,
                "verified": e.is_verified,
                "counts_as_direct_support": e in direct_support,
            }
            for e in supporting
        ],
        "contradicting": [
            {
                "id": e.id,
                "type": e.evidence_type,
                "status": e.status,
                "verification_status": e.status,
                "applicability": e.applicability,
                "excerpt": e.excerpt,
                "verified": e.is_verified,
            }
            for e in contradicting
        ],
        "note": (
            "Verified evidence present"
            if verified_present
            else ("Proposed/interview evidence only" if proposed_present else "No supporting evidence")
        ),
    }


def make_recommendation(
    *,
    option: str,
    status: str,
    confidence: str,
    evidence: list[DecisionEvidence],
    missing_codes: list[str] | None = None,
    blocking_conflicts: list[str] | None = None,
    rationale: str,
    explanation: dict[str, Any] | None = None,
) -> DecisionRecommendation:
    supporting = [e.id for e in evidence if e.support_level == "SUPPORTS" and e.option in {None, option}]
    contradicting = [e.id for e in evidence if e.support_level == "CONTRADICTS" and e.option in {None, option}]
    if not supporting:
        supporting = [e.id for e in evidence if e.support_level == "SUPPORTS"]
    rec = DecisionRecommendation(
        option=option,
        status=status,
        confidence=confidence,
        supporting_evidence_ids=supporting,
        contradicting_evidence_ids=contradicting,
        missing_evidence_ids=list(missing_codes or []),
        blocking_conflicts=list(blocking_conflicts or []),
        rationale=rationale,
        explanation=explanation
        or {
            "why": rationale,
            "missing": list(missing_codes or []),
            "caution": list(blocking_conflicts or []),
            "required_action": "Medical writer review",
        },
    )
    if status in {"SUPPORTED", "PARTIALLY_SUPPORTED"}:
        require_evidence_for_recommendation(rec)
    return rec

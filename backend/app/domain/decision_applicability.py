"""Evidence applicability — Phase 15.1.

verification_status and applicability are independent dimensions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.decision_dependency import APPLICABILITY_VALUES, DECISION_INPUT_SOURCE_TYPES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EvidenceApplicability:
    evidence_id: str
    decision_id: str | None = None
    applicability: str = "UNKNOWN"
    applicability_reason: str = ""
    review_status: str = "PROPOSED"  # PROPOSED|REVIEWED|STALE|REQUIRES_REVIEW
    source_version_id: str | None = None
    dimensions: dict[str, str] = field(default_factory=dict)
    # e.g. active_substance, dosage_form, dose, population, design, condition, route, pk_context, jurisdiction
    id: str = field(default_factory=lambda: f"EA-{uuid4().hex[:10]}")
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    assessed_by: str | None = None  # human or "DETERMINISTIC"; never AI as final

    def __post_init__(self) -> None:
        if self.applicability not in APPLICABILITY_VALUES:
            raise ValueError(f"Invalid applicability: {self.applicability}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def mark_stale(self, *, reason: str) -> None:
        self.review_status = "STALE"
        self.applicability_reason = (self.applicability_reason or "") + f" | STALE: {reason}"
        self.updated_at = _now()


def classify_decision_input_source(
    *,
    evidence_type: str,
    is_system_recommendation: bool = False,
    is_expert_decision: bool = False,
) -> str:
    if is_system_recommendation:
        return "SYSTEM_RECOMMENDATION"
    if is_expert_decision or evidence_type == "EXPERT_DECISION":
        return "EXPERT_DECISION"
    if evidence_type in {"STRUCTURED_STUDY_FACT"}:
        return "CURRENT_STUDY_FACT"
    if evidence_type in {"EXPERT_RULE", "REGULATORY_RULE"}:
        return "RULE"
    return "EVIDENCE"


def assess_analogue_applicability(
    *,
    same_substance: bool | None = None,
    same_dosage_form: bool | None = None,
    same_dose: bool | None = None,
    same_population: bool | None = None,
    same_design: bool | None = None,
) -> EvidenceApplicability:
    """Deterministic heuristic — never auto-DIRECT for merely similar studies."""
    dims = {
        "active_substance": "SAME" if same_substance else ("DIFFERENT" if same_substance is False else "UNKNOWN"),
        "dosage_form": "SAME" if same_dosage_form else ("DIFFERENT" if same_dosage_form is False else "UNKNOWN"),
        "dose": "SAME" if same_dose else ("DIFFERENT" if same_dose is False else "UNKNOWN"),
        "population": "SAME" if same_population else ("DIFFERENT" if same_population is False else "UNKNOWN"),
        "design": "SAME" if same_design else ("DIFFERENT" if same_design is False else "UNKNOWN"),
    }
    if same_substance is False:
        appl, reason = "LOW", "Different active substance — not direct evidence"
    elif same_substance and same_dosage_form and same_dose and same_population:
        appl, reason = "HIGH", "Same substance/form/dose/population — still not automatically DIRECT"
    elif same_substance and same_dosage_form and same_population and same_dose is False:
        appl, reason = "MODERATE", "Same substance/form/population, different dose"
    elif same_substance and same_dosage_form:
        appl, reason = "MODERATE", "Same substance and dosage form; other dimensions incomplete"
    elif same_substance is None:
        appl, reason = "UNKNOWN", "Applicability dimensions not fully reviewed"
    else:
        appl, reason = "LOW", "Limited similarity"
    return EvidenceApplicability(
        evidence_id="pending",
        applicability=appl,
        applicability_reason=reason,
        review_status="PROPOSED",
        dimensions=dims,
        assessed_by="DETERMINISTIC",
    )


def assess_regulatory_applicability(
    *,
    explicitly_same_context: bool | None = None,
    reviewed: bool = False,
) -> EvidenceApplicability:
    if explicitly_same_context is True:
        appl, reason = "DIRECT", "Claim explicitly addresses the same BE design situation"
        status = "REVIEWED" if reviewed else "PROPOSED"
    elif explicitly_same_context is False:
        appl, reason = "NOT_APPLICABLE", "Claim does not address the current BE context"
        status = "REVIEWED" if reviewed else "PROPOSED"
    else:
        appl, reason = "UNKNOWN", "Claim exists but contextual applicability has not been reviewed"
        status = "PROPOSED"
    return EvidenceApplicability(
        evidence_id="pending",
        applicability=appl,
        applicability_reason=reason,
        review_status=status,
        assessed_by="DETERMINISTIC" if explicitly_same_context is not None else None,
    )


def apply_ai_applicability_proposal(
    current: EvidenceApplicability,
    *,
    proposed_applicability: str,
    reason: str,
) -> EvidenceApplicability:
    """AI may propose only — remains PROPOSED; cannot finalize."""
    if proposed_applicability not in APPLICABILITY_VALUES:
        raise ValueError("Invalid AI applicability")
    return EvidenceApplicability(
        evidence_id=current.evidence_id,
        decision_id=current.decision_id,
        applicability=proposed_applicability,
        applicability_reason=f"AI proposal (PROPOSED only): {reason}",
        review_status="PROPOSED",
        source_version_id=current.source_version_id,
        dimensions=dict(current.dimensions),
        assessed_by="AI",
    )


def stale_on_source_version_change(
    items: list[EvidenceApplicability],
    *,
    evidence_id: str,
    old_version: str,
    new_version: str,
) -> list[EvidenceApplicability]:
    out = []
    for it in items:
        if it.evidence_id == evidence_id and it.source_version_id == old_version:
            it.mark_stale(reason=f"source_version {old_version} → {new_version}")
            it.review_status = "REQUIRES_REVIEW"
            out.append(it)
    return out


def assert_source_type_valid(source_type: str) -> None:
    if source_type not in DECISION_INPUT_SOURCE_TYPES:
        raise ValueError(f"Invalid decision input source type: {source_type}")

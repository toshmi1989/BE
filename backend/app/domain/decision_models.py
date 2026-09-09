"""ProtocolDecision / DecisionEvidence / Recommendation models — Phase 15.0."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.decision_classes import (
    CONFIDENCE_LEVELS,
    DECISION_DOMAINS,
    DECISION_STATUSES,
    DOMAIN_OPTIONS,
    EVIDENCE_TYPES,
    RECOMMENDATION_STATUSES,
    SUPPORT_LEVELS,
    display_domain,
    display_option,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DecisionEvidence:
    evidence_type: str
    support_level: str
    id: str = field(default_factory=lambda: f"DE-{uuid4().hex[:12]}")
    decision_id: str | None = None
    claim_id: str | None = None
    value_id: str | None = None
    rule_id: str | None = None
    source_id: str | None = None
    relevance: str = "MEDIUM"  # HIGH|MEDIUM|LOW|UNKNOWN
    excerpt: str | None = None
    location: str | None = None
    status: str = "PROPOSED"  # PROPOSED|VERIFIED|REJECTED — evidence verification status
    option: str | None = None  # which option this evidence relates to
    created_at: str = field(default_factory=_now)
    notes: str | None = None
    decision_source_type: str = "EVIDENCE"  # CURRENT_STUDY_FACT|EVIDENCE|RULE|...
    applicability: str = "UNKNOWN"
    applicability_reason: str = ""

    def __post_init__(self) -> None:
        if self.evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f"Invalid evidence_type: {self.evidence_type}")
        if self.support_level not in SUPPORT_LEVELS:
            raise ValueError(f"Invalid support_level: {self.support_level}")
        if not (self.claim_id or self.value_id or self.rule_id or self.source_id or self.excerpt):
            raise ValueError("DecisionEvidence requires provenance identity or excerpt")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def is_verified(self) -> bool:
        return self.status == "VERIFIED"


@dataclass
class DecisionRecommendation:
    option: str
    status: str
    confidence: str
    id: str = field(default_factory=lambda: f"DR-{uuid4().hex[:12]}")
    decision_id: str | None = None
    version: int = 1
    supporting_evidence_ids: list[str] = field(default_factory=list)
    contradicting_evidence_ids: list[str] = field(default_factory=list)
    missing_evidence_ids: list[str] = field(default_factory=list)
    blocking_conflicts: list[str] = field(default_factory=list)
    rationale: str = ""
    explanation: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)
    superseded: bool = False

    def __post_init__(self) -> None:
        if self.status not in RECOMMENDATION_STATUSES:
            raise ValueError(f"Invalid recommendation status: {self.status}")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise ValueError(f"Invalid confidence: {self.confidence}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["option_label"] = display_option(self.option)
        d["status_is_not_approved"] = True  # recommendation ≠ expert approval
        return d


@dataclass
class ProtocolDecision:
    domain: str
    subject: str
    id: str = field(default_factory=lambda: f"PD-{uuid4().hex[:12]}")
    study_id: str | None = None
    project_id: str | None = None
    package_id: str | None = None
    status: str = "DRAFT"
    recommendation: DecisionRecommendation | None = None
    recommendation_history: list[DecisionRecommendation] = field(default_factory=list)
    evidence: list[DecisionEvidence] = field(default_factory=list)
    option_matrix: list[dict[str, Any]] = field(default_factory=list)
    current_context: dict[str, Any] = field(default_factory=dict)
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    research_tasks: list[dict[str, Any]] = field(default_factory=list)
    blocking_conflicts: list[str] = field(default_factory=list)
    blocking_reasons: list[dict[str, Any]] = field(default_factory=list)
    non_blocking_issues: list[dict[str, Any]] = field(default_factory=list)
    applicability_assessments: list[dict[str, Any]] = field(default_factory=list)
    selected_option: str | None = None
    expert_decision_id: str | None = None
    expert_actions: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    study_mutated: bool = False

    def __post_init__(self) -> None:
        if self.domain not in DECISION_DOMAINS:
            raise ValueError(f"Invalid domain: {self.domain}")
        if self.status not in DECISION_STATUSES:
            raise ValueError(f"Invalid decision status: {self.status}")

    def to_dict(self, *, for_ui: bool = False) -> dict[str, Any]:
        rec = self.recommendation.to_dict() if self.recommendation else None
        d: dict[str, Any] = {
            "id": self.id,
            "study_id": self.study_id,
            "project_id": self.project_id,
            "package_id": self.package_id,
            "domain": self.domain,
            "domain_label": display_domain(self.domain),
            "subject": self.subject,
            "status": self.status,
            "recommendation": rec,
            "recommendation_history": [r.to_dict() for r in self.recommendation_history],
            "evidence": [e.to_dict() for e in self.evidence],
            "option_matrix": list(self.option_matrix),
            "current_context": dict(self.current_context),
            "knowledge_gaps": list(self.knowledge_gaps),
            "research_tasks": list(self.research_tasks),
            "blocking_conflicts": list(self.blocking_conflicts),
            "blocking_reasons": list(self.blocking_reasons),
            "non_blocking_issues": list(self.non_blocking_issues),
            "applicability_assessments": list(self.applicability_assessments),
            "selected_option": self.selected_option,
            "selected_option_label": display_option(self.selected_option) if self.selected_option else None,
            "expert_decision_id": self.expert_decision_id,
            "expert_actions": list(self.expert_actions),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "study_mutated": False,
            "options": [
                {"code": o, "label": display_option(o)} for o in DOMAIN_OPTIONS.get(self.domain, ())
            ],
        }
        if for_ui:
            d["display"] = {
                "domain": display_domain(self.domain),
                "status": self.status,
                "recommendation_option": display_option(self.recommendation.option)
                if self.recommendation
                else None,
                "recommendation_status": self.recommendation.status if self.recommendation else None,
                "approved": self.status == "APPROVED",
                "recommended_is_not_approved": self.status != "APPROVED",
                "blocking_why": [
                    b.get("blocking_reason_code") or b.get("message") for b in self.blocking_reasons
                ],
                "non_blocking_why": [
                    b.get("blocking_reason_code") or b.get("message") for b in self.non_blocking_issues
                ],
            }
        return d


@dataclass
class AnalogueStudyEvidence:
    study_reference: str
    id: str = field(default_factory=lambda: f"ANL-{uuid4().hex[:10]}")
    population: str | None = None
    product: str | None = None
    dose: str | None = None
    design: str | None = None
    condition: str | None = None
    sampling: str | None = None
    relevance: str = "UNKNOWN"  # HIGH|MEDIUM|LOW|UNKNOWN
    source_id: str | None = None
    claim: str | None = None
    review_status: str = "PROPOSED"
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["identical_to_current"] = False  # never assume analogue = identical
        return d


def require_evidence_for_recommendation(rec: DecisionRecommendation) -> None:
    if rec.status in {"SUPPORTED", "PARTIALLY_SUPPORTED"} and not (
        rec.supporting_evidence_ids or rec.rationale
    ):
        raise ValueError("Recommendation without evidence is rejected")

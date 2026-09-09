"""Phase 15.5 — StatisticsPlan domain models (immutable versions)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.statistics_engine_classes import (
    ANALYSIS_POPULATIONS,
    DESCRIPTIVE_STATS,
    ESTIMATE_KINDS,
    METHODOLOGY_VERSION,
    PARAMETER_ROLES,
    PLAN_STATUSES,
    REVIEW_ACTIONS,
    SOURCE_ROLES,
    STATISTICS_ENGINE_VERSION,
    SUPPORTED_MODELS,
    TRANSFORMATIONS,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProvenancedChoice:
    name: str
    value: Any
    source_role: str
    id: str = field(default_factory=lambda: f"SPC-{uuid4().hex[:10]}")
    source_evidence_ids: list[str] = field(default_factory=list)
    source_decision_ids: list[str] = field(default_factory=list)
    original_wording: str | None = None
    notes: str | None = None
    verification_status: str | None = None

    def __post_init__(self) -> None:
        if self.source_role not in SOURCE_ROLES:
            raise ValueError(f"Invalid source_role: {self.source_role}")
        if self.source_role == "PROPOSED_EVIDENCE":
            # Allowed to record, but never authoritative — engine must not use alone
            pass
        if self.value is None:
            raise ValueError(f"Choice {self.name} requires a value")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AcceptanceIntervalSpec:
    lower_bound: float
    upper_bound: float
    source_role: str
    verification_status: str = "UNVERIFIED"
    source_evidence_ids: list[str] = field(default_factory=list)
    original_wording: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StatisticalParameterPlan:
    parameter: str
    role: str
    transformation: str
    model: str | None
    estimate: str
    confidence_interval: float | None  # e.g. 0.90
    acceptance_interval: AcceptanceIntervalSpec | None
    summary_method: list[str] = field(default_factory=list)
    source_evidence_ids: list[str] = field(default_factory=list)
    source_decision_ids: list[str] = field(default_factory=list)
    status: str = "DRAFT"
    original_wording: str | None = None
    model_terms: list[str] = field(default_factory=list)
    planned_gmr: Any = None  # never fabricate observed GMR
    planned_ci_result: Any = None  # never fabricate observed CI
    observed_data_present: bool = False
    id: str = field(default_factory=lambda: f"SPP-{uuid4().hex[:10]}")
    plan_id: str | None = None
    blocking_reasons: list[str] = field(default_factory=list)
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.role not in PARAMETER_ROLES:
            raise ValueError(f"Invalid role: {self.role}")
        if self.transformation not in TRANSFORMATIONS:
            raise ValueError(f"Invalid transformation: {self.transformation}")
        if self.estimate not in ESTIMATE_KINDS:
            raise ValueError(f"Invalid estimate: {self.estimate}")
        if self.model is not None and self.model not in SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {self.model}")
        for s in self.summary_method:
            if s not in DESCRIPTIVE_STATS and s not in {"Range"}:
                raise ValueError(f"Unsupported summary statistic: {s}")
        # Hard guard: never store fabricated results
        self.planned_gmr = None
        self.planned_ci_result = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["acceptance_interval"] = (
            self.acceptance_interval.to_dict() if self.acceptance_interval else None
        )
        d["planned_gmr"] = None
        d["planned_ci_result"] = None
        d["fabricated_results"] = False
        return d

    def display_dict(self) -> dict[str, Any]:
        """UI contract — human labels, no raw enum dump required by callers."""
        from app.domain.statistics_engine_classes import (
            MODEL_LABELS,
            ROLE_LABELS_RU,
            TRANSFORM_LABELS,
        )

        ai = None
        if self.acceptance_interval:
            lo = self.acceptance_interval.lower_bound * 100
            hi = self.acceptance_interval.upper_bound * 100
            ai = f"{lo:.2f}–{hi:.2f}%"
        return {
            "parameter": self.parameter,
            "role_label": ROLE_LABELS_RU.get(self.role, self.role),
            "transform_label": TRANSFORM_LABELS.get(self.transformation, self.transformation),
            "model_label": MODEL_LABELS.get(self.model or "", self.model),
            "ci_label": f"{int(self.confidence_interval * 100)}%" if self.confidence_interval else None,
            "acceptance_label": ai,
            "summary": list(self.summary_method),
            "status": self.status,
            "exposes_internal_enums": False,
        }


@dataclass
class StatisticsScenario:
    label: str
    primary_parameters: list[str]
    id: str = field(default_factory=lambda: f"SSCEN-{uuid4().hex[:10]}")
    parameter_ids: list[str] = field(default_factory=list)
    status: str = "REQUIRES_EXPERT_SELECTION"
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StatisticsExpertReview:
    plan_id: str
    reviewer: str
    action: str
    plan_version: int
    comment: str = ""
    timestamp: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: f"SREV-{uuid4().hex[:10]}")
    modifications: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action not in REVIEW_ACTIONS:
            raise ValueError(f"Invalid review action: {self.action}")
        if not self.reviewer or not str(self.reviewer).strip():
            raise ValueError("reviewer required")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["study_mutated"] = False
        return d


@dataclass
class StatisticsPlan:
    study_id: str
    id: str = field(default_factory=lambda: f"STP-{uuid4().hex[:12]}")
    decision_id: str | None = None
    version: int = 1
    status: str = "DRAFT"
    created_at: str = field(default_factory=_now)
    created_by: str | None = None
    methodology_version: str = METHODOLOGY_VERSION
    engine_version: str = STATISTICS_ENGINE_VERSION
    explanation: str = ""
    design: str | None = None
    model: str | None = None
    model_terms: list[str] = field(default_factory=list)
    confidence_level: float | None = None
    alpha: float | None = None
    alpha_derivation: str | None = None
    acceptance_interval: AcceptanceIntervalSpec | None = None
    analysis_population: str | None = None
    parameters: list[StatisticalParameterPlan] = field(default_factory=list)
    scenarios: list[StatisticsScenario] = field(default_factory=list)
    choices: list[ProvenancedChoice] = field(default_factory=list)
    current_study_facts: dict[str, Any] = field(default_factory=dict)
    recommendation_summary: str | None = None
    blocking_reasons: list[str] = field(default_factory=list)
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    reviews: list[StatisticsExpertReview] = field(default_factory=list)
    supersedes_id: str | None = None
    fingerprint: str | None = None
    observed_data_present: bool = False
    study_mutated: bool = False
    is_recommendation_not_approval: bool = True
    audit: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status not in PLAN_STATUSES:
            raise ValueError(f"Invalid status: {self.status}")
        if self.analysis_population is not None and self.analysis_population not in ANALYSIS_POPULATIONS:
            raise ValueError(f"Invalid analysis_population: {self.analysis_population}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["parameters"] = [p.to_dict() for p in self.parameters]
        d["scenarios"] = [s.to_dict() for s in self.scenarios]
        d["choices"] = [c.to_dict() for c in self.choices]
        d["acceptance_interval"] = (
            self.acceptance_interval.to_dict() if self.acceptance_interval else None
        )
        d["reviews"] = [r.to_dict() for r in self.reviews]
        d["study_mutated"] = False
        d["is_recommendation_not_approval"] = True
        d["fabricated_gmr"] = False
        d["fabricated_ci"] = False
        return d

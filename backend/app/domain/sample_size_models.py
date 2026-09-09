"""Phase 15.4 — Sample Size Engine domain models (immutable calculation records)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.sample_size_engine_classes import (
    CALCULATION_STATUSES,
    CALCULATION_VERSION,
    INFLATION_METHODS,
    INPUT_SOURCE_KINDS,
    RECOMMENDATION_OPTIONS,
    REVIEW_DECISIONS,
    ROUNDING_RULES,
    SAMPLE_SIZE_ENGINE_VERSION,
    SAMPLE_SIZE_PK_PARAMETERS,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ProvenancedInput:
    """Every non-derived input must carry provenance — no anonymous values."""

    name: str
    value: Any
    source_kind: str
    id: str = field(default_factory=lambda: f"SSI-{uuid4().hex[:10]}")
    source_claim_id: str | None = None
    source_measurement_id: str | None = None
    source_label: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.source_kind not in INPUT_SOURCE_KINDS:
            raise ValueError(f"Invalid source_kind: {self.source_kind}")
        if self.value is None:
            raise ValueError(f"Input {self.name} value required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SampleSizeScenario:
    parameter: str
    required_n: int | None
    randomized_n: int | None
    raw_n: float | None
    achieved_power: float | None
    target_power: float
    cv_value: float
    cv_unit: str
    cv_source_claim_id: str | None
    status: str = "CALCULATED"
    blocking_reasons: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: f"SSS-{uuid4().hex[:10]}")

    def __post_init__(self) -> None:
        if self.parameter not in SAMPLE_SIZE_PK_PARAMETERS:
            raise ValueError(f"Unsupported sample-size parameter: {self.parameter}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SampleSizeRecommendation:
    option: str = "REQUIRES_EXPERT_DECISION"
    current_protocol_n: int | None = None
    calculated_randomized_n: int | None = None
    rationale: str = "Expert must choose; calculation is not a decision"
    auto_selected: bool = False
    id: str = field(default_factory=lambda: f"SSR-{uuid4().hex[:10]}")

    def __post_init__(self) -> None:
        if self.option not in RECOMMENDATION_OPTIONS:
            raise ValueError(f"Invalid recommendation option: {self.option}")
        if self.auto_selected:
            raise ValueError("Recommendations must not be auto-selected")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_not_approval"] = True
        d["auto_selected"] = False
        return d


@dataclass
class SampleSizeExpertReview:
    calculation_id: str
    reviewer: str
    decision: str
    comment: str = ""
    timestamp: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: f"SSRV-{uuid4().hex[:10]}")
    projected_to_study: bool = False

    def __post_init__(self) -> None:
        if self.decision not in REVIEW_DECISIONS:
            raise ValueError(f"Invalid review decision: {self.decision}")
        if not self.reviewer or not str(self.reviewer).strip():
            raise ValueError("reviewer required")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["study_mutated"] = False
        return d


@dataclass
class SampleSizeDiscrepancy:
    current_protocol_n: int
    calculated_randomized_n: int
    current_source: str = "SYNOPSIS"
    status: str = "DISCREPANCY"
    code: str = "SAMPLE_SIZE_DISCREPANCY"
    note: str = "Not an automatic error — requires expert interpretation"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SampleSizeCalculationRecord:
    """Immutable authoritative calculation record (create new version on input change)."""

    study_id: str
    design: str
    id: str = field(default_factory=lambda: f"SSC-{uuid4().hex[:12]}")
    decision_id: str | None = None
    parameter: str | None = None
    cv_value: float | None = None
    cv_unit: str = "%"
    expected_ratio: float | None = None
    alpha: float | None = None
    power: float | None = None  # target
    target_power: float | None = None
    achieved_power: float | None = None
    dropout_percent: float | None = None
    inflation_method: str | None = None
    required_n: int | None = None
    randomized_n: int | None = None
    raw_n: float | None = None
    rounding_rule: str = "CEIL_EVEN_2X2"
    method: str | None = None
    calculation_version: str = CALCULATION_VERSION
    engine_version: str = SAMPLE_SIZE_ENGINE_VERSION
    algorithm_version: str | None = None
    status: str = "BLOCKED"
    fingerprint: str | None = None
    version_number: int = 1
    supersedes_id: str | None = None
    inputs: list[ProvenancedInput] = field(default_factory=list)
    scenarios: list[SampleSizeScenario] = field(default_factory=list)
    controlling_parameter: str | None = None
    controlling_requires_expert: bool = True
    recommendation: SampleSizeRecommendation | None = None
    discrepancy: SampleSizeDiscrepancy | None = None
    reviews: list[SampleSizeExpertReview] = field(default_factory=list)
    explanation: str = ""
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    current_protocol_n: int | None = None
    current_protocol_n_source: str | None = None
    be_lower: float | None = None
    be_upper: float | None = None
    formula: str | None = None
    software_version: str | None = None
    study_mutated: bool = False
    created_at: str = field(default_factory=_now)
    created_by: str | None = None
    eligible_for_protocol_use: bool = False

    def __post_init__(self) -> None:
        if self.status not in CALCULATION_STATUSES:
            raise ValueError(f"Invalid status: {self.status}")
        if self.inflation_method is not None and self.inflation_method not in INFLATION_METHODS:
            raise ValueError(f"Invalid inflation_method: {self.inflation_method}")
        if self.rounding_rule not in ROUNDING_RULES:
            raise ValueError(f"Invalid rounding_rule: {self.rounding_rule}")
        if self.target_power is None and self.power is not None:
            self.target_power = self.power

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["inputs"] = [i.to_dict() if hasattr(i, "to_dict") else i for i in self.inputs]
        d["scenarios"] = [s.to_dict() if hasattr(s, "to_dict") else s for s in self.scenarios]
        d["recommendation"] = (
            self.recommendation.to_dict() if self.recommendation else None
        )
        d["discrepancy"] = self.discrepancy.to_dict() if self.discrepancy else None
        d["reviews"] = [r.to_dict() if hasattr(r, "to_dict") else r for r in self.reviews]
        d["study_mutated"] = False
        d["is_not_approved_protocol_value"] = True
        d["eligible_for_protocol_use"] = bool(
            self.eligible_for_protocol_use and self.status == "ACCEPTED"
        )
        return d

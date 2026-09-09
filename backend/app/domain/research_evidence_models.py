"""Phase 15.2 — Research evidence domain models.

Extends KnowledgeGap → ResearchTask workflow. Does not duplicate ORM ResearchTask;
this is the study-scoped Decision Center research lane (in-memory + API).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.decision_dependency import APPLICABILITY_VALUES
from app.domain.research_evidence_classes import (
    EXTRACTION_METHODS,
    MATCH_DIMS,
    MATCH_VALUES,
    PK_PARAMETERS,
    PRIORITIES,
    PROVIDER_KINDS,
    QUERY_TYPES,
    RESEARCH_TASK_STATUSES,
    RESEARCH_TASK_TYPES,
    SOURCE_RESULT_TYPES,
    STATISTIC_TYPES,
    USABILITY_STATES,
    VARIABILITY_TYPES,
    VERIFICATION_STATUSES,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ResearchTask:
    """Study-scoped research task linked to a KnowledgeGap."""

    task_type: str
    question: str
    id: str = field(default_factory=lambda: f"RT-{uuid4().hex[:12]}")
    study_id: str | None = None
    knowledge_gap_id: str | None = None
    knowledge_gap_code: str | None = None
    query: str | None = None
    required_field_paths: list[str] = field(default_factory=list)
    status: str = "OPEN"
    priority: str = "HIGH"
    package_id: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    notes: str | None = None
    study_mutated: bool = False

    def __post_init__(self) -> None:
        if self.task_type not in RESEARCH_TASK_TYPES:
            raise ValueError(f"Invalid task_type: {self.task_type}")
        if self.status not in RESEARCH_TASK_STATUSES:
            raise ValueError(f"Invalid status: {self.status}")
        if self.priority not in PRIORITIES:
            raise ValueError(f"Invalid priority: {self.priority}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["study_mutated"] = False
        return d


@dataclass
class ResearchQuery:
    research_task_id: str
    query_text: str
    query_type: str
    id: str = field(default_factory=lambda: f"RQ-{uuid4().hex[:12]}")
    created_at: str = field(default_factory=_now)
    created_by: str = "DETERMINISTIC"
    study_id: str | None = None
    ai_proposed: bool = False  # True only if AI suggested alternative

    def __post_init__(self) -> None:
        if self.query_type not in QUERY_TYPES:
            raise ValueError(f"Invalid query_type: {self.query_type}")
        if not self.query_text or not str(self.query_text).strip():
            raise ValueError("query_text required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SourceResult:
    research_task_id: str
    provider: str
    title: str
    id: str = field(default_factory=lambda: f"SR-{uuid4().hex[:12]}")
    url_or_source_locator: str | None = None
    source_type: str = "OTHER"
    publication_date: str | None = None
    retrieved_at: str = field(default_factory=_now)
    author: str | None = None
    journal: str | None = None
    identifier: str | None = None  # DOI / registration / hash
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "RETRIEVED"
    text_excerpt: str | None = None
    content_hash: str | None = None
    registered_source_id: str | None = None
    registered_source_version_id: str | None = None
    study_id: str | None = None

    def __post_init__(self) -> None:
        if self.provider not in PROVIDER_KINDS:
            raise ValueError(f"Invalid provider: {self.provider}")
        if self.source_type not in SOURCE_RESULT_TYPES:
            raise ValueError(f"Invalid source_type: {self.source_type}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RegisteredSource:
    """Bridge into existing Source / SourceVersion vocabulary (domain mirror)."""

    locator: str
    source_type: str
    id: str = field(default_factory=lambda: f"SRC-{uuid4().hex[:10]}")
    title: str | None = None
    version_id: str = field(default_factory=lambda: f"SV-{uuid4().hex[:10]}")
    version: str = "1"
    content_hash: str | None = None
    retrieved_at: str = field(default_factory=_now)
    classification: str | None = None
    study_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceMeasurement:
    parameter: str
    value: Any = None
    unit: str | None = None
    id: str = field(default_factory=lambda: f"EM-{uuid4().hex[:10]}")
    parameter_context: str | None = None
    condition: str | None = None
    population: str | None = None
    dose: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    analyte: str | None = None
    study_design: str | None = None
    statistic_type: str = "UNKNOWN"
    range_low: Any = None
    range_high: Any = None
    source_claim_id: str | None = None
    applicability: str = "UNKNOWN"
    verification_status: str = "PROPOSED"
    usability: str = "REQUIRES_REVIEW"

    def __post_init__(self) -> None:
        if self.statistic_type not in STATISTIC_TYPES:
            raise ValueError(f"Invalid statistic_type: {self.statistic_type}")
        if self.applicability not in APPLICABILITY_VALUES:
            raise ValueError(f"Invalid applicability: {self.applicability}")
        if self.verification_status not in VERIFICATION_STATUSES:
            raise ValueError(f"Invalid verification_status: {self.verification_status}")
        if self.usability not in USABILITY_STATES:
            raise ValueError(f"Invalid usability: {self.usability}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CVintraEvidence:
    CV_value: Any = None
    CV_unit: str | None = "%"
    PK_parameter: str = "Cmax"
    id: str = field(default_factory=lambda: f"CV-{uuid4().hex[:10]}")
    parameter: str = "CVintra"
    variability_type: str = "WITHIN_SUBJECT"
    study_design: str | None = None
    treatment_context: str | None = None
    dose: str | None = None
    dosage_form: str | None = None
    population: str | None = None
    condition: str | None = None
    source_id: str | None = None
    source_claim_id: str | None = None
    applicability: str = "UNKNOWN"
    verification_status: str = "PROPOSED"
    usability: str = "REQUIRES_REVIEW"

    def __post_init__(self) -> None:
        if self.PK_parameter not in PK_PARAMETERS:
            raise ValueError(f"Invalid PK_parameter: {self.PK_parameter}")
        if self.variability_type not in VARIABILITY_TYPES:
            raise ValueError(f"Invalid variability_type: {self.variability_type}")
        if self.applicability not in APPLICABILITY_VALUES:
            raise ValueError(f"Invalid applicability: {self.applicability}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Never present between-subject as within-subject
        d["is_cvintra"] = self.variability_type == "WITHIN_SUBJECT"
        return d


@dataclass
class AnalogueStudyRecord:
    study_title: str
    id: str = field(default_factory=lambda: f"ANL-{uuid4().hex[:10]}")
    source_id: str | None = None
    source_version_id: str | None = None
    active_substance: str | None = None
    dose: str | None = None
    dosage_form: str | None = None
    population: str | None = None
    design: str | None = None
    condition: str | None = None
    sampling_summary: str | None = None
    analyte: str | None = None
    relevance: str = "UNKNOWN"
    applicability_status: str = "UNKNOWN"
    verification_status: str = "PROPOSED"
    match_dimensions: dict[str, str] = field(default_factory=dict)
    study_id: str | None = None

    def __post_init__(self) -> None:
        if self.applicability_status not in APPLICABILITY_VALUES:
            raise ValueError(f"Invalid applicability_status: {self.applicability_status}")
        for k, v in self.match_dimensions.items():
            if k not in MATCH_DIMS:
                raise ValueError(f"Invalid match dimension: {k}")
            if v not in MATCH_VALUES:
                raise ValueError(f"Invalid match value: {v}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["identical_to_current"] = False
        return d


@dataclass
class ResearchClaim:
    claim_text: str
    id: str = field(default_factory=lambda: f"RC-{uuid4().hex[:12]}")
    claim_id: str | None = None  # alias of id for API
    research_task_id: str | None = None
    field_path: str | None = None
    value: Any = None
    unit: str | None = None
    source_id: str | None = None
    source_version_id: str | None = None
    source_result_id: str | None = None
    location: str | None = None
    excerpt: str | None = None
    extraction_method: str = "DETERMINISTIC"
    confidence: str = "LOW"  # sufficiency label, not probability
    verification_status: str = "PROPOSED"
    applicability: str = "UNKNOWN"
    applicability_reason: str = ""
    usability: str = "REQUIRES_REVIEW"
    measurement: dict[str, Any] | None = None
    cvintra: dict[str, Any] | None = None
    decision_domains: list[str] = field(default_factory=list)
    review_history: list[dict[str, Any]] = field(default_factory=list)
    study_id: str | None = None
    study_mutated: bool = False

    def __post_init__(self) -> None:
        if self.claim_id is None:
            self.claim_id = self.id
        if self.extraction_method not in EXTRACTION_METHODS:
            raise ValueError(f"Invalid extraction_method: {self.extraction_method}")
        if self.verification_status not in VERIFICATION_STATUSES:
            raise ValueError(f"Invalid verification_status: {self.verification_status}")
        if self.applicability not in APPLICABILITY_VALUES:
            raise ValueError(f"Invalid applicability: {self.applicability}")
        if self.usability not in USABILITY_STATES:
            raise ValueError(f"Invalid usability: {self.usability}")
        if not (self.source_id or self.source_result_id or self.excerpt):
            raise ValueError("ResearchClaim requires provenance")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["study_mutated"] = False
        d["is_not_expert_decision"] = True
        return d


@dataclass
class EvidenceConflictRecord:
    field_path: str
    claim_ids: list[str]
    values: list[Any]
    id: str = field(default_factory=lambda: f"ECF-{uuid4().hex[:10]}")
    research_task_id: str | None = None
    severity: str = "HIGH"
    status: str = "OPEN"
    resolution: str | None = None
    study_id: str | None = None
    notes: str = "Do not average conflicting values"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchCoverage:
    knowledge_gap_code: str
    task_present: bool = False
    search_done: bool = False
    sources_count: int = 0
    candidate_claims: int = 0
    verified_claims: int = 0
    usable_evidence: int = 0
    status: str = "OPEN"
    study_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["green"] = (
            self.verified_claims > 0
            and self.usable_evidence > 0
            and self.status == "COMPLETED"
        )
        return d

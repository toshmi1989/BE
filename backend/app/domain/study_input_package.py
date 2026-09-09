"""CandidateStudyValue + StudyInputPackage models — Phase 14."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.study_input_classes import (
    CANDIDATE_STATUSES,
    DOCUMENT_TYPES,
    EXTRACTION_METHODS,
    FIELD_PATH_SET,
    PACKAGE_STATUSES,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CandidateStudyValue:
    field_path: str
    value: Any
    value_type: str
    source_id: str
    document_type: str
    id: str = field(default_factory=lambda: f"CSV-{uuid4().hex[:12]}")
    study_id: str | None = None
    source_version_id: str | None = None
    document_id: str | None = None
    location: str | None = None
    excerpt: str | None = None
    confidence: str = "MEDIUM"
    extraction_method: str = "DETERMINISTIC"
    status: str = "PROPOSED"
    original_filename: str | None = None
    created_at: str = field(default_factory=_now)
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.field_path not in FIELD_PATH_SET:
            raise ValueError(f"Invalid field_path: {self.field_path}")
        if self.status not in CANDIDATE_STATUSES:
            raise ValueError(f"Invalid candidate status: {self.status}")
        if self.extraction_method not in EXTRACTION_METHODS:
            raise ValueError(f"Invalid extraction_method: {self.extraction_method}")
        if self.document_type not in DOCUMENT_TYPES:
            raise ValueError(f"Invalid document_type: {self.document_type}")
        if not self.source_id:
            raise ValueError("source_id required")
        if not self.excerpt:
            raise ValueError("excerpt (provenance) required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StudyInputDocument:
    document_id: str
    source_id: str
    document_type: str
    original_filename: str
    content_hash: str
    mime_type: str | None = None
    source_version_id: str | None = None
    classification_method: str = "MANUAL"  # MANUAL|HEURISTIC|AI
    classification_confidence: str = "HIGH"
    classification_overridable: bool = True
    ingestion_status: str = "OK"  # OK|SUCCESS|PARTIAL|FAILED
    role: str = "INPUT"  # INPUT|REFERENCE_OUTPUT
    relative_path: str | None = None
    user_selected_type: bool = False
    file_size: int | None = None
    page_count: int | None = None
    paragraph_count: int | None = None
    table_count: int | None = None
    ingestion_warnings: list[str] = field(default_factory=list)
    superseded_by: str | None = None  # document_id of replacement
    previous_version_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StudyInputPackage:
    package_id: str
    status: str = "DRAFT"
    study_id: str | None = None
    project_id: str | None = None
    fixture_id: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    documents: list[StudyInputDocument] = field(default_factory=list)
    candidates: list[CandidateStudyValue] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    research_tasks: list[dict[str, Any]] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    blocking_issues: list[str] = field(default_factory=list)
    classification_status: str = "PENDING"
    notes: str | None = None
    ingestion_runs: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.status not in PACKAGE_STATUSES:
            raise ValueError(f"Invalid package status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "status": self.status,
            "study_id": self.study_id,
            "project_id": self.project_id,
            "fixture_id": self.fixture_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "documents": [d.to_dict() for d in self.documents],
            "candidates": [c.to_dict() for c in self.candidates],
            "conflicts": list(self.conflicts),
            "knowledge_gaps": list(self.knowledge_gaps),
            "research_tasks": list(self.research_tasks),
            "coverage": dict(self.coverage),
            "blocking_issues": list(self.blocking_issues),
            "classification_status": self.classification_status,
            "notes": self.notes,
            "ingestion_runs": list(self.ingestion_runs),
            "study_mutated": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StudyInputPackage":
        docs = [StudyInputDocument(**d) for d in (data.get("documents") or [])]
        cands = [CandidateStudyValue(**c) for c in (data.get("candidates") or [])]
        return cls(
            package_id=data["package_id"],
            status=data.get("status") or "DRAFT",
            study_id=data.get("study_id"),
            project_id=data.get("project_id"),
            fixture_id=data.get("fixture_id"),
            created_at=data.get("created_at") or _now(),
            updated_at=data.get("updated_at") or _now(),
            documents=docs,
            candidates=cands,
            conflicts=list(data.get("conflicts") or []),
            knowledge_gaps=list(data.get("knowledge_gaps") or []),
            research_tasks=list(data.get("research_tasks") or []),
            coverage=dict(data.get("coverage") or {}),
            blocking_issues=list(data.get("blocking_issues") or []),
            classification_status=data.get("classification_status") or "PENDING",
            notes=data.get("notes"),
            ingestion_runs=list(data.get("ingestion_runs") or []),
        )


def verify_candidate(candidate: CandidateStudyValue, *, reviewer: str) -> CandidateStudyValue:
    if not reviewer or not str(reviewer).strip():
        raise ValueError("reviewer required")
    if not candidate.excerpt or not candidate.source_id:
        raise ValueError("provenance incomplete")
    candidate.status = "VERIFIED"
    candidate.reviewed_by = reviewer
    candidate.reviewed_at = _now()
    return candidate


def reject_candidate(candidate: CandidateStudyValue, *, reviewer: str, notes: str | None = None) -> CandidateStudyValue:
    if not reviewer:
        raise ValueError("reviewer required")
    candidate.status = "REJECTED"
    candidate.reviewed_by = reviewer
    candidate.reviewed_at = _now()
    if notes:
        candidate.notes = (candidate.notes or "") + f" | {notes}"
    return candidate

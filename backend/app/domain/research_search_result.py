"""Phase 15.3 — Real search result models & source priority.

Priority ≠ verification. Official sources remain PROPOSED until review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


SOURCE_PRIORITY_CLASSES: tuple[str, ...] = (
    "OFFICIAL_REGULATORY",
    "OFFICIAL_PRODUCT",
    "PEER_REVIEWED",
    "CLINICAL_DATABASE",
    "PUBLICATION",
    "INTERNAL_PROTOCOL",
    "OTHER",
)

REAL_SOURCE_TYPES: tuple[str, ...] = (
    "REGULATORY",
    "SMPC",
    "PRODUCT_LABEL",
    "PUBLICATION",
    "CLINICAL_STUDY",
    "PROTOCOL",
    "DATABASE",
    "GUIDELINE",
    "REVIEW",
    "OTHER",
    "UNKNOWN",
)

RESEARCH_RUN_STATUSES: tuple[str, ...] = (
    "OK",
    "PARTIAL",
    "RESEARCH_FAILED",
    "NO_USABLE_EVIDENCE",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ResearchSearchResult:
    title: str
    url: str
    id: str = field(default_factory=lambda: f"RSR-{uuid4().hex[:12]}")
    provider: str = "WEB"
    snippet: str | None = None
    source_type: str = "UNKNOWN"
    publication_date: str | None = None
    authors: str | None = None
    identifier: str | None = None
    retrieved_at: str = field(default_factory=_now)
    raw_metadata: dict[str, Any] = field(default_factory=dict)
    priority_class: str = "OTHER"
    research_task_id: str | None = None
    study_id: str | None = None
    registered: bool = False
    registered_source_id: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.priority_class not in SOURCE_PRIORITY_CLASSES:
            raise ValueError(f"Invalid priority_class: {self.priority_class}")
        if self.source_type not in REAL_SOURCE_TYPES:
            # tolerate unknown → UNKNOWN
            self.source_type = "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["priority_is_not_verification"] = True
        d["verification_status"] = None  # never auto-verified
        return d


@dataclass
class SourceSnapshot:
    locator: str
    retrieved_at: str = field(default_factory=_now)
    content_hash: str | None = None
    source_version_id: str | None = None
    mime_type: str | None = None
    document_metadata: dict[str, Any] = field(default_factory=dict)
    text_excerpt: str | None = None
    page_count: int | None = None
    paragraph_count: int | None = None
    table_count: int | None = None
    snapshot_complete: bool = True
    snapshot_limitations: list[str] = field(default_factory=list)
    study_mutated: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["study_mutated"] = False
        return d


@dataclass
class ResearchRunLog:
    task_id: str
    query: str
    provider: str
    start_time: str
    end_time: str | None = None
    result_count: int = 0
    selected_count: int = 0
    source_count: int = 0
    claim_count: int = 0
    error_count: int = 0
    duration_ms: float | None = None
    status: str = "OK"
    errors: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: f"RRL-{uuid4().hex[:10]}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def infer_priority_class(*, source_type: str, url: str | None = None, title: str | None = None) -> str:
    """Heuristic priority metadata — NOT verification."""
    u = (url or "").lower()
    t = (title or "").lower()
    st = source_type.upper()
    if st in {"REGULATORY", "GUIDELINE"} or any(x in u for x in ("ema.europa", "fda.gov", "who.int", "eec.", "minzdrav")):
        return "OFFICIAL_REGULATORY"
    if st in {"SMPC", "PRODUCT_LABEL"} or "smpc" in t or "prescribing information" in t or "инструкц" in t:
        return "OFFICIAL_PRODUCT"
    if st == "CLINICAL_STUDY" or "clinicaltrials.gov" in u:
        return "CLINICAL_DATABASE"
    if st == "PUBLICATION" or "pubmed" in u or "doi.org" in u:
        return "PEER_REVIEWED"
    if st == "PROTOCOL":
        return "INTERNAL_PROTOCOL"
    if st == "REVIEW":
        return "PUBLICATION"
    return "OTHER"

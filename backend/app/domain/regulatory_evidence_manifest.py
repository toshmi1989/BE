"""RegulatoryEvidenceManifest — Phase 13.1.

Represents real or missing regulatory sources. Does not fabricate documents.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.domain.regulatory_source_classes import (
    SOURCE_CLASSES,
    SOURCE_VERIFICATION_STATUSES,
    is_interview_class,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGULATORY_ROOT = REPO_ROOT / "fixtures" / "regulatory"


@dataclass
class RegulatorySourceEntry:
    source_id: str
    source_class: str
    title: str
    issuing_authority: str | None = None
    document_identifier: str | None = None
    jurisdiction: str | None = None
    publication_date: str | None = None
    effective_date: str | None = None
    language: str | None = None
    file_hash: str | None = None
    source_uri: str | None = None
    relative_path: str | None = None
    source_version: str = "1"
    ingestion_status: str = "MISSING"  # MISSING|PENDING|OK|FAILED
    verification_status: str = "UNVERIFIED"
    knowledge_gap_code: str | None = None
    notes: str | None = None
    superseded_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RegulatoryEvidenceManifest:
    manifest_id: str
    package_status: str  # REAL | PARTIAL | MISSING
    sources: list[RegulatorySourceEntry] = field(default_factory=list)
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    interview_claims_path: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "package_status": self.package_status,
            "sources": [s.to_dict() for s in self.sources],
            "knowledge_gaps": list(self.knowledge_gaps),
            "interview_claims_path": self.interview_claims_path,
            "notes": self.notes,
        }

    def by_class(self, source_class: str) -> list[RegulatorySourceEntry]:
        return [s for s in self.sources if s.source_class == source_class]

    def missing_sources(self) -> list[RegulatorySourceEntry]:
        return [s for s in self.sources if s.ingestion_status == "MISSING"]

    def present_sources(self) -> list[RegulatorySourceEntry]:
        return [s for s in self.sources if s.ingestion_status == "OK"]

    def present_regulatory_sources(self) -> list[RegulatorySourceEntry]:
        """Official/regulatory documents only — excludes EXPERT_INTERVIEW."""
        from app.domain.regulatory_source_classes import is_interview_class

        return [
            s
            for s in self.sources
            if s.ingestion_status == "OK" and not is_interview_class(s.source_class)
        ]


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def detect_duplicate_sources(entries: list[RegulatorySourceEntry]) -> list[dict[str, Any]]:
    """Detect duplicates by source_id, document_identifier, or content hash."""
    dups: list[dict[str, Any]] = []
    seen_id: dict[str, str] = {}
    seen_doc: dict[str, str] = {}
    seen_hash: dict[str, str] = {}
    for e in entries:
        if e.source_id in seen_id:
            dups.append(
                {
                    "type": "SOURCE_ID",
                    "source_id": e.source_id,
                    "other_source_id": seen_id[e.source_id],
                }
            )
        else:
            seen_id[e.source_id] = e.source_id
        if e.document_identifier:
            key = e.document_identifier.strip().lower()
            if key in seen_doc:
                dups.append(
                    {
                        "type": "DOCUMENT_IDENTIFIER",
                        "source_id": e.source_id,
                        "other_source_id": seen_doc[key],
                        "document_identifier": e.document_identifier,
                    }
                )
            else:
                seen_doc[key] = e.source_id
        if e.file_hash:
            if e.file_hash in seen_hash:
                dups.append(
                    {
                        "type": "CONTENT_HASH",
                        "source_id": e.source_id,
                        "other_source_id": seen_hash[e.file_hash],
                        "file_hash": e.file_hash,
                    }
                )
            else:
                seen_hash[e.file_hash] = e.source_id
    return dups


def _entry_from_dict(d: dict) -> RegulatorySourceEntry:
    sc = str(d.get("source_class") or "OTHER")
    if sc not in SOURCE_CLASSES:
        sc = "OTHER"
    vs = str(d.get("verification_status") or "UNVERIFIED")
    if vs not in SOURCE_VERIFICATION_STATUSES:
        vs = "UNVERIFIED"
    # Never auto-verify from JSON alone for regulatory docs
    if vs == "VERIFIED" and not is_interview_class(sc):
        # Allow explicit VERIFIED only if flag set — default force REVIEW_REQUIRED
        if not d.get("explicitly_verified"):
            vs = "REVIEW_REQUIRED" if d.get("ingestion_status") == "OK" else "UNVERIFIED"
    return RegulatorySourceEntry(
        source_id=str(d["source_id"]),
        source_class=sc,
        title=str(d.get("title") or d["source_id"]),
        issuing_authority=d.get("issuing_authority"),
        document_identifier=d.get("document_identifier"),
        jurisdiction=d.get("jurisdiction"),
        publication_date=d.get("publication_date"),
        effective_date=d.get("effective_date"),
        language=d.get("language"),
        file_hash=d.get("file_hash"),
        source_uri=d.get("source_uri"),
        relative_path=d.get("relative_path"),
        source_version=str(d.get("source_version") or "1"),
        ingestion_status=str(d.get("ingestion_status") or "MISSING"),
        verification_status=vs,
        knowledge_gap_code=d.get("knowledge_gap_code"),
        notes=d.get("notes"),
        superseded_by=d.get("superseded_by"),
    )


def refresh_file_status(entry: RegulatorySourceEntry, root: Path) -> RegulatorySourceEntry:
    """Update hash/ingestion from disk. Does NOT set VERIFIED."""
    if not entry.relative_path:
        entry.ingestion_status = "MISSING"
        return entry
    path = root / entry.relative_path
    if not path.is_file() or path.stat().st_size == 0:
        entry.ingestion_status = "MISSING"
        entry.file_hash = None
        if entry.verification_status == "VERIFIED":
            # Missing file cannot remain verified without explicit re-review — mark superseded path
            entry.verification_status = "UNVERIFIED"
        return entry
    entry.file_hash = file_sha256(path)
    entry.ingestion_status = "OK"
    if entry.verification_status == "UNVERIFIED":
        entry.verification_status = "EXTRACTED"
    return entry


def load_regulatory_manifest(root: Path | None = None) -> RegulatoryEvidenceManifest:
    base = Path(root) if root else DEFAULT_REGULATORY_ROOT
    path = base / "manifest.json"
    if not path.is_file():
        return RegulatoryEvidenceManifest(
            manifest_id="regulatory-missing",
            package_status="MISSING",
            knowledge_gaps=[
                {
                    "code": "REG.PACKAGE.MISSING",
                    "domain": "REGULATORY",
                    "question": "Regulatory evidence package not found",
                    "blocking": True,
                }
            ],
            notes="fixtures/regulatory/manifest.json missing",
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    sources = [_entry_from_dict(s) for s in (raw.get("sources") or [])]
    for s in sources:
        refresh_file_status(s, base)
    present = sum(1 for s in sources if s.ingestion_status == "OK" and not is_interview_class(s.source_class))
    missing_reg = sum(
        1
        for s in sources
        if s.ingestion_status == "MISSING"
        and s.source_class not in {"EXPERT_INTERVIEW", "OTHER"}
    )
    has_interview_ok = any(
        s.ingestion_status == "OK" and is_interview_class(s.source_class) for s in sources
    )
    if present > 0 and missing_reg == 0:
        status = "REAL"
    elif present > 0 and missing_reg > 0:
        status = "PARTIAL"
    elif has_interview_ok or (base / "manifest.json").is_file():
        # Structure + interview and/or declared missing official docs → PARTIAL (not fabricated REAL)
        status = "PARTIAL" if (has_interview_ok or missing_reg > 0) else "MISSING"
    else:
        status = str(raw.get("package_status") or "MISSING")

    gaps = list(raw.get("knowledge_gaps") or [])
    for s in sources:
        if s.ingestion_status == "MISSING" and s.knowledge_gap_code:
            gaps.append(
                {
                    "code": s.knowledge_gap_code,
                    "domain": s.source_class,
                    "question": f"Missing regulatory source: {s.title}",
                    "source_id": s.source_id,
                    "blocking": True,
                    "document_identifier": s.document_identifier,
                }
            )
    # Dedup gaps by code
    seen: set[str] = set()
    uniq_gaps: list[dict[str, Any]] = []
    for g in gaps:
        c = str(g.get("code") or "")
        if c in seen:
            continue
        seen.add(c)
        uniq_gaps.append(g)

    return RegulatoryEvidenceManifest(
        manifest_id=str(raw.get("manifest_id") or "regulatory-pack"),
        package_status=status,
        sources=sources,
        knowledge_gaps=uniq_gaps,
        interview_claims_path=raw.get("interview_claims_path"),
        notes=raw.get("notes"),
    )


def supersede_source(
    entries: list[RegulatorySourceEntry],
    *,
    old_source_id: str,
    new_entry: RegulatorySourceEntry,
) -> list[RegulatorySourceEntry]:
    """Versioning: mark old SUPERSEDED; append new version. Does not mutate historical claims."""
    out: list[RegulatorySourceEntry] = []
    for e in entries:
        if e.source_id == old_source_id:
            e.verification_status = "SUPERSEDED"
            e.superseded_by = new_entry.source_id
        out.append(e)
    out.append(new_entry)
    return out

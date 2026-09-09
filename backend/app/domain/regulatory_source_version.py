"""SourceVersion registry & import store — Phase 13.2.

Filesystem store under fixtures/regulatory/_imported/.
Never auto-verifies. Does not invent official documents.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.document_ingest import (
    extract_document,
    safe_filename,
    sha256_hex,
    validate_upload,
)
from app.domain.exceptions import ValidationError
from app.domain.regulatory_evidence_manifest import DEFAULT_REGULATORY_ROOT
from app.domain.regulatory_source_classes import SOURCE_CLASSES, SOURCE_VERIFICATION_STATUSES


IMPORTED_DIR_NAME = "_imported"
REGISTRY_FILENAME = "registry.json"
EXTRACTION_VERSION = "DOC.EXTRACT.v1"


@dataclass
class SourceVersion:
    source_id: str
    version_id: str
    filename: str
    content_hash: str
    file_size: int
    mime_type: str | None
    source_class: str
    title: str
    document_identifier: str | None = None
    issuing_authority: str | None = None
    publication_date: str | None = None
    effective_date: str | None = None
    superseded_date: str | None = None
    retrieval_date: str | None = None
    jurisdiction: str | None = None
    language: str | None = None
    source_url: str | None = None
    relative_path: str | None = None
    ingestion_status: str = "PENDING"  # PENDING|OK|FAILED|EXISTING_SOURCE_VERSION
    verification_status: str = "UNVERIFIED"
    is_current: bool = True
    superseded_by: str | None = None
    technical_fixture: bool = False
    project_id: str | None = None
    pages_total: int = 0
    pages_extracted: int = 0
    empty_pages: int = 0
    failed_pages: int = 0
    text_length: int = 0
    extraction_quality: str = "UNKNOWN"  # GOOD|FAIR|POOR|FAILED|UNKNOWN
    extraction_version: str = EXTRACTION_VERSION
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImportResult:
    status: str  # IMPORTED | EXISTING_SOURCE_VERSION | VERSION_CONFLICT | FAILED
    source_version: SourceVersion | None = None
    existing_version_id: str | None = None
    conflict: dict[str, Any] | None = None
    pages: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    study_mutated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_version": self.source_version.to_dict() if self.source_version else None,
            "existing_version_id": self.existing_version_id,
            "conflict": self.conflict,
            "pages": self.pages,
            "chunks": self.chunks,
            "study_mutated": self.study_mutated,
        }


def imported_root(base: Path | None = None) -> Path:
    root = Path(base) if base else DEFAULT_REGULATORY_ROOT
    path = root / IMPORTED_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def registry_path(base: Path | None = None) -> Path:
    return imported_root(base) / REGISTRY_FILENAME


def load_registry(base: Path | None = None) -> dict[str, Any]:
    path = registry_path(base)
    if not path.is_file():
        return {"versions": [], "updated_at": None}
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(data: dict[str, Any], base: Path | None = None) -> None:
    path = registry_path(base)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_source_versions(base: Path | None = None, *, project_id: str | None = None) -> list[SourceVersion]:
    reg = load_registry(base)
    out: list[SourceVersion] = []
    for raw in reg.get("versions") or []:
        if project_id is not None:
            pid = raw.get("project_id")
            if pid is not None and pid != project_id:
                continue
        out.append(_version_from_dict(raw))
    return out


def get_source_version(version_id: str, base: Path | None = None) -> SourceVersion | None:
    for v in list_source_versions(base):
        if v.version_id == version_id:
            return v
    return None


def get_source_versions_by_source(source_id: str, base: Path | None = None) -> list[SourceVersion]:
    return [v for v in list_source_versions(base) if v.source_id == source_id]


def _version_from_dict(d: dict) -> SourceVersion:
    vs = str(d.get("verification_status") or "UNVERIFIED")
    if vs == "VERIFIED":
        # Registry must never auto-persist VERIFIED without explicit workflow flag
        if not d.get("explicitly_verified"):
            vs = "REVIEW_REQUIRED"
    sc = str(d.get("source_class") or "OTHER")
    if sc not in SOURCE_CLASSES:
        sc = "OTHER"
    return SourceVersion(
        source_id=str(d["source_id"]),
        version_id=str(d["version_id"]),
        filename=str(d.get("filename") or ""),
        content_hash=str(d.get("content_hash") or ""),
        file_size=int(d.get("file_size") or 0),
        mime_type=d.get("mime_type"),
        source_class=sc,
        title=str(d.get("title") or d.get("filename") or d["source_id"]),
        document_identifier=d.get("document_identifier"),
        issuing_authority=d.get("issuing_authority"),
        publication_date=d.get("publication_date"),
        effective_date=d.get("effective_date"),
        superseded_date=d.get("superseded_date"),
        retrieval_date=d.get("retrieval_date"),
        jurisdiction=d.get("jurisdiction"),
        language=d.get("language"),
        source_url=d.get("source_url"),
        relative_path=d.get("relative_path"),
        ingestion_status=str(d.get("ingestion_status") or "PENDING"),
        verification_status=vs if vs in SOURCE_VERIFICATION_STATUSES else "UNVERIFIED",
        is_current=bool(d.get("is_current", True)),
        superseded_by=d.get("superseded_by"),
        technical_fixture=bool(d.get("technical_fixture", False)),
        project_id=d.get("project_id"),
        pages_total=int(d.get("pages_total") or 0),
        pages_extracted=int(d.get("pages_extracted") or 0),
        empty_pages=int(d.get("empty_pages") or 0),
        failed_pages=int(d.get("failed_pages") or 0),
        text_length=int(d.get("text_length") or 0),
        extraction_quality=str(d.get("extraction_quality") or "UNKNOWN"),
        extraction_version=str(d.get("extraction_version") or EXTRACTION_VERSION),
        warnings=list(d.get("warnings") or []),
    )


def _assess_quality(pages: list, warnings: list[str]) -> tuple[str, int, int, int, int]:
    total = len(pages)
    empty = 0
    extracted = 0
    text_len = 0
    for p in pages:
        text = getattr(p, "text", None) or (p.get("text") if isinstance(p, dict) else "") or ""
        text = str(text)
        text_len += len(text)
        if text.strip():
            extracted += 1
        else:
            empty += 1
    failed = 0
    if total == 0:
        return "FAILED", 0, 0, 0, 0
    if extracted == 0:
        quality = "FAILED"
    elif empty / total > 0.5 or text_len < 40:
        quality = "POOR"
    elif empty > 0 or warnings:
        quality = "FAIR"
    else:
        quality = "GOOD"
    return quality, total, extracted, empty, text_len


def import_regulatory_file(
    *,
    content: bytes,
    filename: str,
    source_id: str,
    source_class: str,
    title: str | None = None,
    document_identifier: str | None = None,
    issuing_authority: str | None = None,
    jurisdiction: str | None = None,
    language: str | None = None,
    mime_type: str | None = None,
    technical_fixture: bool = False,
    project_id: str | None = None,
    source_url: str | None = None,
    base: Path | None = None,
) -> ImportResult:
    """Import bytes into immutable source version store. Never sets VERIFIED."""
    try:
        safe = validate_upload(
            filename=filename,
            mime_type=mime_type or "application/octet-stream",
            size=len(content),
            content=content,
        )
    except ValidationError as exc:
        return ImportResult(
            status="FAILED",
            conflict={"error": str(exc), "field": getattr(exc, "field", None)},
        )

    if source_class not in SOURCE_CLASSES:
        source_class = "OTHER"

    digest = sha256_hex(content)
    existing = list_source_versions(base, project_id=project_id)
    for v in existing:
        if v.content_hash == digest:
            return ImportResult(
                status="EXISTING_SOURCE_VERSION",
                source_version=v,
                existing_version_id=v.version_id,
                study_mutated=False,
            )

    # Same document_identifier + different hash → version conflict / new version
    conflict_meta = None
    prior_same_id = [
        v
        for v in existing
        if document_identifier
        and v.document_identifier
        and v.document_identifier == document_identifier
        and v.is_current
    ]

    retrieval = datetime.now(timezone.utc).isoformat()
    version_id = f"SV-{digest[:12]}"
    store = imported_root(base) / source_id
    store.mkdir(parents=True, exist_ok=True)
    dest_name = f"{version_id}_{safe}"
    dest = store / dest_name
    dest.write_bytes(content)

    pages_out: list[dict[str, Any]] = []
    chunks_out: list[dict[str, Any]] = []
    warnings: list[str] = []
    ingestion_status = "OK"
    verification_status = "EXTRACTED"

    try:
        extracted = extract_document(filename=safe, content=content)
        warnings = list(extracted.warnings or [])
        quality, total, n_ext, empty, text_len = _assess_quality(extracted.pages, warnings)
        for p in extracted.pages:
            # Human-facing page numbers are already 1-based in extractor
            page_no = int(p.page_number)
            pages_out.append({"page_number": page_no, "text": p.text})
        for c in extracted.chunks:
            chunks_out.append(
                {
                    "page_number": int(c.page_number),
                    "chunk_index": int(c.chunk_index),
                    "text": c.text,
                    "start_offset": c.start_offset,
                    "end_offset": c.end_offset,
                }
            )
        if quality in {"FAILED", "POOR"}:
            verification_status = "REVIEW_REQUIRED"
            if quality == "FAILED":
                ingestion_status = "FAILED"
                warnings.append("EXTRACTION_FAILED: no meaningful text")
    except Exception as exc:  # noqa: BLE001
        quality, total, n_ext, empty, text_len = "FAILED", 0, 0, 0, 0
        ingestion_status = "FAILED"
        verification_status = "REVIEW_REQUIRED"
        warnings.append(f"EXTRACTION_FAILED: {exc}")

    # Relative path from regulatory root
    root = Path(base) if base else DEFAULT_REGULATORY_ROOT
    try:
        rel = str(dest.relative_to(root)).replace("\\", "/")
    except ValueError:
        rel = str(dest)

    new_v = SourceVersion(
        source_id=source_id,
        version_id=version_id,
        filename=safe,
        content_hash=digest,
        file_size=len(content),
        mime_type=mime_type,
        source_class=source_class,
        title=title or safe,
        document_identifier=document_identifier,
        issuing_authority=issuing_authority,
        retrieval_date=retrieval,
        jurisdiction=jurisdiction,
        language=language,
        source_url=source_url,
        relative_path=rel,
        ingestion_status=ingestion_status,
        verification_status=verification_status,
        is_current=True,
        technical_fixture=technical_fixture,
        project_id=project_id,
        pages_total=total,
        pages_extracted=n_ext,
        empty_pages=empty,
        failed_pages=0 if quality != "FAILED" else total,
        text_length=text_len,
        extraction_quality=quality,
        warnings=warnings,
    )

    reg = load_registry(base)
    versions = list(reg.get("versions") or [])
    if prior_same_id:
        conflict_meta = {
            "type": "VERSION_CONFLICT",
            "document_identifier": document_identifier,
            "previous_version_ids": [v.version_id for v in prior_same_id],
            "previous_hashes": [v.content_hash for v in prior_same_id],
            "new_hash": digest,
        }
        # Supersede prior current versions for same identifier
        for i, raw in enumerate(versions):
            if raw.get("version_id") in {v.version_id for v in prior_same_id}:
                raw["is_current"] = False
                raw["verification_status"] = "SUPERSEDED"
                raw["superseded_by"] = version_id
                raw["superseded_date"] = retrieval
                versions[i] = raw
        status = "VERSION_CONFLICT"
    else:
        status = "IMPORTED"

    versions.append(new_v.to_dict())
    reg["versions"] = versions
    save_registry(reg, base)

    return ImportResult(
        status=status,
        source_version=new_v,
        conflict=conflict_meta,
        pages=pages_out,
        chunks=chunks_out,
        study_mutated=False,
    )


def copy_fixture_into_import(
    *,
    fixture_path: Path,
    source_id: str,
    source_class: str = "OTHER",
    technical_fixture: bool = True,
    document_identifier: str | None = None,
    project_id: str | None = None,
    base: Path | None = None,
) -> ImportResult:
    """Import an on-disk technical fixture file (must already exist)."""
    if not fixture_path.is_file():
        return ImportResult(status="FAILED", conflict={"error": "MISSING_FILE", "path": str(fixture_path)})
    return import_regulatory_file(
        content=fixture_path.read_bytes(),
        filename=fixture_path.name,
        source_id=source_id,
        source_class=source_class,
        title=fixture_path.stem,
        document_identifier=document_identifier or f"TECH-{fixture_path.stem}",
        technical_fixture=technical_fixture,
        project_id=project_id,
        mime_type="text/plain" if fixture_path.suffix.lower() == ".txt" else None,
        base=base,
    )

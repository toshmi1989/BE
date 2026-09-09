"""Phase 17 — Safe persistent study document storage."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.exceptions import ValidationError
from app.models.workspace_persistence import WorkspaceDocumentRecord

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_ALLOWED_EXT = {".docx", ".pdf", ".txt", ".mhtml", ".html", ".htm"}


def _root() -> Path:
    settings = get_settings()
    root = Path(settings.document_storage_root).resolve() / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(name: str) -> str:
    base = Path(name).name  # strip path traversal
    if ".." in base or "/" in base or "\\" in base:
        raise ValidationError("Unsafe filename", field="filename")
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "upload"
    return cleaned[:180]


def store_study_document(
    db: Session,
    *,
    study_key: str,
    filename: str,
    content: bytes,
    document_type: str = "OTHER",
    mime_type: str | None = None,
    uploaded_by: str | None = None,
    organization_id: UUID | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if len(content) > settings.max_upload_bytes:
        raise ValidationError("File too large", field="size")
    if len(content) == 0:
        raise ValidationError("Empty file", field="size")
    original = Path(filename).name
    ext = Path(original).suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise ValidationError(f"Unsupported extension: {ext}", field="filename")
    if ".." in filename or filename.startswith("/") or "\\" in filename.replace("/", ""):
        # reject path traversal attempts in original name
        if ".." in filename or filename.startswith(("/", "\\")) or ":\\" in filename:
            raise ValidationError("Path traversal denied", field="filename")

    digest = hashlib.sha256(content).hexdigest()
    # Idempotent: same study + hash → return existing
    existing = db.execute(
        select(WorkspaceDocumentRecord).where(
            WorkspaceDocumentRecord.study_key == study_key,
            WorkspaceDocumentRecord.content_hash == digest,
        )
    ).scalar_one_or_none()
    if existing:
        return _ser(existing)

    doc_id = f"WDOC-{uuid4().hex[:12]}"
    safe = f"{doc_id}_{_safe_filename(original)}"
    org_part = str(organization_id or "public")
    rel = f"{org_part}/{study_key}/{safe}"
    dest_dir = _root() / org_part / study_key
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / safe
    # Ensure resolved path stays under root
    if not str(dest.resolve()).startswith(str(_root())):
        raise ValidationError("Path traversal denied", field="storage")
    dest.write_bytes(content)

    row = WorkspaceDocumentRecord(
        document_id=doc_id,
        study_key=study_key,
        organization_id=organization_id,
        filename=original,
        safe_storage_name=safe,
        document_type=document_type.upper(),
        mime_type=mime_type,
        size=len(content),
        content_hash=digest,
        uploaded_by=uploaded_by,
        uploaded_at=datetime.now(timezone.utc),
        ingestion_status="UPLOADED",
        classification_status="PENDING",
        extraction_status="PENDING",
        storage_key=rel,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _ser(row)


def list_study_documents(db: Session, study_key: str) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(WorkspaceDocumentRecord)
            .where(WorkspaceDocumentRecord.study_key == study_key)
            .order_by(WorkspaceDocumentRecord.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_ser(r) for r in rows]


def update_document_classification(
    db: Session,
    *,
    study_key: str,
    document_id: str,
    document_type: str,
    actor: str = "writer",
) -> dict[str, Any]:
    """Correct document classification — does not invent types or mutate Study SoT."""
    allowed = {"CHECKLIST", "SYNOPSIS", "SMPC", "OTHER", "DESIGN", "SYNOPSIS_DESIGN"}
    dtype = (document_type or "OTHER").strip().upper()
    if dtype not in allowed:
        raise ValidationError(f"Unsupported document_type: {dtype}", field="document_type")
    row = db.execute(
        select(WorkspaceDocumentRecord).where(
            WorkspaceDocumentRecord.study_key == study_key,
            WorkspaceDocumentRecord.document_id == document_id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValidationError("Document not found", field="document_id")
    old = row.document_type
    row.document_type = dtype
    row.classification_status = "CLASSIFIED"
    db.commit()
    db.refresh(row)
    out = _ser(row)
    out["previous_type"] = old
    out["classified_by"] = actor
    return out


def document_ui_status(row: WorkspaceDocumentRecord) -> str:
    """Writer-facing status — not an internal pipeline enum dump."""
    statuses = [
        str(row.ingestion_status or "").upper(),
        str(row.classification_status or "").upper(),
        str(row.extraction_status or "").upper(),
    ]
    if any("ERROR" in s or "FAIL" in s for s in statuses):
        return "ERROR"
    if any("REVIEW" in s for s in statuses):
        return "REVIEW_REQUIRED"
    if all(s in {"READY", "COMPLETE", "DONE", "CLASSIFIED", "EXTRACTED"} for s in statuses if s):
        return "READY"
    if any(s in {"PENDING", "PROCESSING", "RUNNING", "IN_PROGRESS"} for s in statuses):
        if statuses[0] == "UPLOADED" and statuses[1] == "PENDING" and statuses[2] == "PENDING":
            return "UPLOADED"
        return "PROCESSING"
    if statuses[0] == "UPLOADED":
        return "UPLOADED"
    return statuses[0] or "UPLOADED"


def _ser(row: WorkspaceDocumentRecord) -> dict[str, Any]:
    return {
        "document_id": row.document_id,
        "study_id": row.study_key,
        "filename": row.filename,
        "document_type": row.document_type,
        "type": row.document_type,
        "mime_type": row.mime_type,
        "size": row.size,
        "hash": row.content_hash,
        "source_hash": row.content_hash,
        "version": row.version,
        "uploaded_by": row.uploaded_by,
        "uploaded_at": row.uploaded_at.isoformat() if row.uploaded_at else None,
        "ingestion_status": row.ingestion_status,
        "classification_status": row.classification_status,
        "extraction_status": row.extraction_status,
        "ingestion": row.ingestion_status,
        "classification": row.classification_status,
        "extraction": row.extraction_status,
        "status": document_ui_status(row),
        "storage_key": row.storage_key,
        "safe_storage_name": row.safe_storage_name,
    }

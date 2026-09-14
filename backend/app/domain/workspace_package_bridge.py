"""Bridge Workspace document uploads → Study Input Package for analyze workflow.

Writers upload via `/studies/{id}/documents/upload` (WorkspaceDocumentRecord).
Analyze / Decision Center still consume StudyInputPackage. Without this bridge,
UI shows Checklist/Synopsis/SmPC as PRESENT while workflow raises
"Нет загруженного пакета документов".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.domain.exceptions import ValidationError
from app.domain.study_input_pipeline import (
    attach_document,
    create_package,
    run_extraction,
)
from app.domain.study_input_store import list_packages, put_package
from app.domain.workspace_documents import list_study_documents


def _storage_root() -> Path:
    from app.domain.workspace_documents import _root

    return _root()


def _map_document_type(raw: str | None) -> str:
    dtype = (raw or "OTHER").strip().upper()
    if dtype in {"SYNOPSIS_DESIGN", "DESIGN_SYNOPSIS"}:
        return "SYNOPSIS"
    if dtype == "DESIGN":
        return "DESIGN"
    if dtype in {"CHECKLIST", "SYNOPSIS", "SMPC", "OTHER"}:
        return dtype
    return "OTHER"


def _absolute_path(storage_key: str | None) -> Path | None:
    if not storage_key:
        return None
    path = (_storage_root() / storage_key).resolve()
    root = _storage_root()
    if not str(path).startswith(str(root)):
        return None
    if not path.is_file():
        return None
    return path


def _existing_package_for_study(study_key: str):
    for p in list_packages():
        if getattr(p, "study_id", None) == study_key:
            return p
    return None


def ensure_package_from_workspace_documents(
    db: Session,
    study_key: str,
    *,
    force_rebuild: bool = False,
) -> Any | None:
    """Build or refresh StudyInputPackage from persisted workspace uploads.

    Returns the package, or None when there are no workspace documents.
    Does not invent medical content — only ingests bytes already on disk.
    """
    docs = list_study_documents(db, study_key)
    if not docs:
        return None

    existing = _existing_package_for_study(study_key)
    if existing is not None and existing.documents and not force_rebuild:
        # Already have a package for this study — keep expert-reviewed state
        return existing

    pkg = create_package(
        package_id=(existing.package_id if existing else None) or f"SIP-WS-{uuid4().hex[:10]}",
        study_id=study_key,
        fixture_id=None,
    )
    attached = 0
    missing_files: list[str] = []
    for meta in docs:
        path = _absolute_path(str(meta.get("storage_key") or ""))
        if path is None:
            missing_files.append(str(meta.get("filename") or meta.get("document_id") or "?"))
            continue
        dtype = _map_document_type(str(meta.get("document_type") or meta.get("type") or ""))
        attach_document(
            pkg,
            path=path,
            document_type=dtype,
            user_selected=True,
            source_id=str(meta.get("document_id") or ""),
        )
        attached += 1

    if attached == 0:
        raise ValidationError(
            "Файлы отмечены как загруженные, но содержимое недоступно на диске — "
            "загрузите документы снова",
            field="documents",
            details={"missing_files": missing_files},
        )

    run_extraction(pkg, replace=True)
    put_package(pkg)

    # Mark workspace rows as extracted when ingest succeeded
    from app.models.workspace_persistence import WorkspaceDocumentRecord
    from sqlalchemy import select

    rows = (
        db.execute(
            select(WorkspaceDocumentRecord).where(WorkspaceDocumentRecord.study_key == study_key)
        )
        .scalars()
        .all()
    )
    by_hash = {d.content_hash: d for d in pkg.documents if d.content_hash}
    for row in rows:
        matched = by_hash.get(row.content_hash)
        if matched is None:
            continue
        row.ingestion_status = matched.ingestion_status or row.ingestion_status
        row.classification_status = "CLASSIFIED"
        if matched.ingestion_status in {"SUCCESS", "PARTIAL", "OK"}:
            row.extraction_status = "EXTRACTED"
        elif matched.ingestion_status == "FAILED":
            row.extraction_status = "ERROR"
    db.commit()

    return pkg

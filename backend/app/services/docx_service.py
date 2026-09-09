"""DOCX generation service — orchestrates ProtocolDraft → Renderer → GeneratedDocument."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.domain.docx_profile import DOCX_GENERATOR_VERSION, PROFILE_VERSION, TEMPLATE_VERSION, get_template_profile
from app.domain.docx_renderer import render_protocol_docx
from app.domain.exceptions import NotFoundError, ValidationError
from app.models import Project
from app.models.generated_document import GeneratedDocument
from app.models.protocol import ProtocolDraft
from app.schemas.phase9 import DocxBuildRequest, DocxStatusOut, DocxValidationOut, GeneratedDocumentOut
from app.services import protocol_service as protocol
from app.services import validation_service as validation


def _generated_root() -> Path:
    settings = get_settings()
    # Prefer dedicated generated/ under backend, gitignored
    root = Path(__file__).resolve().parents[2] / "generated"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _project_out_dir(project_id: UUID) -> Path:
    path = _generated_root() / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _serialize(row: GeneratedDocument) -> GeneratedDocumentOut:
    return GeneratedDocumentOut.model_validate(row)


def _latest(db: Session, project_id: UUID) -> GeneratedDocument | None:
    return (
        db.execute(
            select(GeneratedDocument)
            .where(GeneratedDocument.project_id == project_id)
            .order_by(GeneratedDocument.created_at.desc())
        )
        .scalars()
        .first()
    )


def _draft_to_payload(draft: ProtocolDraft) -> dict:
    return {
        "status": draft.status,
        "protocol_version": draft.protocol_version,
        "template_version": draft.template_version,
        "rules_version": draft.rules_version,
        "generator_version": draft.generator_version,
        "consistency_snapshot": draft.consistency_snapshot or {},
        "canonical_fingerprint": draft.canonical_fingerprint,
        "sections": [
            {
                "section_code": s.section_code,
                "title": s.title,
                "order": s.order,
                "parent_section": s.parent_section,
                "status": s.status,
                "generation_status": s.generation_status,
                "content_blocks": s.content_blocks or [],
                "source_ids": s.source_ids or [],
                "warnings": s.warnings or [],
                "template_key": s.template_key,
            }
            for s in draft.sections
        ],
        "tables": [
            {
                "table_key": t.table_key,
                "section_code": t.section_code,
                "title": t.title,
                "order": t.order,
                "columns": t.columns or [],
                "rows": t.rows or [],
                "source_ids": t.source_ids or [],
                "status": t.status,
                "display_number": t.display_number,
            }
            for t in draft.tables
        ],
        "references": [
            {
                "source_section": r.source_section,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "display_text": r.display_text,
            }
            for r in draft.references
        ],
        "build_report": (
            {
                "generated_sections": draft.build_report.generated_sections,
                "unresolved_fields": draft.build_report.unresolved_fields,
                "blocking_issues": draft.build_report.blocking_issues,
                "warnings": draft.build_report.warnings,
                "source_count": draft.build_report.source_count,
                "calculated_values": draft.build_report.calculated_values,
                "expert_verified_values": draft.build_report.expert_verified_values,
            }
            if draft.build_report
            else {}
        ),
    }


def build_docx(db: Session, project_id: UUID, payload: DocxBuildRequest | None = None) -> GeneratedDocumentOut:
    body = payload or DocxBuildRequest()
    mode = body.mode.upper()
    if mode not in {"DRAFT", "REVIEW", "FINAL"}:
        raise ValidationError("mode must be DRAFT|REVIEW|FINAL", field="mode")

    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", field="project_id")

    row = GeneratedDocument(
        project_id=project_id,
        mode=mode,
        status="BUILDING",
        blocking_reasons=[],
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        if body.ensure_protocol:
            try:
                protocol.get_protocol(db, project_id)
            except NotFoundError:
                protocol.build_protocol(db, project_id)

        draft = (
            db.execute(
                select(ProtocolDraft)
                .where(ProtocolDraft.project_id == project_id)
                .options(
                    selectinload(ProtocolDraft.sections),
                    selectinload(ProtocolDraft.tables),
                    selectinload(ProtocolDraft.references),
                    selectinload(ProtocolDraft.build_report),
                )
                .order_by(ProtocolDraft.created_at.desc())
            )
            .scalars()
            .first()
        )
        if draft is None:
            raise ValidationError("ProtocolDraft required before DOCX", field="protocol")

        ctx = validation.build_project_context(db, project_id)

        payload_dict = _draft_to_payload(draft)
        slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (project.name or "project"))[:40]
        result = render_protocol_docx(
            protocol_payload=payload_dict,
            study_ctx=ctx,
            mode=mode,
            output_dir=_project_out_dir(project_id),
            project_slug=slug or "project",
            protocol_version=draft.protocol_version,
            only_sections=set(body.only_sections) if body.only_sections else None,
        )

        row.protocol_draft_id = draft.id
        row.template_version = result.template_version
        row.protocol_version = draft.protocol_version
        row.generator_version = result.generator_version
        row.profile_version = result.profile_version
        row.blocking_reasons = list(result.blocking_reasons)
        row.table_numbers = result.table_numbers
        row.built_at = datetime.now(timezone.utc)

        if result.status == "BLOCKED":
            row.status = "BLOCKED"
            row.validation_report = result.validation.to_dict() if result.validation else None
            row.error = "; ".join(result.blocking_reasons)[:2000] if result.blocking_reasons else "blocked"
        elif result.status == "FAILED":
            row.status = "FAILED"
            row.error = "; ".join(result.blocking_reasons)[:2000]
        else:
            row.status = "READY"
            row.filename = result.filename
            # opaque storage key — not absolute filesystem path
            row.storage_key = f"{project_id}/{result.filename}"
            row.checksum = result.checksum
            row.validation_report = result.validation.to_dict() if result.validation else None

        db.commit()
        db.refresh(row)
        return _serialize(row)
    except Exception as exc:  # noqa: BLE001
        row.status = "FAILED"
        row.error = str(exc)[:2000]
        db.commit()
        db.refresh(row)
        if isinstance(exc, (NotFoundError, ValidationError)):
            raise
        raise ValidationError(str(exc), field="docx") from exc


def get_docx_status(db: Session, project_id: UUID) -> DocxStatusOut:
    if db.get(Project, project_id) is None:
        raise NotFoundError("Project not found", field="project_id")
    profile = get_template_profile()
    latest = _latest(db, project_id)
    return DocxStatusOut(
        latest=_serialize(latest) if latest else None,
        template_version=profile.template_version,
        generator_version=DOCX_GENERATOR_VERSION,
        profile_version=PROFILE_VERSION,
    )


def get_docx_validation(db: Session, project_id: UUID) -> DocxValidationOut:
    latest = _latest(db, project_id)
    if latest is None:
        raise NotFoundError("No generated DOCX", field="document_id")
    return DocxValidationOut(
        document_id=latest.id,
        status=latest.status,
        validation=latest.validation_report or {},
        blocking_reasons=list(latest.blocking_reasons or []),
    )


def resolve_download_path(db: Session, project_id: UUID) -> tuple[Path, str]:
    latest = _latest(db, project_id)
    if latest is None or latest.status != "READY" or not latest.storage_key:
        raise NotFoundError("DOCX not ready for download", field="document_id")
    # storage_key is project_id/filename under generated/
    path = _generated_root() / latest.storage_key
    if not path.exists():
        raise NotFoundError("Generated file missing on disk", field="storage_key")
    # prevent path escape
    try:
        path.resolve().relative_to(_generated_root().resolve())
    except ValueError as exc:
        raise ValidationError("Invalid storage key", field="storage_key") from exc
    return path, latest.filename or path.name

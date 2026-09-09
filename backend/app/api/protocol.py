from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.phase8 import (
    ProtocolBuildReportOut,
    ProtocolBuildRequest,
    ProtocolDraftOut,
    ProtocolPreviewOut,
    ProtocolSectionOut,
)
from app.schemas.phase9 import DocxBuildRequest, DocxStatusOut, DocxValidationOut, GeneratedDocumentOut
from app.services import docx_service as docx
from app.services import protocol_service as protocol

router = APIRouter(tags=["protocol"])


@router.post("/projects/{project_id}/protocol/build", response_model=ProtocolDraftOut)
def build_protocol(
    project_id: UUID,
    payload: ProtocolBuildRequest | None = None,
    db: Session = Depends(get_db),
) -> ProtocolDraftOut:
    body = payload or ProtocolBuildRequest()
    return protocol.build_protocol(db, project_id, protocol_version=body.protocol_version)


@router.get("/projects/{project_id}/protocol", response_model=ProtocolDraftOut)
def get_protocol(project_id: UUID, db: Session = Depends(get_db)) -> ProtocolDraftOut:
    return protocol.get_protocol(db, project_id)


@router.get("/projects/{project_id}/protocol/sections", response_model=list[ProtocolSectionOut])
def list_sections(project_id: UUID, db: Session = Depends(get_db)) -> list[ProtocolSectionOut]:
    return protocol.list_sections(db, project_id)


@router.get("/projects/{project_id}/protocol/build-report", response_model=ProtocolBuildReportOut)
def build_report(project_id: UUID, db: Session = Depends(get_db)) -> ProtocolBuildReportOut:
    return protocol.get_build_report(db, project_id)


@router.get("/projects/{project_id}/protocol/preview", response_model=ProtocolPreviewOut)
def preview(project_id: UUID, db: Session = Depends(get_db)) -> ProtocolPreviewOut:
    return protocol.preview_protocol(db, project_id)


@router.post(
    "/projects/{project_id}/protocol/sections/{section_code}/rebuild",
    response_model=ProtocolDraftOut,
)
def rebuild_section(
    project_id: UUID, section_code: str, db: Session = Depends(get_db)
) -> ProtocolDraftOut:
    return protocol.rebuild_section(db, project_id, section_code)


@router.post("/projects/{project_id}/protocol/docx/build", response_model=GeneratedDocumentOut)
def build_docx(
    project_id: UUID,
    payload: DocxBuildRequest | None = None,
    db: Session = Depends(get_db),
) -> GeneratedDocumentOut:
    return docx.build_docx(db, project_id, payload)


@router.get("/projects/{project_id}/protocol/docx/status", response_model=DocxStatusOut)
def docx_status(project_id: UUID, db: Session = Depends(get_db)) -> DocxStatusOut:
    return docx.get_docx_status(db, project_id)


@router.get("/projects/{project_id}/protocol/docx/validation", response_model=DocxValidationOut)
def docx_validation(project_id: UUID, db: Session = Depends(get_db)) -> DocxValidationOut:
    return docx.get_docx_validation(db, project_id)


@router.get("/projects/{project_id}/protocol/docx/download")
def docx_download(project_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    path, filename = docx.resolve_download_path(db, project_id)
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

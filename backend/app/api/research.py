from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.phase5 import (
    ApplyVerifiedOut,
    ApplyVerifiedRequest,
    EvidenceConflictCreate,
    EvidenceConflictOut,
    EvidenceConflictResolve,
    EvidenceCreate,
    EvidenceOut,
    ResearchCaseCreate,
    ResearchCaseOut,
    ResearchTaskCreate,
    ResearchTaskOut,
)
from app.schemas.phase6 import (
    CompletenessOut,
    DocumentOut,
    DocumentPageOut,
    ManualEvidenceRequest,
    ResearchProfileIn,
    ResearchProfileOut,
    ResearchSearchRequest,
    SearchHitOut,
)
from app.services import document_service as documents
from app.services import research_engine_service as engine
from app.services import research_service as research

router = APIRouter(tags=["research"])


@router.post("/projects/{project_id}/research-case", response_model=ResearchCaseOut, status_code=201)
def create_research_case(
    project_id: UUID, payload: ResearchCaseCreate | None = None, db: Session = Depends(get_db)
) -> ResearchCaseOut:
    return research.ensure_research_case(db, project_id, payload or ResearchCaseCreate())


@router.get("/projects/{project_id}/research-case", response_model=ResearchCaseOut)
def get_research_case(project_id: UUID, db: Session = Depends(get_db)) -> ResearchCaseOut:
    return research.get_research_case(db, project_id)


@router.post("/projects/{project_id}/research-profile", response_model=ResearchProfileOut)
def upsert_research_profile(
    project_id: UUID, payload: ResearchProfileIn, db: Session = Depends(get_db)
) -> ResearchProfileOut:
    return engine.upsert_research_profile(db, project_id, payload)


@router.get("/projects/{project_id}/research-profile", response_model=ResearchProfileOut)
def get_research_profile(project_id: UUID, db: Session = Depends(get_db)) -> ResearchProfileOut:
    return engine.get_research_profile(db, project_id)


@router.post(
    "/projects/{project_id}/research-case/tasks/generate",
    response_model=list[ResearchTaskOut],
)
def generate_tasks(project_id: UUID, db: Session = Depends(get_db)) -> list[ResearchTaskOut]:
    return engine.generate_tasks_for_project(db, project_id)


@router.post(
    "/projects/{project_id}/research-case/tasks",
    response_model=ResearchTaskOut,
    status_code=201,
)
def create_task(
    project_id: UUID, payload: ResearchTaskCreate, db: Session = Depends(get_db)
) -> ResearchTaskOut:
    return research.create_task(db, project_id, payload)


@router.get("/projects/{project_id}/research-case/tasks", response_model=list[ResearchTaskOut])
def list_tasks(project_id: UUID, db: Session = Depends(get_db)) -> list[ResearchTaskOut]:
    return research.list_tasks(db, project_id)


@router.post("/projects/{project_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    project_id: UUID,
    file: UploadFile = File(...),
    source_type: str = Form("OTHER"),
    db: Session = Depends(get_db),
) -> DocumentOut:
    content = await file.read()
    return documents.upload_document(
        db,
        project_id,
        filename=file.filename or "upload.bin",
        content=content,
        mime_type=file.content_type,
        source_type=source_type,
    )


@router.get("/projects/{project_id}/documents", response_model=list[DocumentOut])
def list_documents(project_id: UUID, db: Session = Depends(get_db)) -> list[DocumentOut]:
    return documents.list_documents(db, project_id)


@router.post(
    "/projects/{project_id}/documents/{document_id}/ingest",
    response_model=DocumentOut,
)
def ingest_document(
    project_id: UUID, document_id: UUID, db: Session = Depends(get_db)
) -> DocumentOut:
    return documents.ingest_document(db, project_id, document_id)


@router.get(
    "/projects/{project_id}/documents/{document_id}/pages",
    response_model=list[DocumentPageOut],
)
def list_pages(
    project_id: UUID, document_id: UUID, db: Session = Depends(get_db)
) -> list[DocumentPageOut]:
    return documents.list_pages(db, project_id, document_id)


@router.post("/projects/{project_id}/research/search", response_model=list[SearchHitOut])
def research_search(
    project_id: UUID, payload: ResearchSearchRequest, db: Session = Depends(get_db)
) -> list[SearchHitOut]:
    return documents.search_project_documents(
        db,
        project_id,
        query=payload.query,
        phrase=payload.phrase,
        source_type=payload.source_type,
        document_id=payload.document_id,
        limit=payload.limit,
    )


@router.post("/projects/{project_id}/research/evidence", response_model=EvidenceOut, status_code=201)
def create_research_evidence(
    project_id: UUID, payload: ManualEvidenceRequest, db: Session = Depends(get_db)
) -> EvidenceOut:
    return engine.create_manual_evidence(db, project_id, payload)


@router.get("/projects/{project_id}/research/evidence", response_model=list[EvidenceOut])
def list_research_evidence(project_id: UUID, db: Session = Depends(get_db)) -> list[EvidenceOut]:
    return research.list_evidence(db, project_id)


# Keep Phase 5 evidence paths
@router.post(
    "/projects/{project_id}/research-case/evidence",
    response_model=EvidenceOut,
    status_code=201,
)
def create_evidence(
    project_id: UUID, payload: EvidenceCreate, db: Session = Depends(get_db)
) -> EvidenceOut:
    return research.create_evidence(db, project_id, payload)


@router.get("/projects/{project_id}/research-case/evidence", response_model=list[EvidenceOut])
def list_evidence(project_id: UUID, db: Session = Depends(get_db)) -> list[EvidenceOut]:
    return research.list_evidence(db, project_id)


@router.post("/projects/{project_id}/research/conflicts", response_model=list[EvidenceConflictOut])
def detect_research_conflicts(
    project_id: UUID, db: Session = Depends(get_db)
) -> list[EvidenceConflictOut]:
    return engine.refresh_conflicts(db, project_id)


@router.post(
    "/projects/{project_id}/research-case/conflicts",
    response_model=EvidenceConflictOut,
    status_code=201,
)
def create_conflict(
    project_id: UUID, payload: EvidenceConflictCreate, db: Session = Depends(get_db)
) -> EvidenceConflictOut:
    return research.create_conflict(db, project_id, payload)


@router.get(
    "/projects/{project_id}/research-case/conflicts",
    response_model=list[EvidenceConflictOut],
)
def list_conflicts(project_id: UUID, db: Session = Depends(get_db)) -> list[EvidenceConflictOut]:
    return research.list_conflicts(db, project_id)


@router.post(
    "/projects/{project_id}/research-case/conflicts/{conflict_id}/resolve",
    response_model=EvidenceConflictOut,
)
def resolve_conflict(
    project_id: UUID,
    conflict_id: UUID,
    payload: EvidenceConflictResolve,
    db: Session = Depends(get_db),
) -> EvidenceConflictOut:
    return research.resolve_conflict(db, project_id, conflict_id, payload)


@router.post("/projects/{project_id}/research/completeness", response_model=CompletenessOut)
def completeness(project_id: UUID, db: Session = Depends(get_db)) -> CompletenessOut:
    return engine.research_completeness(db, project_id)


@router.post(
    "/projects/{project_id}/research-case/apply-verified",
    response_model=ApplyVerifiedOut,
)
def apply_verified(
    project_id: UUID, payload: ApplyVerifiedRequest, db: Session = Depends(get_db)
) -> ApplyVerifiedOut:
    return research.apply_verified(db, project_id, payload)


@router.get("/reference-data/source-ranking")
def source_ranking(db: Session = Depends(get_db)) -> dict:
    return research.get_or_seed_source_ranking(db)


@router.get("/reference-data/evidence-fields")
def evidence_fields(db: Session = Depends(get_db)) -> list[dict]:
    return engine.seed_evidence_field_definitions(db)

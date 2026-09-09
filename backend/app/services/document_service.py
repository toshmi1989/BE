from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.document_ingest import extract_document, sha256_hex, validate_upload
from app.domain.document_search import search_chunks
from app.domain.exceptions import NotFoundError, ValidationError
from app.models import Project, Source
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.schemas.common import ProvenanceIn
from app.schemas.phase6 import DocumentOut, DocumentPageOut, SearchHitOut
from app.services.provenance import apply_provenance
def _project(db: Session, project_id: UUID) -> Project:
    p = db.get(Project, project_id)
    if p is None:
        raise NotFoundError("Project not found", field="project_id")
    return p


def _storage_dir(project_id: UUID) -> Path:
    settings = get_settings()
    root = Path(settings.document_storage_root)
    if not root.is_absolute():
        # relative to backend package parent (repo backend/)
        root = Path(__file__).resolve().parents[2] / root
    path = root / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def serialize_document(row: Document) -> DocumentOut:
    return DocumentOut.model_validate(row)


def upload_document(
    db: Session,
    project_id: UUID,
    *,
    filename: str,
    content: bytes,
    mime_type: str | None,
    source_type: str = "OTHER",
) -> DocumentOut:
    _project(db, project_id)
    settings = get_settings()
    if len(content) > settings.max_upload_bytes:
        raise ValidationError("File too large", field="file")
    safe = validate_upload(
        filename=filename, mime_type=mime_type, size=len(content), content=content
    )
    checksum = sha256_hex(content)

    # dedupe by checksum within project
    existing = db.execute(
        select(Document).where(Document.project_id == project_id, Document.checksum == checksum)
    ).scalar_one_or_none()
    if existing is not None:
        return serialize_document(existing)

    doc_id = uuid4()
    storage = _storage_dir(project_id) / f"{doc_id}_{safe}"
    storage.write_bytes(content)

    source = Source(
        project_id=project_id,
        type=source_type,
        title=safe,
        checksum=checksum,
        file_id=str(doc_id),
    )
    apply_provenance(
        source,
        ProvenanceIn(origin="USER", status="PROPOSED", source_ids=[]),
        creating=True,
    )
    db.add(source)
    db.flush()

    row = Document(
        id=doc_id,
        project_id=project_id,
        source_id=source.id,
        filename=safe,
        mime_type=(mime_type or "application/octet-stream").split(";")[0].strip(),
        size=len(content),
        checksum=checksum,
        storage_path=str(storage),
        status="UPLOADED",
        ingest_warnings=[],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_document(row)


def ingest_document(db: Session, project_id: UUID, document_id: UUID) -> DocumentOut:
    _project(db, project_id)
    row = db.get(Document, document_id)
    if row is None or row.project_id != project_id:
        raise NotFoundError("Document not found", field="document_id")
    path = Path(row.storage_path)
    if not path.exists():
        raise ValidationError("Stored file missing", field="storage_path")
    content = path.read_bytes()
    extracted = extract_document(filename=row.filename, content=content)

    # replace pages/chunks
    for page in list(row.pages or []):
        db.delete(page)
    db.flush()

    page_by_num: dict[int, DocumentPage] = {}
    for p in extracted.pages:
        page = DocumentPage(document_id=row.id, page_number=p.page_number, text=p.text or "")
        db.add(page)
        db.flush()
        page_by_num[p.page_number] = page

    for ch in extracted.chunks:
        page = page_by_num.get(ch.page_number)
        if page is None:
            continue
        db.add(
            DocumentChunk(
                document_page_id=page.id,
                chunk_index=ch.chunk_index,
                text=ch.text,
                start_offset=ch.start_offset,
                end_offset=ch.end_offset,
            )
        )

    row.status = "INGESTED"
    row.ingest_warnings = list(extracted.warnings)
    db.commit()
    db.refresh(row)
    return serialize_document(row)


def list_documents(db: Session, project_id: UUID) -> list[DocumentOut]:
    _project(db, project_id)
    rows = db.execute(select(Document).where(Document.project_id == project_id)).scalars().all()
    return [serialize_document(r) for r in rows]


def list_pages(db: Session, project_id: UUID, document_id: UUID) -> list[DocumentPageOut]:
    _project(db, project_id)
    row = db.get(Document, document_id)
    if row is None or row.project_id != project_id:
        raise NotFoundError("Document not found", field="document_id")
    pages = (
        db.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == document_id)
            .order_by(DocumentPage.page_number)
        )
        .scalars()
        .all()
    )
    return [DocumentPageOut.model_validate(p) for p in pages]


def search_project_documents(
    db: Session,
    project_id: UUID,
    *,
    query: str,
    phrase: bool = False,
    source_type: str | None = None,
    document_id: UUID | None = None,
    limit: int = 50,
) -> list[SearchHitOut]:
    _project(db, project_id)
    if not query or not query.strip():
        raise ValidationError("query required", field="query")

    stmt = (
        select(DocumentChunk, DocumentPage, Document, Source)
        .join(DocumentPage, DocumentChunk.document_page_id == DocumentPage.id)
        .join(Document, DocumentPage.document_id == Document.id)
        .outerjoin(Source, Document.source_id == Source.id)
        .where(Document.project_id == project_id)
    )
    if document_id is not None:
        stmt = stmt.where(Document.id == document_id)

    # Postgres FTS when available
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql" and not phrase:
        from sqlalchemy import func, literal_column, text as sql_text

        # Use plainto_tsquery against generated column if present; fall back to portable search
        try:
            fts_stmt = stmt.where(
                sql_text("document_chunks.text_tsv @@ plainto_tsquery('simple', :q)")
            ).params(q=query)
            rows = db.execute(fts_stmt).all()
            hits = []
            for chunk, page, doc, source in rows:
                hits.append(
                    SearchHitOut(
                        source_id=str(source.id) if source else None,
                        document_id=str(doc.id),
                        page=page.page_number,
                        chunk_id=str(chunk.id),
                        score=1.0,
                        snippet=(chunk.text or "")[:200],
                    )
                )
            return hits[:limit]
        except Exception:  # noqa: BLE001
            pass

    rows = db.execute(stmt).all()
    portable = []
    for chunk, page, doc, source in rows:
        portable.append(
            {
                "chunk_id": str(chunk.id),
                "document_id": str(doc.id),
                "page_number": page.page_number,
                "text": chunk.text,
                "source_id": str(source.id) if source else None,
                "source_type": source.type if source else None,
            }
        )
    return [
        SearchHitOut(**h.to_dict())
        for h in search_chunks(
            portable, query, phrase=phrase, source_type=source_type, limit=limit
        )
    ]

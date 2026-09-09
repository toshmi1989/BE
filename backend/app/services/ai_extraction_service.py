"""Local AI structured evidence extraction — assistive only."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.ai_prompts import SCHEMA_VERSION, get_prompt
from app.domain.ai_provider import get_ai_provider
from app.domain.ai_schemas import ChunkContext
from app.domain.exceptions import NotFoundError, ValidationError
from app.domain.document_search import search_chunks
from app.models import Project, Source
from app.models.ai_run import AIRun
from app.models.documents import Document, DocumentChunk, DocumentPage
from app.models.research import Evidence, EvidenceClaim, ResearchCase
from app.domain.ai_schemas import AIExtractionResult
from app.schemas.phase5 import ApplyVerifiedRequest, EvidenceClaimIn, EvidenceCreate
from app.schemas.phase7 import (
    AIClaimOut,
    AIClaimReviewRequest,
    AIExtractRequest,
    AIExtractResponse,
    AIRunOut,
    AIStatusOut,
)
from app.services import research_engine_service as engine
from app.services import research_service as foundation


TASK_PROMPT_MAP = {
    "EXTRACT_REFERENCE": "EXTRACT_REFERENCE",
    "EXTRACT_PRODUCT_DATA": "EXTRACT_REFERENCE",
    "EXTRACT_REGISTRATION": "EXTRACT_REGISTRATION",
    "EXTRACT_PK": "EXTRACT_PK",
    "EXTRACT_PK_DATA": "EXTRACT_PK",
    "EXTRACT_ANALYTES": "EXTRACT_ANALYTES",
    "EXTRACT_FOOD": "EXTRACT_FOOD",
    "EXTRACT_FOOD_CONDITION": "EXTRACT_FOOD",
    "EXTRACT_DESIGN": "EXTRACT_DESIGN",
    "EXTRACT_STUDY_DESIGN": "EXTRACT_DESIGN",
    "EXTRACT_CV": "EXTRACT_CV",
    "EXTRACT_CV_DATA": "EXTRACT_CV",
    "EXTRACT_SAFETY": "EXTRACT_SAFETY",
    "FIND_CONFLICTS": "FIND_CONFLICTS",
}

# Default search seeds when query omitted
TASK_QUERIES = {
    "EXTRACT_PK": "Tmax half-life AUC Cmax",
    "EXTRACT_PK_DATA": "Tmax half-life",
    "EXTRACT_CV": "CVintra within-subject variation Cmax",
    "EXTRACT_CV_DATA": "coefficient of variation Cmax",
    "EXTRACT_FOOD": "fed fasting food",
    "EXTRACT_FOOD_CONDITION": "with food fed",
    "EXTRACT_REFERENCE": "reference product",
    "EXTRACT_PRODUCT_DATA": "reference product",
    "EXTRACT_ANALYTES": "analyte metabolite plasma",
    "EXTRACT_DESIGN": "crossover parallel design",
    "EXTRACT_STUDY_DESIGN": "crossover",
    "EXTRACT_REGISTRATION": "registration marketing authorisation",
    "EXTRACT_SAFETY": "safety adverse",
}


def _resolved_ai_config(*, force_mock: bool = False) -> dict:
    from app.domain.ai_runtime_settings import get_runtime

    s = get_settings()
    rt = get_runtime()
    enabled = bool(force_mock) or (s.ai_enabled if rt.enabled is None else bool(rt.enabled))
    provider = "mock" if force_mock else (rt.provider or s.ai_provider or "openai")
    model = rt.model or s.ai_model or "gpt-4o-mini"
    base_url = rt.base_url or s.ai_base_url or "https://api.openai.com/v1"
    api_key = rt.api_key or (s.openai_api_key or None) or None
    return {
        "enabled": enabled,
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "timeout": s.ai_timeout,
        "max_tokens": s.ai_max_tokens,
        "temperature": s.ai_temperature,
    }


def _provider(*, force_mock: bool = False):
    cfg = _resolved_ai_config(force_mock=force_mock)
    return get_ai_provider(
        enabled=cfg["enabled"],
        provider=cfg["provider"],
        base_url=cfg["base_url"],
        model=cfg["model"],
        timeout=cfg["timeout"],
        max_tokens=cfg["max_tokens"],
        temperature=cfg["temperature"],
        force_mock=force_mock,
        api_key=cfg["api_key"],
    )


def ai_status(*, force_mock: bool = False) -> AIStatusOut:
    cfg = _resolved_ai_config(force_mock=force_mock)
    if not cfg["enabled"] and not force_mock:
        return AIStatusOut(
            enabled=False,
            provider="disabled",
            model=cfg["model"],
            available=False,
            detail="AI disabled (env or Settings)",
        )
    if cfg["provider"] in {"openai", "cloud", "gpt"} and not cfg["api_key"] and not force_mock:
        return AIStatusOut(
            enabled=True,
            provider="openai",
            model=cfg["model"],
            available=False,
            detail="OpenAI API key missing — set in Settings",
        )
    provider = _provider(force_mock=force_mock)
    st = provider.status()
    return AIStatusOut(
        enabled=True,
        provider=st.provider,
        model=st.model,
        available=st.available,
        detail=st.detail,
    )


def _load_chunk_rows(
    db: Session,
    project_id: UUID,
    *,
    document_ids: list[UUID] | None,
) -> list[dict]:
    stmt = (
        select(DocumentChunk, DocumentPage, Document, Source)
        .join(DocumentPage, DocumentChunk.document_page_id == DocumentPage.id)
        .join(Document, DocumentPage.document_id == Document.id)
        .outerjoin(Source, Document.source_id == Source.id)
        .where(Document.project_id == project_id)
    )
    if document_ids:
        stmt = stmt.where(Document.id.in_(document_ids))
    rows = []
    for chunk, page, doc, source in db.execute(stmt).all():
        if not source:
            continue
        rows.append(
            {
                "chunk_id": str(chunk.id),
                "document_id": str(doc.id),
                "page_number": page.page_number,
                "text": chunk.text or "",
                "source_id": str(source.id),
                "source_type": source.type,
            }
        )
    return rows


def _select_chunks(
    rows: list[dict], query: str, limit: int
) -> list[ChunkContext]:
    if not rows:
        return []
    hits = search_chunks(rows, query, phrase=False, limit=limit)
    by_id = {r["chunk_id"]: r for r in rows}
    selected: list[ChunkContext] = []
    seen: set[str] = set()
    for h in hits:
        row = by_id.get(h.chunk_id)
        if not row or h.chunk_id in seen:
            continue
        seen.add(h.chunk_id)
        selected.append(
            ChunkContext(
                source_id=row["source_id"],
                document_id=row["document_id"],
                page=int(row["page_number"]),
                chunk_id=row["chunk_id"],
                text=row["text"],
                source_type=row.get("source_type"),
            )
        )
    # fallback: first N chunks if search empty but docs exist
    if not selected:
        for row in rows[:limit]:
            selected.append(
                ChunkContext(
                    source_id=row["source_id"],
                    document_id=row["document_id"],
                    page=int(row["page_number"]),
                    chunk_id=row["chunk_id"],
                    text=row["text"],
                    source_type=row.get("source_type"),
                )
            )
    return selected


def run_extraction(db: Session, project_id: UUID, payload: AIExtractRequest) -> AIExtractResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", field="project_id")

    foundation.ensure_research_case(db, project_id)
    case = db.execute(
        select(ResearchCase).where(ResearchCase.project_id == project_id)
    ).scalar_one()

    task = payload.task_type.upper()
    prompt_key = TASK_PROMPT_MAP.get(task)
    if prompt_key is None:
        raise ValidationError(f"Unsupported AI task_type: {payload.task_type}", field="task_type")
    prompt = get_prompt(prompt_key)

    query = payload.query or TASK_QUERIES.get(task, "bioequivalence")
    rows = _load_chunk_rows(db, project_id, document_ids=payload.document_ids)
    chunks = _select_chunks(rows, query, payload.limit_chunks)

    provider = _provider(force_mock=payload.force_mock)
    settings = get_settings()
    if not settings.ai_enabled and not payload.force_mock:
        raise ValidationError("AI is disabled (AI_ENABLED=false)", field="ai_enabled")

    run = AIRun(
        project_id=project_id,
        research_case_id=case.id,
        provider=provider.name,
        model=getattr(provider, "model", settings.ai_model),
        task_type=task,
        input_document_ids=[str(d) for d in (payload.document_ids or [])]
        or sorted({c.document_id for c in chunks}),
        prompt_version=prompt.full_id,
        schema_version=SCHEMA_VERSION,
        started_at=datetime.now(timezone.utc),
        status="RUNNING",
        chunk_ids=[c.chunk_id for c in chunks],
        claim_ids=[],
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        if not chunks:
            result = AIExtractionResult(claims=[], not_found=True, notes="NOT_FOUND")
        else:
            result = provider.extract_evidence(task_type=task, chunks=chunks, prompt=prompt)

        claim_outs: list[AIClaimOut] = []
        claim_ids: list[str] = []
        for draft in result.claims:
            # Guardrail: AI claims always PROPOSED / AI_PROPOSED
            created = foundation.create_evidence(
                db,
                project_id,
                EvidenceCreate(
                    source_id=draft.source_id,
                    evidence_type=_evidence_type_for_field(draft.field_name),
                    claim=f"{draft.field_name}: {draft.value}",
                    extracted_text=draft.evidence_text,
                    page=draft.page,
                    section=f"chunk:{draft.chunk_id}|doc:{draft.document_id}",
                    confidence=draft.confidence,
                    verification_status="PROPOSED",
                    claims=[
                        EvidenceClaimIn(
                            field_name=draft.field_name,
                            value=draft.value,
                            normalized_value=draft.normalized_value,
                            unit=draft.unit,
                            confidence=draft.confidence,
                            status="PROPOSED",
                            origin="AI_PROPOSED",
                            source_ids=[draft.source_id],
                        )
                    ],
                ),
            )
            c = created.claims[0]
            claim_ids.append(str(c.id))
            claim_outs.append(
                AIClaimOut(
                    claim_id=c.id,
                    evidence_id=created.id,
                    field_name=c.field_name,
                    value=c.value or draft.value,
                    normalized_value=c.normalized_value,
                    unit=c.unit,
                    source_id=draft.source_id,
                    document_id=draft.document_id,
                    page=draft.page,
                    chunk_id=draft.chunk_id,
                    evidence_text=draft.evidence_text,
                    confidence=float(c.confidence or draft.confidence or 0),
                    status="PROPOSED",
                    origin="AI_PROPOSED",
                    model=run.model,
                )
            )

        conflicts = engine.refresh_conflicts(db, project_id) if claim_outs else []
        payload_bytes = json.dumps(
            [c.model_dump(mode="json") for c in claim_outs], sort_keys=True
        ).encode()
        run.status = "NEEDS_REVIEW" if claim_outs else "COMPLETED"
        if result.not_found and not claim_outs:
            run.status = "COMPLETED"
        run.finished_at = datetime.now(timezone.utc)
        run.claim_ids = claim_ids
        run.output_checksum = hashlib.sha256(payload_bytes).hexdigest()
        run.error = None
        db.commit()
        db.refresh(run)

        return AIExtractResponse(
            run=AIRunOut.model_validate(run),
            claims=claim_outs,
            conflicts_detected=len([c for c in conflicts if c.resolved_at is None]),
        )
    except Exception as exc:  # noqa: BLE001
        run.status = "FAILED"
        run.finished_at = datetime.now(timezone.utc)
        run.error = str(exc)[:2000]
        db.commit()
        db.refresh(run)
        if isinstance(exc, (ValidationError, NotFoundError)):
            raise
        raise ValidationError(str(exc), field="ai_extraction") from exc


def _evidence_type_for_field(field_name: str) -> str:
    mapping = {
        "tmax": "PK",
        "half_life": "PK",
        "cv_cmax": "CV",
        "cv_auc": "CV",
        "food_condition": "FOOD",
        "reference_product": "REFERENCE",
        "analyte": "ANALYTE",
        "design": "DESIGN",
        "safety_statement": "SAFETY",
    }
    return mapping.get(field_name, "OTHER")


def list_ai_runs(db: Session, project_id: UUID) -> list[AIRunOut]:
    if db.get(Project, project_id) is None:
        raise NotFoundError("Project not found", field="project_id")
    rows = (
        db.execute(
            select(AIRun)
            .where(AIRun.project_id == project_id)
            .order_by(AIRun.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [AIRunOut.model_validate(r) for r in rows]


def list_proposed_ai_claims(db: Session, project_id: UUID) -> list[AIClaimOut]:
    foundation.ensure_research_case(db, project_id)
    case = db.execute(
        select(ResearchCase).where(ResearchCase.project_id == project_id)
    ).scalar_one()
    rows = (
        db.execute(
            select(EvidenceClaim, Evidence)
            .join(Evidence, EvidenceClaim.evidence_id == Evidence.id)
            .where(
                Evidence.research_case_id == case.id,
                EvidenceClaim.origin == "AI_PROPOSED",
                EvidenceClaim.status == "PROPOSED",
            )
        )
        .all()
    )
    out: list[AIClaimOut] = []
    for claim, evidence in rows:
        # parse chunk from section ref if present
        chunk_id = ""
        document_id = ""
        if evidence.section:
            for part in evidence.section.split("|"):
                if part.startswith("chunk:"):
                    chunk_id = part.split(":", 1)[1]
                elif part.startswith("doc:"):
                    document_id = part.split(":", 1)[1]
        out.append(
            AIClaimOut(
                claim_id=claim.id,
                evidence_id=evidence.id,
                field_name=claim.field_name,
                value=claim.value or "",
                normalized_value=claim.normalized_value,
                unit=claim.unit,
                source_id=evidence.source_id,
                document_id=document_id,
                page=evidence.page or "",
                chunk_id=chunk_id,
                evidence_text=evidence.extracted_text or claim.value or "",
                confidence=float(claim.confidence or 0),
                status=claim.status,
                origin=claim.origin,
            )
        )
    return out


def review_ai_claim(
    db: Session, project_id: UUID, claim_id: UUID, payload: AIClaimReviewRequest
) -> dict:
    claim = db.get(EvidenceClaim, claim_id)
    if claim is None:
        raise NotFoundError("Claim not found", field="claim_id")
    evidence = db.get(Evidence, claim.evidence_id)
    case = db.get(ResearchCase, evidence.research_case_id) if evidence else None
    if case is None or case.project_id != project_id:
        raise NotFoundError("Claim not in project", field="claim_id")
    if claim.origin != "AI_PROPOSED":
        raise ValidationError("Only AI_PROPOSED claims use this review endpoint", field="origin")

    action = payload.action.lower()
    if action == "reject":
        claim.status = "REJECTED"
        evidence.verification_status = "REJECTED"
        db.commit()
        return {"status": "REJECTED", "claim_id": str(claim.id)}

    if action in {"verify", "edit_verify"}:
        if action == "edit_verify":
            if payload.edited_value is not None:
                claim.value = payload.edited_value
            if payload.edited_normalized_value is not None:
                claim.normalized_value = payload.edited_normalized_value
        claim.status = "VERIFIED"
        evidence.verification_status = "VERIFIED"
        db.commit()
        # Apply via existing bridge — never AI-direct Study write
        applied = foundation.apply_verified(
            db,
            project_id,
            ApplyVerifiedRequest(claim_ids=[claim.id], analyte_id=payload.analyte_id),
        )
        return {
            "status": "VERIFIED",
            "claim_id": str(claim.id),
            "apply": applied.model_dump(),
        }

    raise ValidationError("action must be verify|reject|edit_verify", field="action")


class AIResearchExtractionService:
    """Named extraction entrypoints — all routes go through run_extraction + Evidence."""

    def extract_reference(self, db: Session, project_id: UUID, **kwargs) -> AIExtractResponse:
        return run_extraction(
            db, project_id, AIExtractRequest(task_type="EXTRACT_REFERENCE", **kwargs)
        )

    def extract_registration(self, db: Session, project_id: UUID, **kwargs) -> AIExtractResponse:
        return run_extraction(
            db, project_id, AIExtractRequest(task_type="EXTRACT_REGISTRATION", **kwargs)
        )

    def extract_pk(self, db: Session, project_id: UUID, **kwargs) -> AIExtractResponse:
        return run_extraction(db, project_id, AIExtractRequest(task_type="EXTRACT_PK", **kwargs))

    def extract_analytes(self, db: Session, project_id: UUID, **kwargs) -> AIExtractResponse:
        return run_extraction(
            db, project_id, AIExtractRequest(task_type="EXTRACT_ANALYTES", **kwargs)
        )

    def extract_food(self, db: Session, project_id: UUID, **kwargs) -> AIExtractResponse:
        return run_extraction(db, project_id, AIExtractRequest(task_type="EXTRACT_FOOD", **kwargs))

    def extract_design(self, db: Session, project_id: UUID, **kwargs) -> AIExtractResponse:
        return run_extraction(
            db, project_id, AIExtractRequest(task_type="EXTRACT_DESIGN", **kwargs)
        )

    def extract_cv(self, db: Session, project_id: UUID, **kwargs) -> AIExtractResponse:
        return run_extraction(db, project_id, AIExtractRequest(task_type="EXTRACT_CV", **kwargs))

    def extract_safety(self, db: Session, project_id: UUID, **kwargs) -> AIExtractResponse:
        return run_extraction(
            db, project_id, AIExtractRequest(task_type="EXTRACT_SAFETY", **kwargs)
        )

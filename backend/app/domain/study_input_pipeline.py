"""Study Input Package pipeline — Phase 14 / 14.1.

Binary-first: DOCX/PDF → ingest → classify → extract → candidates → conflicts.
Text dumps are equivalence baselines only (prefer_text_dump=True).
AI-off deterministic. Never mutates Study.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.study_input_binary_ingest import (
    DocumentIngestionResult,
    ingest_binary_file,
    sha256_bytes,
    sha256_file,
    validate_binary_upload,
)
from app.domain.study_input_canonical import resolve_to_canonical_projection
from app.domain.study_input_classify import classify_document
from app.domain.study_input_conflicts import detect_candidate_conflicts, resolve_conflict
from app.domain.study_input_coverage import build_input_coverage, detect_missing_inputs
from app.domain.study_input_extractors import (
    extract_checklist,
    extract_design_only,
    extract_smpc,
    extract_synopsis,
    extract_text_from_docx,
    extract_text_from_pdf,
)
from app.domain.study_input_package import (
    CandidateStudyValue,
    StudyInputDocument,
    StudyInputPackage,
    reject_candidate,
    verify_candidate,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "fixtures" / "study_inputs"


def load_fixture_metadata(fixture_dir: Path) -> dict[str, Any]:
    meta_path = fixture_dir / "fixture.json"
    return json.loads(meta_path.read_text(encoding="utf-8"))


def resolve_fixture_path(fixture_dir: Path, filename: str, *, prefer_raw: bool = True) -> Path:
    """Prefer raw/ binary; fall back to sources/ for compatibility."""
    if prefer_raw:
        raw = fixture_dir / "raw" / filename
        if raw.exists():
            return raw
    src = fixture_dir / "sources" / filename
    if src.exists():
        return src
    return fixture_dir / "raw" / filename


def _read_text_dump(path: Path) -> tuple[str, list[dict[str, Any]] | None]:
    """Text-fixture path for equivalence baselines only."""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        txt = Path(str(path) + ".txt")
        extracted = path.parent.parent / "extracted" / (path.stem + ".txt")
        if extracted.exists():
            return extracted.read_text(encoding="utf-8"), None
        if txt.exists():
            return txt.read_text(encoding="utf-8"), None
        return extract_text_from_docx(path), None
    if suffix == ".pdf":
        extracted = path.parent.parent / "extracted" / (path.stem + ".txt")
        if extracted.exists():
            return extracted.read_text(encoding="utf-8"), None
        return extract_text_from_pdf(path)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8"), None
    return "", None


def create_package(
    *,
    package_id: str | None = None,
    study_id: str | None = None,
    project_id: str | None = None,
    fixture_id: str | None = None,
) -> StudyInputPackage:
    return StudyInputPackage(
        package_id=package_id or f"SIP-{uuid4().hex[:12]}",
        study_id=study_id,
        project_id=project_id,
        fixture_id=fixture_id,
        status="DRAFT",
    )


def _find_by_hash(package: StudyInputPackage, content_hash: str) -> StudyInputDocument | None:
    for d in package.documents:
        if d.content_hash == content_hash and d.superseded_by is None:
            return d
    return None


def attach_document(
    package: StudyInputPackage,
    *,
    path: Path,
    document_type: str | None = None,
    user_selected: bool = False,
    role: str = "INPUT",
    source_id: str | None = None,
    prefer_text_dump: bool = False,
    force_new_version: bool = False,
) -> StudyInputDocument:
    """Attach a document. Production default is binary ingestion (prefer_text_dump=False)."""
    path = Path(path)
    content = path.read_bytes() if path.exists() else b""
    content_hash = sha256_bytes(content) if content else sha256_file(path) if path.exists() else ""

    # Idempotency: same bytes → same active document identity
    if content_hash and not force_new_version:
        existing = _find_by_hash(package, content_hash)
        if existing is not None:
            return existing

    ingestion: DocumentIngestionResult | None = None
    text = ""
    pages: list[dict[str, Any]] | None = None
    tables: list[dict[str, Any]] | None = None

    if prefer_text_dump:
        text, pages = _read_text_dump(path)
        content_hash = content_hash or sha256_bytes(text.encode("utf-8"))
        ingestion_status = "SUCCESS" if text.strip() else "FAILED"
        warnings: list[str] = ["prefer_text_dump=True (equivalence baseline)"]
        mime, _ = mimetypes.guess_type(path.name)
        file_size = len(content) if content else len(text.encode("utf-8"))
        page_count = len(pages) if pages else None
        paragraph_count = None
        table_count = None
        svid = f"SV-TXT-{content_hash[:12]}" if content_hash else f"SV-{uuid4().hex[:10]}"
    else:
        ingestion = ingest_binary_file(
            path,
            source_id=source_id,
            document_type=document_type,
            filename=path.name,
        )
        text = ingestion.extracted_text
        pages = ingestion.pages or None
        tables = ingestion.tables or None
        content_hash = ingestion.content_hash
        ingestion_status = ingestion.extraction_status
        warnings = list(ingestion.warnings)
        mime = ingestion.mime_type
        file_size = ingestion.file_size
        page_count = ingestion.page_count
        paragraph_count = ingestion.paragraph_count
        table_count = ingestion.table_count
        svid = ingestion.source_version_id
        if ingestion.extraction_status == "FAILED":
            # Still register the document — do not pretend SUCCESS
            pass

    classification = classify_document(
        filename=path.name,
        text=text,
        user_selected_type=document_type if user_selected else None,
    )
    if document_type:
        dtype = document_type
        classification_method = "MANUAL" if user_selected else "HEURISTIC"
        overridable = True
        confidence = "HIGH"
    else:
        dtype = classification.document_type
        classification_method = classification.method
        overridable = classification.overridable
        confidence = classification.confidence

    sid = source_id or (ingestion.source_id if ingestion else f"SRC-{dtype}-{uuid4().hex[:8]}")
    doc = StudyInputDocument(
        document_id=f"DOC-{uuid4().hex[:12]}",
        source_id=sid,
        source_version_id=svid,
        document_type=dtype,
        original_filename=path.name,
        content_hash=content_hash,
        mime_type=mime,
        classification_method=classification_method,
        classification_confidence=confidence,
        classification_overridable=overridable,
        ingestion_status=ingestion_status,
        role=role,
        relative_path=str(path),
        user_selected_type=user_selected,
        file_size=file_size,
        page_count=page_count,
        paragraph_count=paragraph_count,
        table_count=table_count,
        ingestion_warnings=warnings,
    )
    # Stash structure for extraction on the package run cache
    package.documents.append(doc)
    package.classification_status = "COMPLETE" if package.documents else "PENDING"
    if ingestion is not None:
        package.ingestion_runs.append(
            {
                **ingestion.observability(),
                "document_id": doc.document_id,
                "candidate_count": None,
                "conflict_count": None,
            }
        )
        # Cache structure keyed by document_id on package notes channel
        if not hasattr(package, "_ingest_cache"):
            setattr(package, "_ingest_cache", {})
        getattr(package, "_ingest_cache")[doc.document_id] = {
            "text": text,
            "pages": pages,
            "tables": tables,
        }
    else:
        if not hasattr(package, "_ingest_cache"):
            setattr(package, "_ingest_cache", {})
        getattr(package, "_ingest_cache")[doc.document_id] = {
            "text": text,
            "pages": pages,
            "tables": tables,
        }
    return doc


def replace_document(
    package: StudyInputPackage,
    *,
    old_document_id: str,
    new_path: Path,
    document_type: str | None = None,
    role: str | None = None,
) -> StudyInputDocument:
    """Replace binary with a new version. Preserves old doc + version; invalidates candidates."""
    old = next((d for d in package.documents if d.document_id == old_document_id), None)
    if old is None:
        raise KeyError(old_document_id)
    new_doc = attach_document(
        package,
        path=new_path,
        document_type=document_type or old.document_type,
        user_selected=True,
        role=role or old.role,
        source_id=old.source_id,  # same source identity
        force_new_version=True,
    )
    new_doc.previous_version_id = old.source_version_id
    old.superseded_by = new_doc.document_id
    # Invalidate prior candidates for old document — require re-review; do not delete evidence
    for c in package.candidates:
        if c.document_id == old.document_id and c.status in {"PROPOSED", "REVIEW_REQUIRED", "VERIFIED"}:
            if c.status == "VERIFIED":
                c.status = "REVIEW_REQUIRED"
                c.notes = (c.notes or "") + " | invalidated by source replacement"
            else:
                c.status = "REVIEW_REQUIRED"
                c.notes = (c.notes or "") + " | superseded source version"
    return new_doc


def reclassify_document(
    package: StudyInputPackage,
    document_id: str,
    *,
    document_type: str,
    user_selected: bool = True,
) -> StudyInputDocument:
    doc = next((d for d in package.documents if d.document_id == document_id), None)
    if doc is None:
        raise KeyError(document_id)
    if not doc.classification_overridable and not user_selected:
        raise ValueError("Cannot overwrite non-overridable classification")
    doc.document_type = document_type
    doc.classification_method = "MANUAL"
    doc.classification_confidence = "HIGH"
    doc.user_selected_type = True
    doc.classification_overridable = True
    return doc


def extract_document(
    package: StudyInputPackage,
    doc: StudyInputDocument,
    *,
    text_override: str | None = None,
) -> list[CandidateStudyValue]:
    if doc.role == "REFERENCE_OUTPUT" or doc.document_type == "GOLDEN_PROTOCOL":
        return []
    if doc.document_type in {"OTHER", "UNKNOWN", "PREVIOUS_PROTOCOL", "REGULATORY", "PUBLICATION"}:
        return []
    if doc.ingestion_status == "FAILED" and text_override is None:
        return []

    cache = getattr(package, "_ingest_cache", {}).get(doc.document_id) or {}
    pages = cache.get("pages")
    tables = cache.get("tables")
    if text_override is not None:
        text = text_override
    elif cache.get("text") is not None:
        text = cache["text"]
    else:
        path = Path(doc.relative_path) if doc.relative_path else None
        if path and path.exists():
            ing = ingest_binary_file(path, source_id=doc.source_id, document_type=doc.document_type)
            text = ing.extracted_text
            pages = ing.pages or None
            tables = ing.tables or None
        else:
            text = ""

    common = dict(
        source_id=doc.source_id,
        original_filename=doc.original_filename,
        document_id=doc.document_id,
    )
    if doc.document_type == "CHECKLIST":
        cands = extract_checklist(text, tables=tables, **common)
    elif doc.document_type == "SYNOPSIS":
        cands = extract_synopsis(text, **common)
    elif doc.document_type == "DESIGN":
        cands = extract_design_only(text, **common)
    elif doc.document_type == "SMPC":
        cands = extract_smpc(text, pages=pages, **common)
    else:
        cands = []

    for c in cands:
        c.study_id = package.study_id
        c.source_version_id = doc.source_version_id
    return cands


def run_extraction(package: StudyInputPackage, *, replace: bool = True) -> StudyInputPackage:
    package.status = "EXTRACTING"
    new_cands: list[CandidateStudyValue] = []
    active_ids = {d.document_id for d in package.documents if d.superseded_by is None}
    for doc in package.documents:
        if doc.superseded_by is not None:
            continue
        new_cands.extend(extract_document(package, doc))

    if replace:
        kept = [
            c
            for c in package.candidates
            if c.document_id not in active_ids
            or (c.status == "REVIEW_REQUIRED" and "superseded" in (c.notes or ""))
        ]
        # Drop stale active-doc candidates; keep invalidated superseded evidence
        kept = [c for c in package.candidates if c.document_id not in active_ids]
        package.candidates = kept + new_cands
    else:
        package.candidates.extend(new_cands)

    conflicts = detect_candidate_conflicts(package.candidates)
    package.conflicts = [c.to_dict() for c in conflicts]

    gaps, tasks = detect_missing_inputs(package)
    package.knowledge_gaps = [g.to_dict() for g in gaps]
    package.research_tasks = [t.to_dict() for t in tasks]

    package.coverage = build_input_coverage(package)
    package.blocking_issues = list(package.coverage.get("blocking_issues") or [])

    if package.conflicts:
        package.status = "REVIEW_REQUIRED"
    elif package.blocking_issues:
        package.status = "REVIEW_REQUIRED"
    else:
        package.status = "READY_FOR_REVIEW"

    if any(c.get("status") == "OPEN" for c in package.conflicts):
        if package.coverage.get("ready_for_assembly"):
            package.coverage["ready_for_assembly"] = False
        package.status = "REVIEW_REQUIRED"

    # Update last ingestion run observability
    if package.ingestion_runs:
        package.ingestion_runs[-1]["candidate_count"] = len(package.candidates)
        package.ingestion_runs[-1]["conflict_count"] = len(package.conflicts)

    return package


def load_real_fixture_package(
    fixture_id: str = "UPDCB-02-BE-2026-REAL-01",
    *,
    run_extract: bool = True,
    prefer_text_dump: bool = False,
    include_smpc: bool = True,
) -> StudyInputPackage:
    fixture_dir = FIXTURE_ROOT / "updcb_02_be_2026"
    meta = load_fixture_metadata(fixture_dir)
    pkg = create_package(fixture_id=meta.get("fixture_id") or fixture_id)
    for doc_meta in meta.get("documents") or []:
        if not include_smpc and doc_meta.get("type") == "SMPC":
            continue
        fname = doc_meta["filename"]
        # Normalize smpc filename across raw/sources
        alt = "smpc.pdf" if fname.startswith("smpc") else fname
        path = resolve_fixture_path(fixture_dir, fname)
        if not path.exists():
            path = resolve_fixture_path(fixture_dir, alt)
        attach_document(
            pkg,
            path=path,
            document_type=doc_meta.get("type"),
            user_selected=False,
            role=doc_meta.get("role") or "INPUT",
            source_id=doc_meta.get("source_id"),
            prefer_text_dump=prefer_text_dump,
        )
    if run_extract:
        run_extraction(pkg)
    return pkg


def load_design_only_fixture(*, run_extract: bool = True, prefer_docx: bool = True) -> StudyInputPackage:
    fixture_dir = FIXTURE_ROOT / "design_only_updcb"
    meta = load_fixture_metadata(fixture_dir)
    pkg = create_package(fixture_id=meta.get("fixture_id") or "DESIGN-ONLY-01")
    fname = meta["documents"][0]["filename"]
    if prefer_docx:
        docx = fixture_dir / "raw" / "design.docx"
        if docx.exists():
            fname = "design.docx"
            path = docx
        else:
            path = resolve_fixture_path(fixture_dir, fname)
    else:
        path = resolve_fixture_path(fixture_dir, fname)
    attach_document(
        pkg,
        path=path,
        document_type="DESIGN",
        user_selected=True,
        role="INPUT",
        source_id="SRC-DESIGN-ONLY",
    )
    if run_extract:
        run_extraction(pkg)
    return pkg


def apply_ai_candidates(
    package: StudyInputPackage,
    proposals: list[dict[str, Any]],
    *,
    source_id: str = "SRC-AI-MOCK",
) -> list[CandidateStudyValue]:
    """Persist AI proposals as PROPOSED only. Reject malformed. Never mutate Study."""
    created: list[CandidateStudyValue] = []
    for p in proposals:
        try:
            c = CandidateStudyValue(
                field_path=str(p["field_path"]),
                value=p.get("value"),
                value_type=str(p.get("value_type") or "string"),
                source_id=str(p.get("source_id") or source_id),
                document_type=str(p.get("document_type") or "OTHER"),
                excerpt=str(p.get("excerpt") or ""),
                location=p.get("location"),
                confidence=str(p.get("confidence") or "LOW"),
                extraction_method="AI",
                status="PROPOSED",
                document_id=p.get("document_id"),
                source_version_id=p.get("source_version_id") or "SV-AI",
            )
        except (ValueError, KeyError, TypeError):
            continue
        if c.status != "PROPOSED":
            raise RuntimeError("AI cannot set non-PROPOSED status")
        package.candidates.append(c)
        created.append(c)
    package.conflicts = [c.to_dict() for c in detect_candidate_conflicts(package.candidates)]
    package.coverage = build_input_coverage(package)
    return created


__all__ = [
    "FIXTURE_ROOT",
    "apply_ai_candidates",
    "attach_document",
    "create_package",
    "load_design_only_fixture",
    "load_real_fixture_package",
    "reclassify_document",
    "reject_candidate",
    "replace_document",
    "resolve_conflict",
    "resolve_fixture_path",
    "resolve_to_canonical_projection",
    "run_extraction",
    "sha256_file",
    "validate_binary_upload",
    "verify_candidate",
]

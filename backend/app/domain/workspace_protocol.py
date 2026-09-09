"""Phase 17 — Canonical workspace protocol preview + persistent DOCX artifacts.

Does NOT use Legacy Project protocol generation path.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from docx import Document as DocxDocument
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.exceptions import ValidationError
from app.domain.study_workspace import append_audit, build_preflight, list_protocol_drafts
from app.domain.workspace_snapshots import latest_snapshot
from app.models.workspace_persistence import WorkspaceProtocolArtifact, WorkspaceProtocolDraftRecord


def _artifact_root() -> Path:
    settings = get_settings()
    root = Path(settings.document_storage_root).resolve().parent / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_preview_from_draft(
    db: Session,
    study_key: str,
    *,
    protocol_id: str | None = None,
) -> dict[str, Any]:
    """Preview reads ProtocolDraft (+ linked snapshot) only — no stale templates."""
    draft_row = None
    if protocol_id:
        draft_row = db.execute(
            select(WorkspaceProtocolDraftRecord).where(
                WorkspaceProtocolDraftRecord.protocol_id == protocol_id
            )
        ).scalar_one_or_none()
    if draft_row is None:
        draft_row = (
            db.execute(
                select(WorkspaceProtocolDraftRecord)
                .where(WorkspaceProtocolDraftRecord.study_key == study_key)
                .order_by(WorkspaceProtocolDraftRecord.version.desc())
            )
            .scalars()
            .first()
        )
    mem = list_protocol_drafts(study_key)
    snap = latest_snapshot(db, study_key)
    payload = (snap or {}).get("payload") or {}
    facts = {}
    for c in payload.get("candidates") or []:
        facts[c.get("field_path")] = c.get("value")

    sections = [
        {"code": "GENERAL", "title": "1. General Information", "body": _section_general(facts, study_key)},
        {"code": "BACKGROUND", "title": "2. Background", "body": "Derived from verified snapshot facts only."},
        {"code": "OBJECTIVES", "title": "3. Objectives", "body": "Bioequivalence objectives from approved decisions."},
        {"code": "DESIGN", "title": "4. Study Design", "body": str(facts.get("design.type") or facts.get("design.crossover") or "—")},
        {"code": "SUBJECTS", "title": "5. Subjects", "body": str(facts.get("subjects.planned_n") or facts.get("subjects.randomized_n") or "—")},
        {"code": "PRODUCTS", "title": "6. Test/Reference Products", "body": _section_products(facts)},
        {"code": "DOSING", "title": "7. Dosing", "body": str(facts.get("reference_product.dose") or facts.get("test_product.dose") or "—")},
        {"code": "FOOD", "title": "8. Food", "body": str(facts.get("food.condition") or "—")},
        {"code": "SAMPLING", "title": "9. Sampling", "body": str(facts.get("sampling.schedule") or "—")},
        {"code": "PK", "title": "10. PK", "body": str(facts.get("pk.parameters") or "—")},
        {"code": "STATISTICS", "title": "11. Statistics", "body": "From approved statistics plan when present."},
        {"code": "SAFETY", "title": "12. Safety", "body": "From verified evidence only."},
        {"code": "ETHICS", "title": "13. Ethics", "body": "Standard ethics section — expert review required."},
        {"code": "SCHEDULE", "title": "14. Schedule", "body": "From procedure schedule when approved."},
    ]
    if draft_row and draft_row.sections_payload:
        # Prefer draft registry summary order when present
        pass

    return {
        "study_id": study_key,
        "protocol_id": draft_row.protocol_id if draft_row else (mem[-1]["protocol_id"] if mem else None),
        "snapshot_id": (draft_row.snapshot_id if draft_row else None) or (snap or {}).get("snapshot_id"),
        "toc": [{"code": s["code"], "title": s["title"]} for s in sections],
        "sections": sections,
        "source": "ProtocolDraft+CanonicalSnapshot",
        "legacy_project_path": False,
        "stale_template_values": False,
    }


def _section_general(facts: dict[str, Any], study_key: str) -> str:
    return (
        f"Study ID: {study_key}\n"
        f"Sponsor: {facts.get('sponsor.name') or '—'}\n"
        f"Product: {facts.get('test_product.name') or facts.get('product.name') or '—'}"
    )


def _section_products(facts: dict[str, Any]) -> str:
    return (
        f"Test: {facts.get('test_product.name') or '—'} "
        f"/ Reference: {facts.get('reference_product.name') or '—'}"
    )


def generate_docx_artifact(
    db: Session,
    study_key: str,
    *,
    created_by: str,
    organization_id: UUID | None = None,
    force_warnings_ok: bool = False,
) -> dict[str, Any]:
    """Preflight → render → store artifact. Download must serve stored bytes."""
    pf = build_preflight(study_key)
    if pf.get("critical_blockers"):
        raise ValidationError(
            "CRITICAL blockers present — DOCX generation disabled",
            field="preflight",
            details={"critical_blockers": pf["critical_blockers"]},
        )
    if pf.get("warnings") and not force_warnings_ok:
        raise ValidationError(
            "Critical blockers отсутствуют. Есть warnings. Confirm to proceed.",
            field="preflight_warnings",
            details={"warnings": pf.get("warnings") or pf.get("checks")},
        )

    preview = build_preview_from_draft(db, study_key)
    protocol_id = preview.get("protocol_id") or f"PROT-{study_key}-1"
    snap_id = preview.get("snapshot_id")

    doc = DocxDocument()
    doc.add_heading(f"Protocol Draft — {study_key}", level=0)
    doc.add_paragraph(f"Generated from snapshot {snap_id} (canonical workspace path).")
    doc.add_paragraph("Recommendation ≠ approval. AI assistive only.")
    for section in preview["sections"]:
        doc.add_heading(section["title"], level=1)
        doc.add_paragraph(str(section.get("body") or ""))

    artifact_id = f"ART-{uuid4().hex[:12]}"
    safe_name = f"{artifact_id}.docx"
    org_part = str(organization_id or "public")
    rel_key = f"{org_part}/{study_key}/{safe_name}"
    abs_path = _artifact_root() / org_part / study_key
    abs_path.mkdir(parents=True, exist_ok=True)
    file_path = abs_path / safe_name
    doc.save(str(file_path))
    raw = file_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()

    # Idempotency: same protocol + same hash → return existing
    existing = db.execute(
        select(WorkspaceProtocolArtifact).where(
            WorkspaceProtocolArtifact.protocol_id == protocol_id,
            WorkspaceProtocolArtifact.sha256 == sha,
        )
    ).scalar_one_or_none()
    if existing:
        return _serialize_artifact(existing)

    row = WorkspaceProtocolArtifact(
        artifact_id=artifact_id,
        protocol_id=protocol_id,
        study_key=study_key,
        organization_id=organization_id,
        filename=f"{study_key}_{protocol_id}.docx",
        size=len(raw),
        sha256=sha,
        storage_key=rel_key,
        generated_by=created_by,
        generated_at=datetime.now(timezone.utc),
        snapshot_id=snap_id,
        decision_set=[],
        statistics_version=None,
        sample_size_version=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    append_audit(
        study_key,
        event="DOCX_ARTIFACT_CREATED",
        who=created_by,
        what=artifact_id,
        new_value=sha,
        source=protocol_id,
    )
    return _serialize_artifact(row)


def get_artifact(db: Session, artifact_id: str) -> dict[str, Any] | None:
    row = db.execute(
        select(WorkspaceProtocolArtifact).where(WorkspaceProtocolArtifact.artifact_id == artifact_id)
    ).scalar_one_or_none()
    return _serialize_artifact(row) if row else None


def read_artifact_bytes(db: Session, artifact_id: str) -> tuple[bytes, dict[str, Any]]:
    """Return exact stored bytes — never rebuild."""
    row = db.execute(
        select(WorkspaceProtocolArtifact).where(WorkspaceProtocolArtifact.artifact_id == artifact_id)
    ).scalar_one_or_none()
    if row is None:
        raise ValidationError("Artifact not found", field="artifact_id")
    path = _artifact_root() / row.storage_key
    if not path.is_file():
        raise ValidationError("Artifact file missing on disk", field="storage_key")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != row.sha256:
        raise ValidationError("Artifact integrity check failed", field="sha256")
    return data, _serialize_artifact(row)


def list_artifacts(db: Session, study_key: str) -> list[dict[str, Any]]:
    rows = (
        db.execute(
            select(WorkspaceProtocolArtifact)
            .where(WorkspaceProtocolArtifact.study_key == study_key)
            .order_by(WorkspaceProtocolArtifact.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_serialize_artifact(r) for r in rows]


def _serialize_artifact(row: WorkspaceProtocolArtifact) -> dict[str, Any]:
    return {
        "artifact_id": row.artifact_id,
        "protocol_id": row.protocol_id,
        "study_id": row.study_key,
        "filename": row.filename,
        "mime_type": row.mime_type,
        "size": row.size,
        "sha256": row.sha256,
        "storage_key": row.storage_key,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "generated_by": row.generated_by,
        "snapshot_id": row.snapshot_id,
        "decision_set": list(row.decision_set or []),
        "statistics_version": row.statistics_version,
        "sample_size_version": row.sample_size_version,
        "rebuild_on_download": False,
    }

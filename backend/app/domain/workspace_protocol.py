"""Phase 17 / 29 — Canonical workspace protocol preview + template-based DOCX artifacts.

Phase 29: Workspace calls the existing `docx_renderer.render_protocol_docx`
(template BE_Protocol_Template_v2.0.docx). Does NOT use Legacy Project ORM as
content authority. Does NOT invent a second renderer.
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
from app.domain.docx_contamination import (
    assert_docx_clean_or_raise,
    clear_product_specific_contamination,
    scrub_contamination_xml_package,
)
from app.domain.docx_profile import DOCX_GENERATOR_VERSION, TEMPLATE_VERSION, get_template_profile
from app.domain.docx_renderer import render_protocol_docx
from app.domain.docx_stale_scrub import scrub_stale_template_products
from app.domain.exceptions import ValidationError
from app.domain.protocol_assembly import assemble_protocol
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.protocol_dependency_stale import detect_stale_protocol_dependencies
from app.domain.sample_size_store import latest_accepted_calculation
from app.domain.statistics_store import latest_approved_plan
from app.domain.study_workspace import append_audit, build_preflight, list_protocol_drafts
from app.domain.template_contamination import contamination_preflight
from app.domain.protocol_traceability import (
    build_section_traceability,
    enrich_field_bindings_with_sources,
    scrub_docx_technical_enums,
)
from app.domain.workspace_assembly_context import (
    build_workspace_assembly_context,
    workspace_docx_blockers,
)
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

    field_bindings = {
        "reference_product.dose": {
            "section": "DOSING",
            "label": "Reference dose",
            "value": facts.get("reference_product.dose"),
        },
        "design.type": {
            "section": "DESIGN",
            "label": "Design",
            "value": facts.get("design.type") or facts.get("design.crossover"),
        },
        "subjects.randomized_n": {
            "section": "SUBJECTS",
            "label": "Subjects N",
            "value": facts.get("subjects.randomized_n") or facts.get("subjects.planned_n"),
        },
        "food.condition": {
            "section": "FOOD",
            "label": "Food",
            "value": facts.get("food.condition"),
        },
        "pk.parameters": {
            "section": "PK",
            "label": "PK parameters",
            "value": facts.get("pk.parameters"),
        },
        "pk.expected_tmax": {
            "section": "PK",
            "label": "Tmax",
            "value": facts.get("pk.expected_tmax") or facts.get("pk.tmax"),
        },
        "product.pharmacology.mechanism": {
            "section": "BACKGROUND",
            "label": "Pharmacology",
            "value": facts.get("product.pharmacology.mechanism"),
        },
    }

    # Phase 30.2 — section-level reverse traceability (DOCX section → claim/source)
    traceability = build_section_traceability(study_key, facts=facts)
    field_bindings = enrich_field_bindings_with_sources(field_bindings, traceability)

    # Attach per-section source summary (writer «Источник»)
    by_section: dict[str, list[dict[str, Any]]] = {}
    for t in traceability:
        by_section.setdefault(str(t["protocol_section_id"]), []).append(t)
    for s in sections:
        s["sources"] = by_section.get(str(s["code"]), [])

    mem_draft = mem[-1] if mem else None
    current_snap_id = (snap or {}).get("snapshot_id")
    stale = detect_stale_protocol_dependencies(
        study_key,
        draft=mem_draft,
        current_snapshot_id=current_snap_id,
        current_snapshot_version=(snap or {}).get("version"),
    )

    return {
        "study_id": study_key,
        "protocol_id": draft_row.protocol_id if draft_row else (mem_draft["protocol_id"] if mem_draft else None),
        "version": draft_row.version if draft_row else (mem_draft.get("version") if mem_draft else None),
        "status": draft_row.status if draft_row else (mem_draft.get("status") if mem_draft else "DRAFT"),
        "snapshot_id": (draft_row.snapshot_id if draft_row else None) or current_snap_id,
        "snapshot_version": (snap or {}).get("version"),
        "toc": [{"code": s["code"], "title": s["title"]} for s in sections],
        "sections": sections,
        "tables": [],
        "field_bindings": field_bindings,
        "section_traceability": traceability,
        "source": "ProtocolDraft+CanonicalSnapshot",
        "legacy_project_path": False,
        "stale_template_values": bool(stale.get("stale")),
        "stale_dependencies": stale,
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
    mode: str = "DRAFT",
) -> dict[str, Any]:
    """Preflight → assemble from Workspace → existing template renderer → store artifact."""
    pf = build_preflight(study_key)
    snap = latest_snapshot(db, study_key)
    mem = list_protocol_drafts(study_key)
    mem_draft = mem[-1] if mem else None
    stale = detect_stale_protocol_dependencies(
        study_key,
        draft=mem_draft,
        current_snapshot_id=(snap or {}).get("snapshot_id"),
        current_snapshot_version=(snap or {}).get("version"),
    )
    if stale.get("stale"):
        raise ValidationError(
            "Protocol dependencies are stale — regenerate draft before DOCX",
            field="protocol_dependencies",
            details={"stale_dependencies": stale, "critical_blockers": pf.get("critical_blockers")},
        )
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
    if preview.get("stale_template_values"):
        raise ValidationError(
            "Protocol preview reports stale dependencies — DOCX blocked",
            field="protocol_dependencies",
            details={"stale_dependencies": preview.get("stale_dependencies")},
        )

    protocol_id = preview.get("protocol_id") or f"PROT-{study_key}-1"
    snap_id = preview.get("snapshot_id") or (snap or {}).get("snapshot_id")
    decision_set = list((mem_draft or {}).get("based_on_decisions") or [])
    st = latest_approved_plan(study_key)
    ss = latest_accepted_calculation(study_key)
    statistics_version = (mem_draft or {}).get("based_on_statistics") or (st.id if st else None)
    sample_size_version = (mem_draft or {}).get("based_on_sample_size") or (ss.id if ss else None)

    study_ctx = build_workspace_assembly_context(
        study_key,
        snapshot_payload=(snap or {}).get("payload") if isinstance(snap, dict) else None,
    )
    content_blockers = workspace_docx_blockers(study_ctx, study_id=study_key)
    if content_blockers:
        raise ValidationError(
            "Недостаточно canonical/approved данных для заполнения шаблона протокола",
            field="workspace_docx",
            details={"blockers": content_blockers},
        )

    render_mode = str(mode or "DRAFT").upper()
    contam = contamination_preflight(study_ctx, mode=render_mode)
    if not contam.get("ok"):
        raise ValidationError(
            contam.get("message")
            or "Template contains product-specific content that is not supported by the current study.",
            field="CRITICAL_TEMPLATE_CONTAMINATION",
            details={
                "action": contam.get("action"),
                "unmanaged_blocks": contam.get("unmanaged_blocks"),
                "mode": render_mode,
            },
        )

    assembled = assemble_protocol(
        study_ctx,
        blocking_validation=False,
        validation_issues=[],
        rules_version="workspace-1",
        protocol_version=str((study_ctx.get("study") or {}).get("version") or "1"),
    )
    protocol_payload = {
        "status": assembled.get("status") or "DRAFT",
        "protocol_version": assembled.get("protocol_version") or "1",
        "template_version": TEMPLATE_VERSION,
        "rules_version": assembled.get("rules_version"),
        "generator_version": assembled.get("generator_version") or PROTOCOL_GENERATOR_VERSION,
        "consistency_snapshot": assembled.get("consistency_snapshot") or {},
        "canonical_fingerprint": assembled.get("canonical_fingerprint"),
        "sections": assembled.get("sections") or [],
        "tables": assembled.get("tables") or [],
        "references": assembled.get("references") or [],
        "build_report": assembled.get("build_report") or {},
    }

    artifact_id = f"ART-{uuid4().hex[:12]}"
    org_part = str(organization_id or "public")
    abs_path = _artifact_root() / org_part / study_key
    abs_path.mkdir(parents=True, exist_ok=True)

    profile = get_template_profile()
    result = render_protocol_docx(
        protocol_payload=protocol_payload,
        study_ctx=study_ctx,
        mode=render_mode,
        output_dir=abs_path,
        project_slug="".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in study_key)[:40]
        or "study",
        protocol_version=str(protocol_payload.get("protocol_version") or "1"),
    )
    if result.status in {"BLOCKED", "FAILED"} or result.output_path is None:
        raise ValidationError(
            "Template DOCX render blocked or failed",
            field="docx_renderer",
            details={
                "status": result.status,
                "blocking_reasons": list(result.blocking_reasons or []),
                "template_version": result.template_version or profile.template_version,
                "generator_version": result.generator_version or DOCX_GENERATOR_VERSION,
            },
        )

    doc = DocxDocument(str(result.output_path))
    # Primary: semantic clear of product-specific template example content
    contamination_clear = clear_product_specific_contamination(doc, study_ctx)
    # Secondary: token scrub of leftover product-name strings
    scrub = scrub_stale_template_products(doc, study_ctx)
    if scrub.get("remaining"):
        result.output_path.unlink(missing_ok=True)
        raise ValidationError(
            "В шаблоне остался пример Бозутиниб/Бозулиф — нет замены из canonical product",
            field="stale_template_product",
            details=scrub,
        )
    # Phase 30.2: never emit raw internal enums (e.g. ACCEPTED_CALCULATION) in final DOCX
    technical_scrub = scrub_docx_technical_enums(doc)
    # Bind filename to artifact id for stable storage_key
    safe_name = f"{artifact_id}.docx"
    file_path = abs_path / safe_name
    doc.save(str(file_path))
    if result.output_path != file_path and result.output_path.exists():
        try:
            result.output_path.unlink(missing_ok=True)
        except OSError:
            pass

    xml_scrub = scrub_contamination_xml_package(file_path, study_ctx)

    # Tertiary: full DOCX contamination scan — must be clean for non-bosutinib studies
    contamination_scan = assert_docx_clean_or_raise(file_path, study_ctx)

    raw = file_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    rel_key = f"{org_part}/{study_key}/{safe_name}"

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
        decision_set=decision_set,
        statistics_version=str(statistics_version) if statistics_version else None,
        sample_size_version=str(sample_size_version) if sample_size_version else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    append_audit(
        study_key,
        event="DOCX_ARTIFACT_CREATED",
        who=created_by,
        what=artifact_id,
        new_value={
            "sha256": sha,
            "template_version": result.template_version or TEMPLATE_VERSION,
            "generator_version": result.generator_version or DOCX_GENERATOR_VERSION,
            "snapshot_id": snap_id,
            "statistics_version": statistics_version,
            "sample_size_version": sample_size_version,
            "scrub": scrub,
            "contamination_clear": contamination_clear,
            "contamination_xml_scrub": xml_scrub,
            "contamination_scan": contamination_scan,
            "technical_enum_scrub": technical_scrub,
            "renderer": "docx_renderer.render_protocol_docx",
        },
        source=protocol_id,
    )
    out = _serialize_artifact(row)
    out["template_version"] = result.template_version or TEMPLATE_VERSION
    out["generator_version"] = result.generator_version or DOCX_GENERATOR_VERSION
    out["renderer"] = "docx_renderer.render_protocol_docx"
    out["template_id"] = profile.template_id
    out["scrub"] = scrub
    out["contamination_clear"] = contamination_clear
    out["contamination_xml_scrub"] = xml_scrub
    out["contamination_scan"] = contamination_scan
    out["technical_enum_scrub"] = technical_scrub
    out["section_traceability"] = build_section_traceability(study_key)
    out["sections_assembled"] = len(protocol_payload.get("sections") or [])
    out["tables_assembled"] = len(protocol_payload.get("tables") or [])
    return out


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

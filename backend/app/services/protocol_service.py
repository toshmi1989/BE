"""Protocol assembly service — persists ProtocolDraft from Study context."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.constants import RULES_CATALOG_VERSION
from app.domain.exceptions import NotFoundError
from app.domain.protocol_assembly import assemble_protocol
from app.domain.protocol_sections import SECTION_BY_CODE
from app.models import Project
from app.models.protocol import (
    ProtocolBuildReport,
    ProtocolDraft,
    ProtocolReference,
    ProtocolSection,
    ProtocolTable,
)
from app.schemas.phase8 import (
    ProtocolBuildReportOut,
    ProtocolDraftOut,
    ProtocolPreviewOut,
    ProtocolSectionOut,
    ProtocolTableOut,
)
from app.services import validation_service as validation


def _serialize(draft: ProtocolDraft) -> ProtocolDraftOut:
    return ProtocolDraftOut.model_validate(draft)


def _latest_draft(db: Session, project_id: UUID) -> ProtocolDraft | None:
    return (
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


def _persist_assembly(db: Session, project_id: UUID, assembled: dict) -> ProtocolDraft:
    # Replace previous drafts for project (single active draft)
    existing = (
        db.execute(select(ProtocolDraft).where(ProtocolDraft.project_id == project_id))
        .scalars()
        .all()
    )
    for row in existing:
        db.delete(row)
    db.flush()

    draft = ProtocolDraft(
        project_id=project_id,
        protocol_version=assembled["protocol_version"],
        template_version=assembled["template_version"],
        rules_version=assembled["rules_version"],
        generator_version=assembled["generator_version"],
        status=assembled["status"],
        canonical_fingerprint=assembled.get("canonical_fingerprint"),
        consistency_snapshot=assembled.get("consistency_snapshot"),
    )
    db.add(draft)
    db.flush()

    for s in assembled["sections"]:
        db.add(
            ProtocolSection(
                protocol_id=draft.id,
                section_code=s["section_code"],
                title=s["title"],
                order=s["order"],
                parent_section=s.get("parent_section"),
                status=s["status"],
                generation_status=s["generation_status"],
                content_blocks=s.get("content_blocks") or [],
                source_ids=s.get("source_ids") or [],
                warnings=s.get("warnings") or [],
                template_key=s.get("template_key"),
            )
        )

    for t in assembled["tables"]:
        db.add(
            ProtocolTable(
                protocol_id=draft.id,
                section_code=t["section_code"],
                table_key=t["table_key"],
                title=t["title"],
                order=t["order"],
                columns=t.get("columns") or [],
                rows=t.get("rows") or [],
                source_ids=t.get("source_ids") or [],
                status=t.get("status") or "GENERATED",
                display_number=t.get("display_number"),
            )
        )

    for r in assembled["references"]:
        db.add(
            ProtocolReference(
                protocol_id=draft.id,
                source_section=r["source_section"],
                target_type=r["target_type"],
                target_id=r["target_id"],
                display_text=r.get("display_text"),
            )
        )

    report = assembled["build_report"]
    db.add(
        ProtocolBuildReport(
            protocol_id=draft.id,
            generated_sections=report.get("generated_sections") or [],
            unresolved_fields=report.get("unresolved_fields") or [],
            blocking_issues=report.get("blocking_issues") or [],
            warnings=report.get("warnings") or [],
            source_count=int(report.get("source_count") or 0),
            calculated_values=report.get("calculated_values") or [],
            expert_verified_values=report.get("expert_verified_values") or [],
            extras={
                "table_count": report.get("table_count"),
                "reference_count": report.get("reference_count"),
                "snapshot_fingerprint": report.get("snapshot_fingerprint"),
                "schema_version": report.get("schema_version"),
            },
        )
    )
    db.commit()

    draft = _latest_draft(db, project_id)
    assert draft is not None
    return draft


def build_protocol(db: Session, project_id: UUID, *, protocol_version: str = "1") -> ProtocolDraftOut:
    if db.get(Project, project_id) is None:
        raise NotFoundError("Project not found", field="project_id")

    # Run validation first
    validation_run = validation.run_validation(db, project_id)
    blocking = bool(validation_run.summary.blocking)
    issues = [i.model_dump() for i in validation_run.issues]

    ctx = validation.build_project_context(db, project_id)
    # Enrich evidence summary lightly
    ctx.setdefault("evidence_summary", {})
    ctx["evidence_summary"]["count"] = ctx["evidence_summary"].get("count", 0)

    assembled = assemble_protocol(
        ctx,
        blocking_validation=blocking,
        validation_issues=issues,
        rules_version=RULES_CATALOG_VERSION,
        protocol_version=protocol_version,
    )
    draft = _persist_assembly(db, project_id, assembled)
    return _serialize(draft)


def get_protocol(db: Session, project_id: UUID) -> ProtocolDraftOut:
    draft = _latest_draft(db, project_id)
    if draft is None:
        raise NotFoundError("Protocol draft not found", field="protocol_id")
    return _serialize(draft)


def list_sections(db: Session, project_id: UUID) -> list[ProtocolSectionOut]:
    draft = _latest_draft(db, project_id)
    if draft is None:
        raise NotFoundError("Protocol draft not found", field="protocol_id")
    return [ProtocolSectionOut.model_validate(s) for s in draft.sections]


def get_build_report(db: Session, project_id: UUID) -> ProtocolBuildReportOut:
    draft = _latest_draft(db, project_id)
    if draft is None or draft.build_report is None:
        raise NotFoundError("Protocol build report not found", field="protocol_id")
    return ProtocolBuildReportOut.model_validate(draft.build_report)


def rebuild_section(db: Session, project_id: UUID, section_code: str) -> ProtocolDraftOut:
    if section_code not in SECTION_BY_CODE:
        raise NotFoundError(f"Unknown section_code: {section_code}", field="section_code")
    # Full rebuild keeps cross-section determinism (section deps).
    return build_protocol(db, project_id)


def preview_protocol(db: Session, project_id: UUID) -> ProtocolPreviewOut:
    draft = _latest_draft(db, project_id)
    if draft is None:
        raise NotFoundError("Protocol draft not found", field="protocol_id")

    by_parent: dict[str | None, list] = {}
    for s in draft.sections:
        by_parent.setdefault(s.parent_section, []).append(s)

    def node(sec: ProtocolSection) -> dict:
        children = [node(c) for c in by_parent.get(sec.section_code, [])]
        return {
            "section_code": sec.section_code,
            "title": sec.title,
            "status": sec.status,
            "generation_status": sec.generation_status,
            "content_blocks": sec.content_blocks,
            "source_ids": sec.source_ids,
            "warnings": sec.warnings,
            "children": children,
        }

    roots = by_parent.get(None, [])
    # SYNOPSIS has parent None; also numbered roots
    tree = [node(s) for s in sorted(roots, key=lambda x: x.order)]
    report = draft.build_report
    return ProtocolPreviewOut(
        protocol_id=draft.id,
        status=draft.status,
        tree=tree,
        tables=[ProtocolTableOut.model_validate(t) for t in draft.tables],
        unresolved_fields=list(report.unresolved_fields) if report else [],
        blocking_issues=list(report.blocking_issues) if report else [],
        warnings=list(report.warnings) if report else [],
    )

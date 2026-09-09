"""Phase 12A.1 — knowledge rules, expert decisions, proposals, QA."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.criteria_rules import evaluate_criteria
from app.domain.design_decision_engine import DesignDecisionEngine
from app.domain.exceptions import NotFoundError, ValidationError
from app.domain.knowledge_constants import (
    EXPERT_DECISION_TYPES,
    KNOWLEDGE_GAP_IMPORTANCE,
    KNOWLEDGE_GAP_STATUSES,
    KNOWLEDGE_RULE_DOMAINS,
    KNOWLEDGE_RULE_STATUSES,
    REGULATORY_BASIS_STATUSES,
)
from app.domain.knowledge_seed import FOUNDATION_KNOWLEDGE_GAPS, list_seed_rules
from app.domain.knowledge_transitions import (
    EXPERT_DECISION_CREATE_STATUSES,
    assert_knowledge_rule_transition,
    assert_verified_provenance,
)
from app.domain.pk_semantic import propose_analyte_selection, standard_pk_profile
from app.domain.protocol_qa import compare_identity_maps, run_protocol_qa
from app.domain.sampling_rules import CompatibilitySamplingPointGenerator, evaluate_sampling_plan
from app.models import Project
from app.models.expert_decision import ExpertDecisionRecord
from app.models.knowledge_gap import KnowledgeGapRecord
from app.models.knowledge_rule import KnowledgeRuleRecord
from app.models.protocol_comparison import PreviousProtocolComparisonRecord, ProtocolDiffItemRecord
from app.models.protocol_qa import ProtocolQAFindingRecord, ProtocolQARunRecord
from app.models.regulatory_basis import RegulatoryBasisRecord
from app.schemas.knowledge import (
    DecisionActionBody,
    ExpertDecisionCreate,
    ExpertDecisionOut,
    KnowledgeGapCreate,
    KnowledgeGapOut,
    KnowledgeGapResolve,
    KnowledgeRuleCreate,
    KnowledgeRuleOut,
    KnowledgeRuleUpdate,
    ProposalOut,
    ProtocolComparisonOut,
    ProtocolQARunOut,
    RegulatoryBasisCreate,
    RegulatoryBasisOut,
)
from app.services.provenance import bump_entity_version
from app.services.validation_service import build_project_context


def _get_project(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", field="project_id")
    return project


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------


def seed_knowledge_rules(db: Session) -> list[KnowledgeRuleOut]:
    """Upsert global (project_id=None) rules from seed catalog."""
    seeds = list_seed_rules()
    by_code = {
        r.rule_code: r
        for r in db.execute(
            select(KnowledgeRuleRecord).where(KnowledgeRuleRecord.project_id.is_(None))
        )
        .scalars()
        .all()
    }
    out: list[KnowledgeRuleRecord] = []
    for seed in seeds:
        code = seed["rule_code"]
        row = by_code.get(code)
        if row is None:
            row = KnowledgeRuleRecord(
                project_id=None,
                rule_code=code,
                name=seed["name"],
                domain=seed["domain"],
                description=seed["description"],
                condition_expression=seed.get("condition_expression"),
                action_definition=dict(seed.get("action_definition") or {}),
                priority=int(seed.get("priority") or 100),
                status="PROPOSED",
                requires_expert_confirmation=True,
                source_ids=[],
                evidence_claim_ids=[],
                version="1",
            )
            db.add(row)
        else:
            row.name = seed["name"]
            row.domain = seed["domain"]
            row.description = seed["description"]
            row.condition_expression = seed.get("condition_expression")
            row.action_definition = dict(seed.get("action_definition") or {})
            row.priority = int(seed.get("priority") or 100)
            # Hardening: do not silently downgrade VERIFIED/REJECTED on re-seed
            if row.status not in {"VERIFIED", "REJECTED"}:
                row.status = "PROPOSED"
                row.requires_expert_confirmation = True
            bump_entity_version(row)
        out.append(row)
    db.commit()
    for row in out:
        db.refresh(row)
    return [KnowledgeRuleOut.model_validate(r) for r in out]


def ensure_foundation_gaps(db: Session, project_id: UUID) -> list[KnowledgeGapOut]:
    """Ensure FOUNDATION_KNOWLEDGE_GAPS exist for a project (idempotent by question)."""
    _get_project(db, project_id)
    existing = {
        g.question: g
        for g in db.execute(
            select(KnowledgeGapRecord).where(KnowledgeGapRecord.project_id == project_id)
        )
        .scalars()
        .all()
    }
    created: list[KnowledgeGapRecord] = []
    for gap in FOUNDATION_KNOWLEDGE_GAPS:
        q = gap["question"]
        if q in existing:
            continue
        row = KnowledgeGapRecord(
            project_id=project_id,
            domain=gap["domain"],
            question=q,
            description=gap.get("description"),
            importance=gap.get("importance") or "MEDIUM",
            blocking=bool(gap.get("blocking")),
            status="OPEN",
            related_rule_id=gap.get("related_rule_id"),
            related_decision_type=gap.get("related_decision_type"),
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return [KnowledgeGapOut.model_validate(r) for r in created]


# ---------------------------------------------------------------------------
# Knowledge rules
# ---------------------------------------------------------------------------


def list_knowledge_rules(
    db: Session, *, project_id: UUID | None = None, domain: str | None = None
) -> list[KnowledgeRuleOut]:
    stmt = select(KnowledgeRuleRecord).order_by(KnowledgeRuleRecord.rule_code.asc())
    if project_id is not None:
        stmt = stmt.where(
            (KnowledgeRuleRecord.project_id == project_id) | (KnowledgeRuleRecord.project_id.is_(None))
        )
    if domain is not None:
        stmt = stmt.where(KnowledgeRuleRecord.domain == domain)
    rows = db.execute(stmt).scalars().all()
    return [KnowledgeRuleOut.model_validate(r) for r in rows]


def get_knowledge_rule(db: Session, rule_id: UUID) -> KnowledgeRuleOut:
    row = db.get(KnowledgeRuleRecord, rule_id)
    if row is None:
        raise NotFoundError("Knowledge rule not found", field="id")
    return KnowledgeRuleOut.model_validate(row)


def create_knowledge_rule(db: Session, payload: KnowledgeRuleCreate) -> KnowledgeRuleOut:
    if payload.domain not in KNOWLEDGE_RULE_DOMAINS:
        raise ValidationError(f"Invalid domain: {payload.domain}", field="domain")
    if payload.status not in KNOWLEDGE_RULE_STATUSES:
        raise ValidationError(f"Invalid status: {payload.status}", field="status")
    if payload.status == "VERIFIED":
        assert_verified_provenance(
            regulatory_basis_id=payload.regulatory_basis_id,
            evidence_claim_ids=list(payload.evidence_claim_ids or []),
            source_ids=list(payload.source_ids or []),
        )
    if payload.project_id is not None:
        _get_project(db, payload.project_id)
    existing = db.execute(
        select(KnowledgeRuleRecord).where(KnowledgeRuleRecord.rule_code == payload.rule_code)
    ).scalar_one_or_none()
    if existing is not None:
        raise ValidationError(f"rule_code already exists: {payload.rule_code}", field="rule_code")
    row = KnowledgeRuleRecord(
        project_id=payload.project_id,
        rule_code=payload.rule_code,
        name=payload.name,
        domain=payload.domain,
        description=payload.description,
        condition_expression=payload.condition_expression,
        action_definition=dict(payload.action_definition or {}),
        priority=payload.priority,
        status=payload.status,
        requires_expert_confirmation=payload.requires_expert_confirmation,
        regulatory_basis_id=payload.regulatory_basis_id,
        source_ids=list(payload.source_ids or []),
        evidence_claim_ids=list(payload.evidence_claim_ids or []),
        version=payload.version,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return KnowledgeRuleOut.model_validate(row)


def patch_knowledge_rule(
    db: Session, rule_id: UUID, payload: KnowledgeRuleUpdate
) -> KnowledgeRuleOut:
    row = db.get(KnowledgeRuleRecord, rule_id)
    if row is None:
        raise NotFoundError("Knowledge rule not found", field="id")
    data = payload.model_dump(exclude_unset=True)
    if "domain" in data and data["domain"] not in KNOWLEDGE_RULE_DOMAINS:
        raise ValidationError(f"Invalid domain: {data['domain']}", field="domain")
    if "status" in data and data["status"] not in KNOWLEDGE_RULE_STATUSES:
        raise ValidationError(f"Invalid status: {data['status']}", field="status")
    new_status = data.get("status", row.status)
    if "status" in data and data["status"] != row.status:
        assert_knowledge_rule_transition(row.status, data["status"])
    # Apply fields first so provenance check sees merged state
    for key, value in data.items():
        setattr(row, key, value)
    if new_status == "VERIFIED":
        assert_verified_provenance(
            regulatory_basis_id=row.regulatory_basis_id,
            evidence_claim_ids=list(row.evidence_claim_ids or []),
            source_ids=list(row.source_ids or []),
        )
    if "status" in data and data["status"] in {"VERIFIED", "REJECTED"}:
        row.reviewed_at = _now()
    bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return KnowledgeRuleOut.model_validate(row)


# ---------------------------------------------------------------------------
# Expert decisions
# ---------------------------------------------------------------------------


def list_expert_decisions(
    db: Session, *, project_id: UUID | None = None
) -> list[ExpertDecisionOut]:
    stmt = select(ExpertDecisionRecord).order_by(ExpertDecisionRecord.created_at.asc())
    if project_id is not None:
        _get_project(db, project_id)
        stmt = stmt.where(ExpertDecisionRecord.project_id == project_id)
    rows = db.execute(stmt).scalars().all()
    return [ExpertDecisionOut.model_validate(r) for r in rows]


def get_expert_decision(db: Session, decision_id: UUID) -> ExpertDecisionOut:
    row = db.get(ExpertDecisionRecord, decision_id)
    if row is None:
        raise NotFoundError("Expert decision not found", field="id")
    return ExpertDecisionOut.model_validate(row)


def create_expert_decision(db: Session, payload: ExpertDecisionCreate) -> ExpertDecisionOut:
    _get_project(db, payload.project_id)
    if payload.decision_type not in EXPERT_DECISION_TYPES:
        raise ValidationError(f"Invalid decision_type: {payload.decision_type}", field="decision_type")
    # Hardening: client cannot create APPROVED/REJECTED/SUPERSEDED directly
    if payload.status not in EXPERT_DECISION_CREATE_STATUSES:
        raise ValidationError(
            "ExpertDecision must be created as PROPOSED; use approve/reject endpoints",
            field="status",
        )
    row = ExpertDecisionRecord(
        project_id=payload.project_id,
        study_id=payload.study_id,
        decision_type=payload.decision_type,
        target_entity_type=payload.target_entity_type,
        target_entity_id=payload.target_entity_id,
        proposed_value=dict(payload.proposed_value or {}),
        final_value=None,  # never accept client final_value on create
        rationale=payload.rationale,
        status="PROPOSED",
        evidence_claim_ids=list(payload.evidence_claim_ids or []),
        regulatory_basis_ids=list(payload.regulatory_basis_ids or []),
        previous_decision_id=payload.previous_decision_id,
        version=payload.version,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ExpertDecisionOut.model_validate(row)


def _append_audit_note(row: ExpertDecisionRecord, body: DecisionActionBody, action: str) -> None:
    notes: list[str] = []
    if body.rationale:
        notes.append(body.rationale)
    if body.decided_by:
        notes.append(f"[{action} by {body.decided_by}]")
    if notes:
        extra = " | ".join(notes)
        row.rationale = f"{row.rationale}\n---\n{extra}" if row.rationale else extra


def approve_decision(
    db: Session, decision_id: UUID, body: DecisionActionBody | None = None
) -> ExpertDecisionOut:
    """Approve decision. Does NOT mutate Study/Design ORM — ExpertDecision is the decision state."""
    body = body or DecisionActionBody()
    row = db.get(ExpertDecisionRecord, decision_id)
    if row is None:
        raise NotFoundError("Expert decision not found", field="id")
    if row.status not in {"PROPOSED", "REJECTED"}:
        raise ValidationError(
            f"Cannot approve decision in status {row.status}", field="status"
        )

    # Supersede previous APPROVED for same type + target
    prev_stmt = select(ExpertDecisionRecord).where(
        ExpertDecisionRecord.project_id == row.project_id,
        ExpertDecisionRecord.decision_type == row.decision_type,
        ExpertDecisionRecord.target_entity_type == row.target_entity_type,
        ExpertDecisionRecord.status == "APPROVED",
        ExpertDecisionRecord.id != row.id,
    )
    if row.target_entity_id is None:
        prev_stmt = prev_stmt.where(ExpertDecisionRecord.target_entity_id.is_(None))
    else:
        prev_stmt = prev_stmt.where(ExpertDecisionRecord.target_entity_id == row.target_entity_id)

    prev_rows = list(db.execute(prev_stmt).scalars().all())
    for prev in prev_rows:
        prev.status = "SUPERSEDED"
        bump_entity_version(prev)
    if prev_rows and row.previous_decision_id is None:
        # Link to most recently created superseded decision
        newest = max(prev_rows, key=lambda p: p.created_at)
        row.previous_decision_id = newest.id

    row.status = "APPROVED"
    row.decided_at = _now()
    if body.decided_by:
        row.decided_by = body.decided_by
    if row.final_value is None:
        row.final_value = dict(row.proposed_value or {})
    _append_audit_note(row, body, "APPROVED")
    bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return ExpertDecisionOut.model_validate(row)


def reject_decision(
    db: Session, decision_id: UUID, body: DecisionActionBody | None = None
) -> ExpertDecisionOut:
    body = body or DecisionActionBody()
    row = db.get(ExpertDecisionRecord, decision_id)
    if row is None:
        raise NotFoundError("Expert decision not found", field="id")
    if row.status not in {"PROPOSED", "APPROVED"}:
        raise ValidationError(
            f"Cannot reject decision in status {row.status}", field="status"
        )
    row.status = "REJECTED"
    row.decided_at = _now()
    if body.decided_by:
        row.decided_by = body.decided_by
    _append_audit_note(row, body, "REJECTED")
    bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return ExpertDecisionOut.model_validate(row)


# ---------------------------------------------------------------------------
# Knowledge gaps
# ---------------------------------------------------------------------------


def list_knowledge_gaps(
    db: Session, *, project_id: UUID | None = None, status: str | None = None
) -> list[KnowledgeGapOut]:
    stmt = select(KnowledgeGapRecord).order_by(KnowledgeGapRecord.created_at.asc())
    if project_id is not None:
        _get_project(db, project_id)
        stmt = stmt.where(KnowledgeGapRecord.project_id == project_id)
    if status is not None:
        stmt = stmt.where(KnowledgeGapRecord.status == status)
    rows = db.execute(stmt).scalars().all()
    return [KnowledgeGapOut.model_validate(r) for r in rows]


def get_knowledge_gap(db: Session, gap_id: UUID) -> KnowledgeGapOut:
    row = db.get(KnowledgeGapRecord, gap_id)
    if row is None:
        raise NotFoundError("Knowledge gap not found", field="id")
    return KnowledgeGapOut.model_validate(row)


def create_knowledge_gap(db: Session, payload: KnowledgeGapCreate) -> KnowledgeGapOut:
    if payload.importance not in KNOWLEDGE_GAP_IMPORTANCE:
        raise ValidationError(f"Invalid importance: {payload.importance}", field="importance")
    if payload.status not in KNOWLEDGE_GAP_STATUSES:
        raise ValidationError(f"Invalid status: {payload.status}", field="status")
    if payload.project_id is not None:
        _get_project(db, payload.project_id)
    row = KnowledgeGapRecord(
        project_id=payload.project_id,
        domain=payload.domain,
        question=payload.question,
        description=payload.description,
        importance=payload.importance,
        blocking=payload.blocking,
        status=payload.status,
        related_rule_id=payload.related_rule_id,
        related_decision_type=payload.related_decision_type,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return KnowledgeGapOut.model_validate(row)


def resolve_knowledge_gap(
    db: Session, gap_id: UUID, payload: KnowledgeGapResolve
) -> KnowledgeGapOut:
    row = db.get(KnowledgeGapRecord, gap_id)
    if row is None:
        raise NotFoundError("Knowledge gap not found", field="id")
    status = payload.status or "RESOLVED"
    if status not in {"RESOLVED", "DISMISSED"}:
        raise ValidationError(f"Invalid resolve status: {status}", field="status")
    row.status = status
    row.resolution = payload.resolution
    row.resolved_by = payload.resolved_by
    row.resolved_at = _now()
    bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return KnowledgeGapOut.model_validate(row)


# ---------------------------------------------------------------------------
# Regulatory basis
# ---------------------------------------------------------------------------


def list_regulatory_bases(
    db: Session, *, project_id: UUID | None = None
) -> list[RegulatoryBasisOut]:
    stmt = select(RegulatoryBasisRecord).order_by(RegulatoryBasisRecord.created_at.asc())
    if project_id is not None:
        stmt = stmt.where(
            (RegulatoryBasisRecord.project_id == project_id)
            | (RegulatoryBasisRecord.project_id.is_(None))
        )
    rows = db.execute(stmt).scalars().all()
    return [RegulatoryBasisOut.model_validate(r) for r in rows]


def create_regulatory_basis(db: Session, payload: RegulatoryBasisCreate) -> RegulatoryBasisOut:
    if payload.status not in REGULATORY_BASIS_STATUSES:
        raise ValidationError(f"Invalid status: {payload.status}", field="status")
    if payload.project_id is not None:
        _get_project(db, payload.project_id)
    if payload.status == "VERIFIED":
        if not payload.document_identifier or not payload.section_reference:
            raise ValidationError(
                "VERIFIED RegulatoryBasis requires document_identifier and section_reference",
                field="status",
            )
        if payload.source_id is None and not payload.document_identifier:
            raise ValidationError(
                "VERIFIED RegulatoryBasis requires source_id or document_identifier",
                field="source_id",
            )
    if payload.source_id is not None and payload.project_id is not None:
        from app.models.source import Source

        src = db.get(Source, payload.source_id)
        if src is None or (src.project_id is not None and src.project_id != payload.project_id):
            # If Source has no project_id match — reject fake citations
            if src is None:
                raise ValidationError(
                    "RegulatoryBasis source_id does not reference an existing Source",
                    field="source_id",
                )
    row = RegulatoryBasisRecord(
        project_id=payload.project_id,
        title=payload.title,
        source_id=payload.source_id,
        document_identifier=payload.document_identifier,
        section_reference=payload.section_reference,
        page_reference=payload.page_reference,
        paragraph_reference=payload.paragraph_reference,
        jurisdiction=payload.jurisdiction,
        effective_date=payload.effective_date,
        status=payload.status,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return RegulatoryBasisOut.model_validate(row)


# ---------------------------------------------------------------------------
# Domain proposals (no Study/Design mutation)
# ---------------------------------------------------------------------------


def propose_design(db: Session, project_id: UUID, body: dict[str, Any] | None = None) -> ProposalOut:
    _get_project(db, project_id)
    body = dict(body or {})
    ctx = build_project_context(db, project_id)
    design = ctx.get("design") or {}
    food = ctx.get("food") or {}
    cv_sel = ctx.get("cv_selection") or {}
    washout = ctx.get("washout") or {}

    def pick(key: str, *fallbacks: Any) -> Any:
        if key in body:
            return body[key]
        for fb in fallbacks:
            if fb is not None:
                return fb
        return None

    result = DesignDecisionEngine().propose(
        cv_intra_cmax=pick("cv_intra_cmax", cv_sel.get("cv_intra_cmax")),
        cv_intra_auc=pick("cv_intra_auc", cv_sel.get("cv_intra_auc")),
        ci_cmax=pick("ci_cmax"),
        ci_auc=pick("ci_auc"),
        half_life=pick("half_life", washout.get("half_life"), washout.get("t_half")),
        food_condition=pick(
            "food_condition", food.get("condition"), design.get("food_condition")
        ),
        endogenous_compound=pick("endogenous_compound"),
        variability_indication=pick("variability_indication"),
        long_half_life_indicated=pick("long_half_life_indicated"),
        evidence_claim_ids=body.get("evidence_claim_ids"),
        regulatory_basis_ids=body.get("regulatory_basis_ids"),
    )
    return ProposalOut(**result.to_dict())


def evaluate_sampling(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> ProposalOut:
    _get_project(db, project_id)
    body = dict(body or {})
    ctx = build_project_context(db, project_id)
    sampling = ctx.get("sampling") or {}
    points = body.get("points")
    if points is None:
        points = list(sampling.get("points") or [])
    result = evaluate_sampling_plan(
        points=points,
        tmax_h=body.get("tmax_h"),
        half_life_h=body.get("half_life_h") or body.get("half_life"),
        auc_t_over_inf=body.get("auc_t_over_inf"),
        evidence_ids=body.get("evidence_ids"),
    )
    return ProposalOut(**result.to_dict())


def propose_sampling(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> ProposalOut:
    _get_project(db, project_id)
    body = dict(body or {})
    ctx = build_project_context(db, project_id)
    sampling = ctx.get("sampling") or {}
    existing = body.get("existing_points")
    if existing is None:
        existing = list(sampling.get("points") or [])
    result = CompatibilitySamplingPointGenerator().propose(
        existing_points=existing,
        recommend_result=body.get("recommend_result"),
        evidence_ids=body.get("evidence_ids"),
    )
    return ProposalOut(**result.to_dict())


def propose_analytes(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> ProposalOut:
    _get_project(db, project_id)
    body = dict(body or {})
    ctx = build_project_context(db, project_id)
    analytes = ctx.get("analytes") or []
    parent_present = body.get("parent_present")
    if parent_present is None:
        parent_present = any(
            (a or {}).get("role") in {None, "PARENT", "parent"} or (a or {}).get("is_parent")
            for a in analytes
        ) or bool(analytes)
    metabolites = body.get("metabolites")
    if metabolites is None:
        metabolites = [
            (a or {}).get("name") or (a or {}).get("code")
            for a in analytes
            if (a or {}).get("role") in {"METABOLITE", "metabolite"}
        ]
        metabolites = [m for m in metabolites if m]
    result = propose_analyte_selection(
        parent_present=bool(parent_present),
        metabolites=list(metabolites or []),
        pharmacological_relevance=body.get("pharmacological_relevance"),
        evidence_claim_ids=body.get("evidence_claim_ids"),
        regulatory_basis_ids=body.get("regulatory_basis_ids"),
    )
    return ProposalOut(**result.to_dict())


def propose_pk_parameters(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> ProposalOut:
    _get_project(db, project_id)
    _ = body
    result = standard_pk_profile()
    return ProposalOut(**result.to_dict())


def evaluate_criteria_for_project(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> ProposalOut:
    _get_project(db, project_id)
    body = dict(body or {})
    result = evaluate_criteria(
        smpc_evidence_claim_ids=body.get("smpc_evidence_claim_ids"),
        has_cyp_mentions=bool(body.get("has_cyp_mentions")),
        has_contraindications=bool(body.get("has_contraindications")),
        has_smoking_enzyme_link=bool(body.get("has_smoking_enzyme_link")),
        contraception_days_from_smpc=body.get("contraception_days_from_smpc"),
        tmax_h=body.get("tmax_h"),
    )
    return ProposalOut(**result.to_dict())


# ---------------------------------------------------------------------------
# Protocol QA
# ---------------------------------------------------------------------------


def _qa_summary(findings: list[Any]) -> dict[str, Any]:
    by_sev: dict[str, int] = {}
    blocking = 0
    for f in findings:
        sev = getattr(f, "severity", None) or (f.get("severity") if isinstance(f, dict) else "INFO")
        by_sev[sev] = by_sev.get(sev, 0) + 1
        if getattr(f, "blocking", None) or (isinstance(f, dict) and f.get("blocking")):
            blocking += 1
    status = "FAILED" if blocking else ("PASSED" if findings else "EMPTY")
    if findings and not blocking and by_sev.get("WARNING"):
        status = "PASSED_WITH_WARNINGS"
    return {
        "total": len(findings),
        "blocking": blocking,
        "by_severity": by_sev,
        "status": status,
    }


def run_qa(
    db: Session, project_id: UUID, body: dict[str, Any] | None = None
) -> ProtocolQARunOut:
    _get_project(db, project_id)
    body = dict(body or {})
    findings = run_protocol_qa(
        canonical=body.get("canonical") or {},
        displayed=body.get("displayed"),
        document_text=body.get("document_text"),
        previous_identity=body.get("previous_identity"),
    )
    summary = _qa_summary(findings)
    run = ProtocolQARunRecord(
        project_id=project_id,
        status=summary["status"],
        summary=summary,
    )
    db.add(run)
    db.flush()
    for f in findings:
        db.add(
            ProtocolQAFindingRecord(
                run_id=run.id,
                code=f.code,
                severity=f.severity,
                category=f.category,
                message=f.message,
                location=f.location,
                expected=f.expected,
                actual=f.actual,
                related_canonical_field=f.related_canonical_field,
                related_source=f.related_source,
                blocking=f.blocking,
                remediation=f.remediation,
                details=dict(f.details or {}),
            )
        )
    db.commit()
    run = db.execute(
        select(ProtocolQARunRecord)
        .where(ProtocolQARunRecord.id == run.id)
        .options(selectinload(ProtocolQARunRecord.findings))
    ).scalar_one()
    return ProtocolQARunOut.model_validate(run)


def list_qa(db: Session, project_id: UUID) -> list[ProtocolQARunOut]:
    _get_project(db, project_id)
    rows = (
        db.execute(
            select(ProtocolQARunRecord)
            .where(ProtocolQARunRecord.project_id == project_id)
            .options(selectinload(ProtocolQARunRecord.findings))
            .order_by(ProtocolQARunRecord.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [ProtocolQARunOut.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Previous protocol comparison
# ---------------------------------------------------------------------------


def compare_previous_protocol(
    db: Session,
    project_id: UUID,
    previous_map: dict[str, Any],
    current_map: dict[str, Any],
    *,
    previous_protocol_id: str | None = None,
    compared_by: str | None = None,
    persist: bool = True,
) -> ProtocolComparisonOut | dict[str, Any]:
    _get_project(db, project_id)
    items = compare_identity_maps(previous=previous_map or {}, current=current_map or {})
    if not persist:
        return {
            "project_id": str(project_id),
            "previous_protocol_id": previous_protocol_id,
            "compared_by": compared_by,
            "status": "COMPLETED",
            "diff_items": [i.to_dict() for i in items],
        }

    comparison = PreviousProtocolComparisonRecord(
        project_id=project_id,
        previous_protocol_id=previous_protocol_id,
        comparison_version="1",
        compared_by=compared_by,
        status="COMPLETED",
    )
    db.add(comparison)
    db.flush()
    for item in items:
        db.add(
            ProtocolDiffItemRecord(
                comparison_id=comparison.id,
                section=item.section,
                table_key=item.table,
                paragraph_or_field=item.paragraph_or_field,
                previous_value="" if item.previous_value is None else str(item.previous_value),
                current_value="" if item.current_value is None else str(item.current_value),
                diff_type=item.diff_type,
                risk_level=item.risk_level,
                reason=item.reason,
                review_status=item.review_status,
            )
        )
    db.commit()
    comparison = db.execute(
        select(PreviousProtocolComparisonRecord)
        .where(PreviousProtocolComparisonRecord.id == comparison.id)
        .options(selectinload(PreviousProtocolComparisonRecord.diff_items))
    ).scalar_one()
    return ProtocolComparisonOut.model_validate(comparison)

"""Phase 12A.1 — knowledge / expert-decision API router."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
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
    ProtocolDiffRequest,
    ProtocolQARunOut,
    QARunRequest,
    RegulatoryBasisCreate,
    RegulatoryBasisOut,
)
from app.services import knowledge_service as ks

router = APIRouter(tags=["knowledge"])


# ---- Knowledge rules ----


@router.get("/knowledge-rules", response_model=list[KnowledgeRuleOut])
def list_knowledge_rules(
    project_id: UUID | None = None,
    domain: str | None = None,
    db: Session = Depends(get_db),
) -> list[KnowledgeRuleOut]:
    return ks.list_knowledge_rules(db, project_id=project_id, domain=domain)


@router.post("/knowledge-rules", response_model=KnowledgeRuleOut, status_code=201)
def create_knowledge_rule(
    payload: KnowledgeRuleCreate, db: Session = Depends(get_db)
) -> KnowledgeRuleOut:
    return ks.create_knowledge_rule(db, payload)


@router.post("/knowledge-rules/seed", response_model=list[KnowledgeRuleOut])
def seed_knowledge_rules(
    project_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[KnowledgeRuleOut]:
    rules = ks.seed_knowledge_rules(db)
    if project_id is not None:
        ks.ensure_foundation_gaps(db, project_id)
    return rules


@router.get("/knowledge-rules/{rule_id}", response_model=KnowledgeRuleOut)
def get_knowledge_rule(rule_id: UUID, db: Session = Depends(get_db)) -> KnowledgeRuleOut:
    return ks.get_knowledge_rule(db, rule_id)


@router.patch("/knowledge-rules/{rule_id}", response_model=KnowledgeRuleOut)
def patch_knowledge_rule(
    rule_id: UUID, payload: KnowledgeRuleUpdate, db: Session = Depends(get_db)
) -> KnowledgeRuleOut:
    return ks.patch_knowledge_rule(db, rule_id, payload)


# ---- Expert decisions ----


@router.get("/expert-decisions", response_model=list[ExpertDecisionOut])
def list_expert_decisions(
    project_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ExpertDecisionOut]:
    return ks.list_expert_decisions(db, project_id=project_id)


@router.post("/expert-decisions", response_model=ExpertDecisionOut, status_code=201)
def create_expert_decision(
    payload: ExpertDecisionCreate, db: Session = Depends(get_db)
) -> ExpertDecisionOut:
    return ks.create_expert_decision(db, payload)


@router.get("/expert-decisions/{decision_id}", response_model=ExpertDecisionOut)
def get_expert_decision(
    decision_id: UUID, db: Session = Depends(get_db)
) -> ExpertDecisionOut:
    return ks.get_expert_decision(db, decision_id)


@router.post("/expert-decisions/{decision_id}/approve", response_model=ExpertDecisionOut)
def approve_expert_decision(
    decision_id: UUID,
    payload: DecisionActionBody | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ExpertDecisionOut:
    return ks.approve_decision(db, decision_id, payload)


@router.post("/expert-decisions/{decision_id}/reject", response_model=ExpertDecisionOut)
def reject_expert_decision(
    decision_id: UUID,
    payload: DecisionActionBody | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ExpertDecisionOut:
    return ks.reject_decision(db, decision_id, payload)


# ---- Knowledge gaps ----


@router.get("/knowledge-gaps", response_model=list[KnowledgeGapOut])
def list_knowledge_gaps(
    project_id: UUID | None = Query(default=None),
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[KnowledgeGapOut]:
    return ks.list_knowledge_gaps(db, project_id=project_id, status=status)


@router.post("/knowledge-gaps", response_model=KnowledgeGapOut, status_code=201)
def create_knowledge_gap(
    payload: KnowledgeGapCreate, db: Session = Depends(get_db)
) -> KnowledgeGapOut:
    return ks.create_knowledge_gap(db, payload)


@router.get("/knowledge-gaps/{gap_id}", response_model=KnowledgeGapOut)
def get_knowledge_gap(gap_id: UUID, db: Session = Depends(get_db)) -> KnowledgeGapOut:
    return ks.get_knowledge_gap(db, gap_id)


@router.post("/knowledge-gaps/{gap_id}/resolve", response_model=KnowledgeGapOut)
def resolve_knowledge_gap(
    gap_id: UUID, payload: KnowledgeGapResolve, db: Session = Depends(get_db)
) -> KnowledgeGapOut:
    return ks.resolve_knowledge_gap(db, gap_id, payload)


# ---- Regulatory bases ----


@router.get("/regulatory-bases", response_model=list[RegulatoryBasisOut])
def list_regulatory_bases(
    project_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[RegulatoryBasisOut]:
    return ks.list_regulatory_bases(db, project_id=project_id)


@router.post("/regulatory-bases", response_model=RegulatoryBasisOut, status_code=201)
def create_regulatory_basis(
    payload: RegulatoryBasisCreate, db: Session = Depends(get_db)
) -> RegulatoryBasisOut:
    return ks.create_regulatory_basis(db, payload)


# ---- Project-scoped proposals / QA / diff ----


@router.post("/projects/{project_id}/design/propose", response_model=ProposalOut)
def propose_design(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ProposalOut:
    return ks.propose_design(db, project_id, payload)


@router.post("/projects/{project_id}/sampling/evaluate", response_model=ProposalOut)
def evaluate_sampling(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ProposalOut:
    return ks.evaluate_sampling(db, project_id, payload)


@router.post("/projects/{project_id}/sampling/propose", response_model=ProposalOut)
def propose_sampling(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ProposalOut:
    return ks.propose_sampling(db, project_id, payload)


@router.post("/projects/{project_id}/pk/analytes/propose", response_model=ProposalOut)
def propose_analytes(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ProposalOut:
    return ks.propose_analytes(db, project_id, payload)


@router.post("/projects/{project_id}/pk/parameters/propose", response_model=ProposalOut)
def propose_pk_parameters(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ProposalOut:
    return ks.propose_pk_parameters(db, project_id, payload)


@router.post("/projects/{project_id}/criteria/evaluate", response_model=ProposalOut)
def evaluate_criteria(
    project_id: UUID,
    payload: dict[str, Any] | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ProposalOut:
    return ks.evaluate_criteria_for_project(db, project_id, payload)


@router.post("/projects/{project_id}/qa/run", response_model=ProtocolQARunOut)
def run_qa(
    project_id: UUID, payload: QARunRequest | None = None, db: Session = Depends(get_db)
) -> ProtocolQARunOut:
    body = payload.model_dump() if payload else {}
    return ks.run_qa(db, project_id, body)


@router.get("/projects/{project_id}/qa", response_model=list[ProtocolQARunOut])
def list_qa(project_id: UUID, db: Session = Depends(get_db)) -> list[ProtocolQARunOut]:
    return ks.list_qa(db, project_id)


@router.post("/projects/{project_id}/protocol-diff")
def protocol_diff(
    project_id: UUID, payload: ProtocolDiffRequest, db: Session = Depends(get_db)
) -> ProtocolComparisonOut | dict[str, Any]:
    return ks.compare_previous_protocol(
        db,
        project_id,
        payload.previous_map,
        payload.current_map,
        previous_protocol_id=payload.previous_protocol_id,
        compared_by=payload.compared_by,
        persist=payload.persist,
    )

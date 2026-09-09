"""Assemble decision context from Study Input Package / facts — Phase 15.0.

Never mutates Study. PROPOSED candidates are facts-with-status, not VERIFIED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.decision_classes import CRITICAL_CONFLICT_FIELDS
from app.domain.decision_models import AnalogueStudyEvidence
from app.domain.expected_pk import resolve_verified_expected_half_life, resolve_verified_expected_tmax
from app.domain.knowledge_seed import KNOWLEDGE_RULE_SEEDS
from app.domain.regulatory_interview import INTERVIEW_CLAIM_SEEDS
from app.domain.study_input_package import StudyInputPackage


@dataclass
class DecisionContext:
    study_id: str | None = None
    project_id: str | None = None
    package_id: str | None = None
    fixture_id: str | None = None
    structured_facts: dict[str, Any] = field(default_factory=dict)
    fact_statuses: dict[str, str] = field(default_factory=dict)  # field_path → candidate status
    fact_sources: dict[str, str] = field(default_factory=dict)
    open_conflicts: list[dict[str, Any]] = field(default_factory=list)
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    interview_claims: list[dict[str, Any]] = field(default_factory=list)
    expert_rules_proposed: list[dict[str, Any]] = field(default_factory=list)
    verified_rules: list[dict[str, Any]] = field(default_factory=list)
    analogue_studies: list[AnalogueStudyEvidence] = field(default_factory=list)
    previous_protocols: list[dict[str, Any]] = field(default_factory=list)
    half_life: Any = None  # verified expected t½ for planning
    tmax: Any = None  # verified expected Tmax for planning (never observed)
    cvintra: Any = None
    study_mutated: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["analogue_studies"] = [a.to_dict() for a in self.analogue_studies]
        d["study_mutated"] = False
        d["tmax_role"] = "expected_planning"
        d["observed_tmax_not_used_for_sampling"] = True
        return d

    def has_open_critical_conflict(self) -> bool:
        for c in self.open_conflicts:
            if str(c.get("status") or "OPEN") != "OPEN":
                continue
            if str(c.get("field_path")) in CRITICAL_CONFLICT_FIELDS:
                return True
        return False

    def critical_conflict_fields(self) -> list[str]:
        out = []
        for c in self.open_conflicts:
            if str(c.get("status") or "OPEN") != "OPEN":
                continue
            fp = str(c.get("field_path"))
            if fp in CRITICAL_CONFLICT_FIELDS:
                out.append(fp)
        return out

    def fact(self, path: str, *, verified_only: bool = False) -> Any:
        if verified_only and self.fact_statuses.get(path) != "VERIFIED":
            return None
        return self.structured_facts.get(path)


def build_context_from_package(
    package: StudyInputPackage,
    *,
    study_id: str | None = None,
    project_id: str | None = None,
    analogues: list[AnalogueStudyEvidence] | None = None,
) -> DecisionContext:
    facts: dict[str, Any] = {}
    statuses: dict[str, str] = {}
    sources: dict[str, str] = {}
    # Prefer SYNOPSIS / DESIGN / SMPC over checklist for non-conflict display context;
    # keep all statuses. For conflicting fields, do not pick a winner.
    conflict_fields = {
        str(c.get("field_path"))
        for c in package.conflicts
        if str(c.get("status") or "OPEN") == "OPEN"
    }
    prefer = {"SYNOPSIS": 3, "DESIGN": 2, "SMPC": 2, "CHECKLIST": 1}
    for c in package.candidates:
        if c.status == "REJECTED":
            continue
        if c.field_path in conflict_fields:
            # Do not set a single fact for open conflicts
            continue
        rank = prefer.get(c.document_type, 0)
        cur_src = sources.get(c.field_path)
        cur_rank = prefer.get(cur_src or "", -1) if cur_src else -1
        # Prefer VERIFIED; else higher source rank
        if c.field_path not in facts:
            facts[c.field_path] = c.value
            statuses[c.field_path] = c.status
            sources[c.field_path] = c.document_type
        elif c.status == "VERIFIED" and statuses.get(c.field_path) != "VERIFIED":
            facts[c.field_path] = c.value
            statuses[c.field_path] = c.status
            sources[c.field_path] = c.document_type
        elif statuses.get(c.field_path) != "VERIFIED" and rank > cur_rank:
            facts[c.field_path] = c.value
            statuses[c.field_path] = c.status
            sources[c.field_path] = c.document_type

    prev = [
        d.to_dict()
        for d in package.documents
        if d.document_type in {"PREVIOUS_PROTOCOL", "GOLDEN_PROTOCOL"}
    ]

    interviews = [
        {
            "claim_id": s.claim_id,
            "domain": s.domain,
            "field_name": s.field_name,
            "exact_text": s.exact_text,
            "normalized_claim": s.normalized_claim,
            "status": "PROPOSED",
            "evidence_type": "EXPERT_INTERVIEW",
        }
        for s in INTERVIEW_CLAIM_SEEDS
    ]

    proposed_rules = [
        {
            "rule_code": r.rule_code,
            "domain": r.domain,
            "description": r.description,
            "status": r.status,
            "evidence_type": "EXPERT_RULE",
            "action_definition": r.action_definition,
        }
        for r in KNOWLEDGE_RULE_SEEDS
        if r.status == "PROPOSED"
    ]

    return DecisionContext(
        study_id=study_id or package.study_id,
        project_id=project_id or package.project_id,
        package_id=package.package_id,
        fixture_id=package.fixture_id,
        structured_facts=facts,
        fact_statuses=statuses,
        fact_sources=sources,
        open_conflicts=[c for c in package.conflicts if str(c.get("status") or "OPEN") == "OPEN"],
        knowledge_gaps=list(package.knowledge_gaps),
        interview_claims=interviews,
        expert_rules_proposed=proposed_rules,
        verified_rules=[],  # none auto-verified
        analogue_studies=list(analogues or []),
        previous_protocols=prev,
        half_life=resolve_verified_expected_half_life(facts, statuses),
        # Expected (planning) Tmax only when VERIFIED — never invent; never use observed Tmax
        tmax=resolve_verified_expected_tmax(facts, statuses),
        cvintra=None,  # never invent CV
        study_mutated=False,
    )


def design_context_summary(ctx: DecisionContext) -> dict[str, Any]:
    f = ctx.structured_facts
    return {
        "periods": f.get("design.periods"),
        "sequences": f.get("design.sequences"),
        "groups": f.get("design.groups"),
        "randomized": f.get("design.randomized"),
        "open_label": f.get("design.open_label"),
        "crossover": f.get("design.crossover"),
        "conditions": f.get("design.conditions"),
        "randomized_n": f.get("subjects.randomized_n"),
        "note": "Current design context from structured inputs — not an approved medical decision",
    }

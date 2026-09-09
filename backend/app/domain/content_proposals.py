"""Bioanalysis / Safety / Method proposals — Phase 12A.2 (no invented defaults)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.bioanalysis_plan import BioanalysisPlan, empty_bioanalysis_plan
from app.domain.sample_processing import SampleProcessingDefinition, empty_sample_processing
from app.domain.safety_plan import SafetyPlan, empty_safety_plan


FOUNDATION_CONTENT_GAPS: tuple[dict[str, Any], ...] = (
    {
        "domain": "SAFETY",
        "question": "Standard BE safety library not yet formally verified.",
        "importance": "MEDIUM",
        "blocking": False,
        "related_rule_id": "SAFETY-01",
    },
)


@dataclass
class BioanalysisPlanProposal:
    plan: dict[str, Any]
    sample_processing: dict[str, Any]
    method_decision: dict[str, Any]
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    invented_defaults: list[str] = field(default_factory=list)  # must stay empty

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def propose_bioanalysis(
    *,
    provided: dict[str, Any] | None = None,
    evidence_claim_ids: list[str] | None = None,
) -> BioanalysisPlanProposal:
    """Propose empty/partial plan — never fill HPLC-MS/MS, LLOQ, etc."""
    provided = dict(provided or {})
    # Strip any attempt to use sentinel invented defaults
    forbidden = {"hplc-ms/ms", "hplc_ms_ms", "lc-ms/ms"}
    gaps: list[dict[str, Any]] = []
    method = provided.get("analytical_method")
    if method and str(method).strip().lower() in forbidden and not evidence_claim_ids:
        # Do not accept unsourced method name as default — clear and gap
        provided = {**provided, "analytical_method": None}
        gaps.append(
            {
                "domain": "ANALYTE",
                "question": "Bioanalysis method missing or unsourced — no HPLC-MS/MS fallback.",
                "importance": "HIGH",
                "blocking": True,
            }
        )
    plan = empty_bioanalysis_plan()
    # Apply only explicitly provided non-empty values
    for k, v in provided.items():
        if hasattr(plan, k) and v not in (None, ""):
            setattr(plan, k, v)
    if evidence_claim_ids:
        plan.source_ids = list(evidence_claim_ids)
        plan.origin = "SOURCE_DERIVED"
    plan.status = "PROPOSED"
    if plan.analytical_method in (None, ""):
        gaps.append(
            {
                "domain": "ANALYTE",
                "question": "Bioanalysis method not provided — KnowledgeGap (no method fallback).",
                "importance": "HIGH",
                "blocking": True,
            }
        )
    for field_name in plan.unresolved_fields():
        if field_name in {"lloq", "acceptance_criteria", "centrifugation", "storage_temperature"}:
            gaps.append(
                {
                    "domain": "ANALYTE",
                    "question": f"Bioanalysis field '{field_name}' unresolved — not invented.",
                    "importance": "MEDIUM",
                    "blocking": False,
                }
            )
    processing = empty_sample_processing()
    # Map known provided processing keys only
    for k in ("anticoagulant", "centrifugation", "storage", "shipping"):
        if provided.get(k):
            setattr(processing, k, provided[k])
            processing.status = "PROPOSED"
    method_decision = {
        "proposed_method": plan.analytical_method,
        "reason": "Provided by caller/evidence only — no automatic method selection",
        "evidence_claim_ids": list(evidence_claim_ids or []),
        "status": "PROPOSED" if plan.analytical_method else "UNRESOLVED",
        "requires_expert_confirmation": True,
    }
    return BioanalysisPlanProposal(
        plan=plan.to_dict(),
        sample_processing=processing.to_dict(),
        method_decision=method_decision,
        knowledge_gaps=gaps,
        invented_defaults=[],
    )


@dataclass
class SafetyPlanProposal:
    plan: dict[str, Any]
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    invented_defaults: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def propose_safety(provided: dict[str, Any] | None = None) -> SafetyPlanProposal:
    """Empty/partial safety proposal — never invent checklist items."""
    provided = dict(provided or {})
    plan = empty_safety_plan()
    for k in (
        "physical_exam",
        "vital_signs",
        "ECG",
        "laboratory_tests",
        "AE",
        "SAE",
        "pregnancy",
        "follow_up",
    ):
        if k in provided and provided[k] is not None:
            setattr(plan, k, provided[k])
    plan.status = "PROPOSED"
    plan.origin = "USER" if provided else "UNRESOLVED"
    gaps = [
        {
            "domain": "SAFETY",
            "question": "Standard BE safety library not yet formally verified.",
            "importance": "MEDIUM",
            "blocking": False,
        }
    ]
    if not plan.enabled_categories():
        gaps.append(
            {
                "domain": "SAFETY",
                "question": "SafetyPlan has no explicitly enabled categories — not inventing checklist.",
                "importance": "HIGH",
                "blocking": False,
            }
        )
    return SafetyPlanProposal(plan=plan.to_dict(), knowledge_gaps=gaps, invented_defaults=[])

"""Food / Washout / Sample-size decision proposals — Phase 12A.1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FoodDecisionProposal:
    proposed_condition: str | None = None
    meal_concept: str | None = None  # e.g. HIGH_CALORIE_CONCEPT — not numeric constants
    reasons: list[str] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)
    evidence_claim_ids: list[str] = field(default_factory=list)
    regulatory_basis: list[str] = field(default_factory=list)
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    forbidden_auto_constants: list[str] = field(
        default_factory=lambda: ["kcal", "fat_percent", "water_ml", "dose_after_meal_min"]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def propose_food(
    *,
    condition: str | None = None,
    evidence_claim_ids: list[str] | None = None,
    regulatory_basis_ids: list[str] | None = None,
    alternative_supported: bool = False,
) -> FoodDecisionProposal:
    gaps: list[dict[str, Any]] = []
    rules = ["FOOD-01"]
    reasons = ["Food determination references Decision 85 p.44 (PROPOSED)."]
    meal = None
    cond = (condition or "").upper() or None
    if cond == "FED":
        rules.append("FOOD-02")
        meal = "HIGH_CALORIE_CONCEPT"
        reasons.append(
            "Fed → standard high-calorie breakfast concept per Decision 85 p.46; numeric kcal/fat/ml not auto-filled."
        )
    if alternative_supported:
        rules.append("FOOD-03")
        reasons.append("Alternative food conditions require evidence + ExpertDecision.")
        gaps.append(
            {
                "domain": "FOOD",
                "question": "Alternative food condition needs FDA/evidence support and expert approval.",
                "importance": "HIGH",
                "blocking": True,
                "related_rule_id": "FOOD-03",
            }
        )
    if not cond:
        gaps.append(
            {
                "domain": "FOOD",
                "question": "Food condition not provided.",
                "importance": "HIGH",
                "blocking": True,
            }
        )
    return FoodDecisionProposal(
        proposed_condition=cond,
        meal_concept=meal,
        reasons=reasons,
        triggered_rules=rules,
        evidence_claim_ids=list(evidence_claim_ids or []),
        regulatory_basis=list(regulatory_basis_ids or []),
        knowledge_gaps=gaps,
    )


@dataclass
class WashoutDecisionProposal:
    half_life: float | None = None
    calculated_minimum: float | None = None
    proposed_washout: float | None = None
    unit: str = "h"
    evidence: list[str] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    notes: str = "No silent rounding — ExpertDecision(WASHOUT) for final approval."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def propose_washout(
    *,
    half_life: float | None,
    unit: str = "h",
    selected_value: float | None = None,
    evidence_ids: list[str] | None = None,
) -> WashoutDecisionProposal:
    gaps = []
    calc = None
    if half_life is not None:
        calc = float(half_life) * 5.0
    else:
        gaps.append(
            {
                "domain": "WASHOUT",
                "question": "Half-life missing for WASH-01 (5×t½) proposal.",
                "importance": "HIGH",
                "blocking": True,
                "related_rule_id": "WASH-01",
            }
        )
    proposed = selected_value if selected_value is not None else calc
    return WashoutDecisionProposal(
        half_life=half_life,
        calculated_minimum=calc,
        proposed_washout=proposed,
        unit=unit,
        evidence=list(evidence_ids or []),
        triggered_rules=["WASH-01"],
        knowledge_gaps=gaps,
    )


@dataclass
class SampleSizeDecisionProposal:
    design: str | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    proposed_defaults: dict[str, Any] = field(default_factory=dict)
    calculator_result: dict[str, Any] | None = None
    triggered_rules: list[str] = field(default_factory=list)
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    notes: str = "Wraps existing sample-size calculator; does not rewrite numerical engine."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def propose_sample_size_layer(
    *,
    design: str | None,
    cv_intra: float | None = None,
    calculator_result: dict | None = None,
    evidence_ids: list[str] | None = None,
) -> SampleSizeDecisionProposal:
    rules = ["SAMPLE-01", "SAMPLE-02", "SAMPLE-03"]
    gaps = [
        {
            "domain": "SAMPLE_SIZE",
            "question": "Final randomized N decision logic not yet specified.",
            "importance": "CRITICAL",
            "blocking": True,
            "related_decision_type": "SAMPLE_SIZE",
        }
    ]
    defaults: dict[str, Any] = {}
    if design and "CROSSOVER_2X2" in str(design).upper():
        rules.append("SAMPLE-04")
        defaults = {"power": 0.8, "alpha": 0.05}
    if design and "ADAPTIVE" in str(design).upper():
        rules.append("SAMPLE-05")
        gaps.append(
            {
                "domain": "SAMPLE_SIZE",
                "question": "Potvin B/C sample-size implementation specification not yet verified.",
                "importance": "HIGH",
                "blocking": False,
                "related_rule_id": "SAMPLE-05",
            }
        )
    if cv_intra is None:
        gaps.append(
            {
                "domain": "SAMPLE_SIZE",
                "question": "CVintra not established from literature evidence.",
                "importance": "HIGH",
                "blocking": True,
                "related_rule_id": "SAMPLE-01",
            }
        )
    return SampleSizeDecisionProposal(
        design=design,
        inputs={"cv_intra": cv_intra, "evidence_ids": list(evidence_ids or [])},
        proposed_defaults=defaults,
        calculator_result=calculator_result,
        triggered_rules=rules,
        knowledge_gaps=gaps,
    )

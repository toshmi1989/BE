"""DesignDecisionEngine — Phase 12A.1.

Proposes designs; never mutates Study. No magic thresholds for high CV / long half-life.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DesignDecisionProposal:
    proposed_design: str | None
    reasons: list[str] = field(default_factory=list)
    decision_inputs: list[dict[str, Any]] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)
    evidence_claims: list[str] = field(default_factory=list)
    regulatory_basis: list[str] = field(default_factory=list)
    confidence: float | None = None
    status: str = "PROPOSED"
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    requires_expert_confirmation: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _cv_and_ci_present(
    *,
    cv_intra_cmax: float | None,
    cv_intra_auc: float | None,
    ci_cmax: Any,
    ci_auc: Any,
) -> bool:
    has_cv = cv_intra_cmax is not None or cv_intra_auc is not None
    has_ci = ci_cmax is not None or ci_auc is not None
    return bool(has_cv and has_ci)


def propose_design(
    *,
    cv_intra_cmax: float | None = None,
    cv_intra_auc: float | None = None,
    ci_cmax: Any = None,
    ci_auc: Any = None,
    half_life: float | None = None,
    food_condition: str | None = None,
    endogenous_compound: bool | None = None,
    # Explicit indication from evidence — NOT computed from a numeric CV threshold
    variability_indication: str | None = None,  # HIGH | NOT_HIGH | UNKNOWN | None
    long_half_life_indicated: bool | None = None,  # must come from evidence/expert, not threshold
    evidence_claim_ids: list[str] | None = None,
    regulatory_basis_ids: list[str] | None = None,
) -> DesignDecisionProposal:
    evidence_claim_ids = list(evidence_claim_ids or [])
    regulatory_basis_ids = list(regulatory_basis_ids or [])
    gaps: list[dict[str, Any]] = []
    rules: list[str] = []
    reasons: list[str] = []
    inputs = [
        {"name": "cv_intra_cmax", "value": cv_intra_cmax},
        {"name": "cv_intra_auc", "value": cv_intra_auc},
        {"name": "ci_cmax", "value": ci_cmax},
        {"name": "ci_auc", "value": ci_auc},
        {"name": "half_life", "value": half_life},
        {"name": "food_condition", "value": food_condition},
        {"name": "endogenous_compound", "value": endogenous_compound},
        {"name": "variability_indication", "value": variability_indication},
        {"name": "long_half_life_indicated", "value": long_half_life_indicated},
    ]

    present = _cv_and_ci_present(
        cv_intra_cmax=cv_intra_cmax,
        cv_intra_auc=cv_intra_auc,
        ci_cmax=ci_cmax,
        ci_auc=ci_auc,
    )
    var = (variability_indication or "UNKNOWN").upper()
    proposed: str | None = None

    if present and var == "HIGH":
        proposed = "REPLICATE_2X2X4"
        rules.extend(["DESIGN-02", "DESIGN-03"])
        reasons.append(
            "CVintra/CI present and high variability indicated → propose replicate 2×2×4."
        )
        gaps.append(
            {
                "domain": "DESIGN",
                "question": "Expanded BE limits vs standard limits require separate ExpertDecision.",
                "importance": "HIGH",
                "blocking": True,
                "related_rule_id": "DESIGN-03",
            }
        )
    elif present and var in {"NOT_HIGH", "LOW", "MODERATE"}:
        proposed = "CROSSOVER_2X2"
        rules.append("DESIGN-01")
        reasons.append(
            "CVintra/CI present and variability not indicated as high → propose 2×2 crossover."
        )
    elif present and var in {"UNKNOWN", ""}:
        proposed = "CROSSOVER_2X2"
        rules.append("DESIGN-01")
        reasons.append(
            "CVintra/CI present but variability indication unclear → tentative 2×2; expert must confirm."
        )
        gaps.append(
            {
                "domain": "DESIGN",
                "question": "Variability indication (high vs not) not confirmed by evidence/expert.",
                "importance": "HIGH",
                "blocking": True,
                "related_rule_id": "DESIGN-01",
            }
        )
    else:
        proposed = "ADAPTIVE"
        rules.append("DESIGN-04")
        reasons.append("CVintra and/or 90% CI absent → propose adaptive design.")
        gaps.append(
            {
                "domain": "SAMPLE_SIZE",
                "question": "Potvin B/C sample-size implementation specification not yet verified.",
                "importance": "HIGH",
                "blocking": False,
                "related_rule_id": "SAMPLE-05",
            }
        )

    if long_half_life_indicated is True:
        rules.append("DESIGN-05")
        reasons.append(
            "Long half-life indicated → parallel design may be considered; not auto-selected."
        )
        gaps.append(
            {
                "domain": "DESIGN",
                "question": "Verified numeric definition of long half-life for parallel design is missing.",
                "importance": "HIGH",
                "blocking": False,
                "related_rule_id": "DESIGN-05",
            }
        )
        # Do not override proposed design automatically
    elif half_life is not None and long_half_life_indicated is None:
        gaps.append(
            {
                "domain": "DESIGN",
                "question": "Half-life provided but long-half-life classification not confirmed (no threshold applied).",
                "importance": "MEDIUM",
                "blocking": False,
                "related_rule_id": "DESIGN-05",
            }
        )

    rules.append("DESIGN-06")
    reasons.append("Final design must be approved via ExpertDecision.")

    conf = 0.55 if present else 0.4
    if var == "HIGH" and present:
        conf = 0.5
    if gaps and any(g.get("blocking") for g in gaps):
        conf = min(conf, 0.45)

    return DesignDecisionProposal(
        proposed_design=proposed,
        reasons=reasons,
        decision_inputs=inputs,
        triggered_rules=sorted(set(rules)),
        evidence_claims=evidence_claim_ids,
        regulatory_basis=regulatory_basis_ids,
        confidence=conf,
        status="PROPOSED",
        knowledge_gaps=gaps,
        requires_expert_confirmation=True,
    )


class DesignDecisionEngine:
    """Service wrapper — does not write Study."""

    def propose(self, **kwargs: Any) -> DesignDecisionProposal:
        return propose_design(**kwargs)

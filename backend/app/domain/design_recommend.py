"""Design recommendation service.

Accepts structured inputs only. No literature search, web, or LLM logic.
Future Research Engine may supply available_guideline_recommendation / evidence IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.constants import (
    CONFIDENCE_EXPERT_OVERRIDE,
    CONFIDENCE_GUIDELINE,
    CONFIDENCE_HEURISTIC,
    CONFIDENCE_INSUFFICIENT,
    CROSSOVER_2X2_REQUIRED_PERIODS,
    CROSSOVER_2X2_REQUIRED_SEQUENCE_COUNT,
    REPLICATE_2X2X4_TYPICAL_PERIODS,
    REPLICATE_2X2X4_TYPICAL_SEQUENCE_COUNT,
)
from app.domain.provenance import DecisionStatus, Origin


@dataclass
class DesignRecommendInput:
    available_guideline_recommendation: str | None = None
    reference_product_known: bool | None = None
    half_life: float | None = None
    variability_known: bool | None = None
    variability_level: str | None = None  # LOW | MODERATE | HIGH when known
    dosage_form: str | None = None
    route: str | None = None
    food_condition: str | None = None
    expert_override: str | None = None
    evidence_source_ids: list[str] = field(default_factory=list)


@dataclass
class DesignRecommendation:
    recommended_design: dict[str, Any] | None
    rationale: str
    confidence: float | None
    evidence_source_ids: list[str]
    status: str
    origin: str


def _crossover_skeleton(food_condition: str | None) -> dict[str, Any]:
    return {
        "type": "CROSSOVER_2X2",
        "periods": CROSSOVER_2X2_REQUIRED_PERIODS,
        "sequences": [["T", "R"], ["R", "T"]],
        "treatments": ["T", "R"],
        "randomization": True,
        "blinding": False,
        "food_condition": food_condition,
        "stage_configuration": None,
    }


def _replicate_skeleton(food_condition: str | None) -> dict[str, Any]:
    periods = REPLICATE_2X2X4_TYPICAL_PERIODS
    return {
        "type": "REPLICATE_2X2X4",
        "periods": periods,
        "sequences": [["T", "R", "T", "R"], ["R", "T", "R", "T"]][
            :REPLICATE_2X2X4_TYPICAL_SEQUENCE_COUNT
        ],
        "treatments": ["T", "R"],
        "randomization": True,
        "blinding": False,
        "food_condition": food_condition,
        "stage_configuration": None,
    }


def recommend_design(inp: DesignRecommendInput) -> DesignRecommendation:
    """Return a PROPOSED or NEEDS_REVIEW recommendation. Never auto-VERIFIED."""
    evidence = list(inp.evidence_source_ids)

    if inp.expert_override:
        design = _skeleton_for_type(inp.expert_override, inp.food_condition)
        return DesignRecommendation(
            recommended_design=design,
            rationale="Expert override supplied; recommendation awaits confirmation.",
            confidence=CONFIDENCE_EXPERT_OVERRIDE,
            evidence_source_ids=evidence,
            status=DecisionStatus.PROPOSED.value,
            origin=Origin.USER.value,
        )

    if inp.available_guideline_recommendation:
        design = _skeleton_for_type(inp.available_guideline_recommendation, inp.food_condition)
        return DesignRecommendation(
            recommended_design=design,
            rationale=(
                "Structured guideline recommendation provided as input "
                "(not fetched by Design Engine)."
            ),
            confidence=CONFIDENCE_GUIDELINE,
            evidence_source_ids=evidence,
            status=DecisionStatus.PROPOSED.value,
            origin=Origin.SOURCE_DERIVED.value,
        )

    # Heuristic path — only when enough structured facts are present; no invention.
    has_form = bool(inp.dosage_form)
    has_route = bool(inp.route)
    ref_known = inp.reference_product_known is True

    if inp.variability_known is True and (inp.variability_level or "").upper() == "HIGH":
        if has_form or has_route or ref_known:
            return DesignRecommendation(
                recommended_design=_replicate_skeleton(inp.food_condition),
                rationale=(
                    "High variability flagged in structured inputs; "
                    "replicate design proposed for expert review."
                ),
                confidence=CONFIDENCE_HEURISTIC,
                evidence_source_ids=evidence,
                status=DecisionStatus.PROPOSED.value,
                origin=Origin.RULE_DERIVED.value,
            )

    if ref_known and has_form and has_route:
        return DesignRecommendation(
            recommended_design=_crossover_skeleton(inp.food_condition),
            rationale=(
                "Reference known with dosage form and route; "
                "standard 2×2 crossover proposed (not verified)."
            ),
            confidence=CONFIDENCE_HEURISTIC,
            evidence_source_ids=evidence,
            status=DecisionStatus.PROPOSED.value,
            origin=Origin.RULE_DERIVED.value,
        )

    missing: list[str] = []
    if not inp.available_guideline_recommendation:
        missing.append("available_guideline_recommendation")
    if inp.reference_product_known is not True:
        missing.append("reference_product_known")
    if not inp.dosage_form:
        missing.append("dosage_form")
    if not inp.route:
        missing.append("route")

    return DesignRecommendation(
        recommended_design=None,
        rationale=(
            "Insufficient structured inputs for a design recommendation. "
            f"Missing or unknown: {', '.join(missing)}. "
            "Research Engine / expert input required."
        ),
        confidence=CONFIDENCE_INSUFFICIENT,
        evidence_source_ids=evidence,
        status=DecisionStatus.NEEDS_REVIEW.value,
        origin=Origin.RULE_DERIVED.value,
    )


def _skeleton_for_type(design_type: str, food_condition: str | None) -> dict[str, Any]:
    if design_type == "REPLICATE_2X2X4":
        return _replicate_skeleton(food_condition)
    if design_type == "PARALLEL":
        return {
            "type": "PARALLEL",
            "periods": 1,
            "sequences": [],
            "treatments": ["T", "R"],
            "randomization": True,
            "blinding": False,
            "food_condition": food_condition,
            "stage_configuration": None,
        }
    if design_type == "ADAPTIVE":
        return {
            "type": "ADAPTIVE",
            "periods": None,
            "sequences": [],
            "treatments": ["T", "R"],
            "randomization": True,
            "blinding": False,
            "food_condition": food_condition,
            "stage_configuration": {
                "stage_1": {"n": None},
                "interim_analysis": {"configured": True},
            },
        }
    if design_type == "CUSTOM":
        return {
            "type": "CUSTOM",
            "periods": None,
            "sequences": [],
            "treatments": [],
            "randomization": None,
            "blinding": None,
            "food_condition": food_condition,
            "stage_configuration": None,
        }
    # Default structural skeleton for CROSSOVER_2X2 and unknown mapped to crossover only
    # when explicitly requested as that type.
    return _crossover_skeleton(food_condition)


# silence unused import if sequence constants only used indirectly
_ = (CROSSOVER_2X2_REQUIRED_SEQUENCE_COUNT,)

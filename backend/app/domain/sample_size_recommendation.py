"""Phase 15.4 — Recommendation layer (never auto-decides)."""

from __future__ import annotations

from app.domain.sample_size_models import SampleSizeRecommendation


def build_recommendation(
    *,
    current_protocol_n: int | None,
    calculated_randomized_n: int | None,
    blocked: bool = False,
) -> SampleSizeRecommendation:
    """Always REQUIRES_EXPERT_DECISION unless comparing numbers for display options.

    Options are listed for the expert; none are auto-selected.
    """
    if blocked or calculated_randomized_n is None:
        return SampleSizeRecommendation(
            option="REQUIRES_EXPERT_DECISION",
            current_protocol_n=current_protocol_n,
            calculated_randomized_n=calculated_randomized_n,
            rationale="Calculation blocked or incomplete — expert decision required",
            auto_selected=False,
        )
    if current_protocol_n is None:
        return SampleSizeRecommendation(
            option="REQUIRES_EXPERT_DECISION",
            current_protocol_n=None,
            calculated_randomized_n=calculated_randomized_n,
            rationale="No current protocol N — expert must decide whether to adopt calculated N",
            auto_selected=False,
        )
    # Surface directional hint but keep option as REQUIRES_EXPERT_DECISION
    # (do not auto-choose INCREASE/DECREASE/USE_CURRENT)
    if calculated_randomized_n > current_protocol_n:
        rationale = (
            f"Calculated randomized N ({calculated_randomized_n}) > current "
            f"({current_protocol_n}). Candidate options: INCREASE_N | USE_CURRENT_N — "
            "expert must choose."
        )
    elif calculated_randomized_n < current_protocol_n:
        rationale = (
            f"Calculated randomized N ({calculated_randomized_n}) < current "
            f"({current_protocol_n}). Candidate options: DECREASE_N | USE_CURRENT_N — "
            "expert must choose."
        )
    else:
        rationale = (
            f"Calculated randomized N equals current ({current_protocol_n}). "
            "Candidate option: USE_CURRENT_N — expert must still confirm."
        )
    return SampleSizeRecommendation(
        option="REQUIRES_EXPERT_DECISION",
        current_protocol_n=current_protocol_n,
        calculated_randomized_n=calculated_randomized_n,
        rationale=rationale,
        auto_selected=False,
    )


# Exposed option catalog for UI / API contracts
AVAILABLE_RECOMMENDATION_OPTIONS = (
    "USE_CURRENT_N",
    "INCREASE_N",
    "DECREASE_N",
    "REQUIRES_EXPERT_DECISION",
)

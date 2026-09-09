"""Design structural validation — no UI magic numbers."""

from __future__ import annotations

from typing import Any

from app.domain.constants import (
    CROSSOVER_2X2_REQUIRED_PERIODS,
    CROSSOVER_2X2_REQUIRED_SEQUENCE_COUNT,
    DESIGN_TYPES,
    PARALLEL_MIN_TREATMENT_GROUPS,
    PARALLEL_REQUIRED_PERIODS,
    REPLICATE_MIN_PERIODS,
)
from app.domain.exceptions import ValidationError


def _treatment_groups(treatments: list | None, sequences: list | None) -> set[str]:
    groups: set[str] = set()
    for item in treatments or []:
        if isinstance(item, str):
            groups.add(item)
        elif isinstance(item, dict) and item.get("code"):
            groups.add(str(item["code"]))
    for seq in sequences or []:
        if isinstance(seq, list):
            for code in seq:
                groups.add(str(code))
    return groups


def validate_design_payload(
    *,
    design_type: str,
    periods: int | None,
    sequences: list | None,
    treatments: list | None = None,
    stage_configuration: dict | None = None,
) -> None:
    if design_type not in DESIGN_TYPES:
        raise ValidationError(
            f"Unsupported design type: {design_type}",
            field="type",
            details={"allowed": list(DESIGN_TYPES)},
        )

    sequences = sequences or []
    treatments = treatments or []

    if design_type == "CROSSOVER_2X2":
        if periods != CROSSOVER_2X2_REQUIRED_PERIODS:
            raise ValidationError(
                f"CROSSOVER_2X2 requires periods={CROSSOVER_2X2_REQUIRED_PERIODS}",
                field="periods",
                details={"expected": CROSSOVER_2X2_REQUIRED_PERIODS, "actual": periods},
            )
        if len(sequences) != CROSSOVER_2X2_REQUIRED_SEQUENCE_COUNT:
            raise ValidationError(
                f"CROSSOVER_2X2 requires sequence_count={CROSSOVER_2X2_REQUIRED_SEQUENCE_COUNT}",
                field="sequences",
                details={
                    "expected": CROSSOVER_2X2_REQUIRED_SEQUENCE_COUNT,
                    "actual": len(sequences),
                },
            )
        for idx, seq in enumerate(sequences):
            if not isinstance(seq, list) or len(seq) != CROSSOVER_2X2_REQUIRED_PERIODS:
                raise ValidationError(
                    "Each CROSSOVER_2X2 sequence must list one treatment per period",
                    field=f"sequences[{idx}]",
                )

    elif design_type == "PARALLEL":
        if periods != PARALLEL_REQUIRED_PERIODS:
            raise ValidationError(
                f"PARALLEL requires periods={PARALLEL_REQUIRED_PERIODS}",
                field="periods",
                details={"expected": PARALLEL_REQUIRED_PERIODS, "actual": periods},
            )
        groups = _treatment_groups(treatments, sequences)
        if len(groups) < PARALLEL_MIN_TREATMENT_GROUPS:
            raise ValidationError(
                f"PARALLEL requires at least {PARALLEL_MIN_TREATMENT_GROUPS} treatment groups",
                field="treatments",
                details={"min_groups": PARALLEL_MIN_TREATMENT_GROUPS, "actual": len(groups)},
            )

    elif design_type == "REPLICATE_2X2X4":
        if periods is None or periods < REPLICATE_MIN_PERIODS:
            raise ValidationError(
                f"REPLICATE_2X2X4 requires periods>={REPLICATE_MIN_PERIODS}",
                field="periods",
                details={"min_periods": REPLICATE_MIN_PERIODS, "actual": periods},
            )
        if len(sequences) < 2:
            raise ValidationError(
                "REPLICATE_2X2X4 requires at least 2 sequences",
                field="sequences",
            )
        for idx, seq in enumerate(sequences):
            if not isinstance(seq, list) or len(seq) != periods:
                raise ValidationError(
                    "Each replicate sequence length must equal periods",
                    field=f"sequences[{idx}]",
                )

    elif design_type == "ADAPTIVE":
        stage = stage_configuration or {}
        if not stage.get("stage_1"):
            raise ValidationError(
                "ADAPTIVE requires stage_configuration.stage_1",
                field="stage_configuration.stage_1",
            )
        interim = stage.get("interim_analysis")
        if not isinstance(interim, dict) or not interim:
            raise ValidationError(
                "ADAPTIVE requires stage_configuration.interim_analysis",
                field="stage_configuration.interim_analysis",
            )

    elif design_type == "CUSTOM":
        # Extensibility placeholder — structural checks deferred to expert rules later.
        if periods is not None and periods < 1:
            raise ValidationError("CUSTOM periods must be >= 1 when supplied", field="periods")


def design_as_dict(obj: Any) -> dict[str, Any]:
    return {
        "type": obj.type,
        "periods": obj.periods,
        "sequences": list(obj.sequences or []),
        "treatments": list(obj.treatments or []),
        "randomization": obj.randomization,
        "blinding": obj.blinding,
        "food_condition": obj.food_condition,
        "stage_configuration": obj.stage_configuration,
        "rationale": obj.rationale,
        "decision_status": obj.decision_status,
        "source_ids": list(obj.source_ids or []),
    }

from fastapi import APIRouter

from app.domain.constants import (
    CROSSOVER_2X2_REQUIRED_PERIODS,
    CROSSOVER_2X2_REQUIRED_SEQUENCE_COUNT,
    DESIGN_TYPES,
    FOOD_CONDITIONS,
    MEAL_TYPES,
    PARALLEL_MIN_TREATMENT_GROUPS,
    PARALLEL_REQUIRED_PERIODS,
    REPLICATE_2X2X4_TYPICAL_PERIODS,
    REPLICATE_MIN_PERIODS,
)

router = APIRouter(tags=["reference-data"])


@router.get("/reference-data/design")
def design_reference_data() -> dict:
    """Structural defaults for UI — sourced from domain constants, not React."""
    return {
        "design_types": list(DESIGN_TYPES),
        "food_conditions": list(FOOD_CONDITIONS),
        "meal_types": list(MEAL_TYPES),
        "templates": {
            "CROSSOVER_2X2": {
                "periods": CROSSOVER_2X2_REQUIRED_PERIODS,
                "sequence_count": CROSSOVER_2X2_REQUIRED_SEQUENCE_COUNT,
                "sequences": [["T", "R"], ["R", "T"]],
                "treatments": ["T", "R"],
            },
            "PARALLEL": {
                "periods": PARALLEL_REQUIRED_PERIODS,
                "min_treatment_groups": PARALLEL_MIN_TREATMENT_GROUPS,
                "treatments": ["T", "R"],
                "sequences": [],
            },
            "REPLICATE_2X2X4": {
                "periods": REPLICATE_2X2X4_TYPICAL_PERIODS,
                "min_periods": REPLICATE_MIN_PERIODS,
                "sequences": [["T", "R", "T", "R"], ["R", "T", "R", "T"]],
                "treatments": ["T", "R"],
            },
            "ADAPTIVE": {
                "stage_configuration": {
                    "stage_1": {"n": None},
                    "interim_analysis": {"configured": True},
                },
                "treatments": ["T", "R"],
                "sequences": [],
            },
            "CUSTOM": {
                "periods": None,
                "sequences": [],
                "treatments": [],
            },
        },
    }

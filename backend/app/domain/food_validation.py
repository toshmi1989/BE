"""Food condition validation."""

from __future__ import annotations

from app.domain.constants import FOOD_CONDITIONS, MEAL_TYPES
from app.domain.exceptions import ValidationError


def validate_food_payload(
    *,
    condition: str,
    meal_type: str | None = None,
    calories: float | None = None,
    fat_percent: float | None = None,
    meal_start_offset_min: int | None = None,
    dose_after_meal_min: int | None = None,
    water_volume_ml: int | None = None,
) -> None:
    if condition not in FOOD_CONDITIONS:
        raise ValidationError(
            f"Unsupported food condition: {condition}",
            field="condition",
            details={"allowed": list(FOOD_CONDITIONS)},
        )

    if meal_type is not None and meal_type not in MEAL_TYPES:
        raise ValidationError(
            f"Unsupported meal_type: {meal_type}",
            field="meal_type",
            details={"allowed": list(MEAL_TYPES)},
        )

    if condition == "FASTING" and meal_type is not None:
        raise ValidationError(
            "FASTING must not declare a meal_type",
            field="meal_type",
        )

    if condition in {"FED", "FASTING_AND_FED"} and meal_type == "CUSTOM":
        # Custom meal allowed; composition/calories may still be missing (NEEDS_REVIEW later).
        pass

    for field_name, value in (
        ("meal_start_offset_min", meal_start_offset_min),
        ("dose_after_meal_min", dose_after_meal_min),
        ("water_volume_ml", water_volume_ml),
    ):
        if value is not None and value < 0:
            raise ValidationError(f"{field_name} must be >= 0 when supplied", field=field_name)

    if calories is not None and calories < 0:
        raise ValidationError("calories must be >= 0 when supplied", field="calories")

    if fat_percent is not None and (fat_percent < 0 or fat_percent > 100):
        raise ValidationError("fat_percent must be in [0, 100] when supplied", field="fat_percent")

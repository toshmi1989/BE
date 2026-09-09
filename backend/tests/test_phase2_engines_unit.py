"""Unit tests for Design Engine validation and recommendation."""

import pytest

from app.domain.constants import CROSSOVER_2X2_REQUIRED_PERIODS
from app.domain.design_recommend import DesignRecommendInput, recommend_design
from app.domain.design_validation import validate_design_payload
from app.domain.exceptions import ValidationError
from app.domain.food_validation import validate_food_payload
from app.domain.subject_plan import SubjectPlanValues, calculate_subject_plan, validate_subject_plan


def test_valid_crossover_2x2() -> None:
    validate_design_payload(
        design_type="CROSSOVER_2X2",
        periods=CROSSOVER_2X2_REQUIRED_PERIODS,
        sequences=[["T", "R"], ["R", "T"]],
        treatments=["T", "R"],
    )


def test_invalid_crossover_period_count() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_design_payload(
            design_type="CROSSOVER_2X2",
            periods=3,
            sequences=[["T", "R"], ["R", "T"]],
        )
    assert exc.value.field == "periods"


def test_invalid_crossover_sequence_count() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_design_payload(
            design_type="CROSSOVER_2X2",
            periods=2,
            sequences=[["T", "R"]],
        )
    assert exc.value.field == "sequences"


def test_valid_parallel() -> None:
    validate_design_payload(
        design_type="PARALLEL",
        periods=1,
        sequences=[],
        treatments=["T", "R"],
    )


def test_invalid_parallel_groups() -> None:
    with pytest.raises(ValidationError):
        validate_design_payload(
            design_type="PARALLEL",
            periods=1,
            sequences=[],
            treatments=["T"],
        )


def test_valid_replicate() -> None:
    validate_design_payload(
        design_type="REPLICATE_2X2X4",
        periods=4,
        sequences=[["T", "R", "T", "R"], ["R", "T", "R", "T"]],
        treatments=["T", "R"],
    )


def test_invalid_replicate_periods() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_design_payload(
            design_type="REPLICATE_2X2X4",
            periods=2,
            sequences=[["T", "R"], ["R", "T"]],
        )
    assert exc.value.field == "periods"


def test_valid_adaptive() -> None:
    validate_design_payload(
        design_type="ADAPTIVE",
        periods=None,
        sequences=[],
        stage_configuration={
            "stage_1": {"n": None},
            "interim_analysis": {"method": "futility"},
        },
    )


def test_invalid_adaptive_missing_interim() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_design_payload(
            design_type="ADAPTIVE",
            periods=None,
            sequences=[],
            stage_configuration={"stage_1": {"n": 12}},
        )
    assert "interim_analysis" in (exc.value.field or "")


def test_recommend_insufficient_needs_review() -> None:
    result = recommend_design(DesignRecommendInput())
    assert result.status == "NEEDS_REVIEW"
    assert result.recommended_design is None
    assert result.confidence is None


def test_recommend_guideline_proposed_not_verified() -> None:
    result = recommend_design(
        DesignRecommendInput(
            available_guideline_recommendation="CROSSOVER_2X2",
            food_condition="FED",
            evidence_source_ids=["src-1"],
        )
    )
    assert result.status == "PROPOSED"
    assert result.recommended_design is not None
    assert result.recommended_design["type"] == "CROSSOVER_2X2"
    assert result.recommended_design["food_condition"] == "FED"
    assert result.status != "VERIFIED"
    assert "src-1" in result.evidence_source_ids


def test_recommend_high_variability_replicate() -> None:
    result = recommend_design(
        DesignRecommendInput(
            variability_known=True,
            variability_level="HIGH",
            dosage_form="tablet",
            route="oral",
        )
    )
    assert result.status == "PROPOSED"
    assert result.recommended_design["type"] == "REPLICATE_2X2X4"


def test_food_fasting_ok() -> None:
    validate_food_payload(condition="FASTING")


def test_food_fed_custom_ok() -> None:
    validate_food_payload(
        condition="FED",
        meal_type="CUSTOM",
        calories=800,
        meal_start_offset_min=30,
        dose_after_meal_min=0,
        water_volume_ml=200,
    )


def test_food_fasting_with_meal_invalid() -> None:
    with pytest.raises(ValidationError):
        validate_food_payload(condition="FASTING", meal_type="HIGH_CALORIE")


def test_food_negative_offset_invalid() -> None:
    with pytest.raises(ValidationError):
        validate_food_payload(condition="FED", meal_type="STANDARD", meal_start_offset_min=-1)


def test_subjects_valid() -> None:
    validate_subject_plan(
        SubjectPlanValues(
            target_evaluable_n=24,
            planned_randomized_n=28,
            reserve_n=0,
            planned_screened_n=40,
        )
    )


def test_subjects_randomized_lt_evaluable() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_subject_plan(
            SubjectPlanValues(target_evaluable_n=30, planned_randomized_n=20)
        )
    assert exc.value.field == "planned_randomized_n"


def test_subjects_screened_lt_randomized() -> None:
    with pytest.raises(ValidationError) as exc:
        validate_subject_plan(
            SubjectPlanValues(planned_randomized_n=28, planned_screened_n=10)
        )
    assert exc.value.field == "planned_screened_n"


def test_subjects_missing_not_zero() -> None:
    result = calculate_subject_plan(SubjectPlanValues(target_evaluable_n=24))
    assert result.target_evaluable_n == 24
    assert result.planned_randomized_n is None
    assert result.reserve_n is None
    assert result.planned_screened_n is None

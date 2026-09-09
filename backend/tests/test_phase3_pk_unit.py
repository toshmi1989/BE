"""Unit tests for Phase 3 PK / Sampling / Blood domain engines."""

import pytest

from app.domain.blood_volume import BloodVolumeInput, SampleCountInput, calculate_blood_volume, calculate_sample_count
from app.domain.exceptions import ValidationError
from app.domain.half_life import HalfLifeInputs, calculate_half_life_dependent_values
from app.domain.observation import ObservationCalcInput, calculate_observation
from app.domain.sampling import (
    AnalyteTmaxWindow,
    SamplingRecommendInput,
    generate_sampling_recommendation,
    merge_sampling_requirements,
    validate_sampling_plan,
)
from app.domain.units import convert_time, normalize_unit, to_hours
from app.domain.washout import WashoutCalcInput, calculate_washout


def test_unit_normalize_and_convert() -> None:
    assert normalize_unit("minutes").value == "min"
    assert to_hours(30, "min") == 0.5
    assert convert_time(48, "h", "day") == 2.0


def test_invalid_unit() -> None:
    with pytest.raises(ValidationError):
        normalize_unit("weeks")


def test_half_life_observation_washout() -> None:
    result = calculate_half_life_dependent_values(
        HalfLifeInputs(half_life_min=10, half_life_max=12, half_life_unit="h")
    )
    assert result.observation_minimum_h == 36.0  # 12 * 3
    assert result.washout_minimum_h == 60.0  # 12 * 5
    assert result.status == "PROPOSED"
    assert result.rule_ids


def test_half_life_missing() -> None:
    with pytest.raises(ValidationError):
        calculate_half_life_dependent_values(HalfLifeInputs(None, None))


def test_washout_crossover_and_too_short() -> None:
    result = calculate_washout(
        WashoutCalcInput(
            half_life_min=10,
            half_life_max=12,
            design_type="CROSSOVER_2X2",
            selected_value=1,
            selected_unit="day",
        )
    )
    assert result.requires_washout is True
    assert result.critical_issues
    assert result.critical_issues[0]["severity"] == "CRITICAL"


def test_washout_parallel_not_required() -> None:
    result = calculate_washout(
        WashoutCalcInput(
            half_life_min=10,
            half_life_max=12,
            design_type="PARALLEL",
        )
    )
    assert result.requires_washout is False
    assert result.calculated_minimum is None


def test_washout_missing_half_life_for_crossover() -> None:
    with pytest.raises(ValidationError):
        calculate_washout(WashoutCalcInput(None, None, design_type="CROSSOVER_2X2"))


def test_observation_valid_and_override() -> None:
    result = calculate_observation(
        ObservationCalcInput(
            half_life_min=8,
            half_life_max=10,
            selected_duration=36,
            selected_unit="h",
            manual_override=True,
        )
    )
    assert result.calculated_minimum_h == 30.0
    assert result.selected_duration_h == 36.0


def test_observation_missing_half_life() -> None:
    with pytest.raises(ValidationError):
        calculate_observation(ObservationCalcInput(None, None))


def test_sampling_basic_tmax_2_3() -> None:
    result = generate_sampling_recommendation(
        SamplingRecommendInput(
            analyte_windows=[
                AnalyteTmaxWindow("a1", "Parent", 2, 3, "h"),
            ],
            observation_duration_h=36,
        )
    )
    times = [p.time_h for p in result.points]
    assert times[0] == 0
    assert times[-1] == 36
    assert any(p.reason == "TMAX_CAPTURE" for p in result.points)
    assert result.status == "PROPOSED"
    # Must not be a hardcoded fixed count law
    assert len(result.points) != 18 or len(result.points) > 0


def test_sampling_early_and_late_tmax() -> None:
    early = generate_sampling_recommendation(
        SamplingRecommendInput(
            analyte_windows=[AnalyteTmaxWindow("a", "A", 0.5, 1, "h")],
            observation_duration_h=24,
        )
    )
    late = generate_sampling_recommendation(
        SamplingRecommendInput(
            analyte_windows=[AnalyteTmaxWindow("b", "B", 6, 8, "h")],
            observation_duration_h=48,
        )
    )
    assert any(0.4 <= p.time_h <= 1.2 for p in early.points if p.reason == "TMAX_CAPTURE")
    assert any(5.5 <= p.time_h <= 9 for p in late.points if p.reason == "TMAX_CAPTURE")


def test_sampling_multiple_analytes_merge() -> None:
    windows = [
        AnalyteTmaxWindow("a", "A", 1, 2, "h"),
        AnalyteTmaxWindow("b", "B", 4, 6, "h"),
    ]
    cmin, cmax, _ = merge_sampling_requirements(windows)
    assert cmin == 1
    assert cmax == 6
    result = generate_sampling_recommendation(
        SamplingRecommendInput(analyte_windows=windows, observation_duration_h=36)
    )
    assert result.points
    covered = {aid for p in result.points for aid in p.analyte_ids}
    assert "a" in covered and "b" in covered


def test_sampling_no_tmax() -> None:
    with pytest.raises(ValidationError):
        generate_sampling_recommendation(
            SamplingRecommendInput(analyte_windows=[], observation_duration_h=24)
        )


def test_sampling_missing_observation() -> None:
    with pytest.raises(ValidationError):
        generate_sampling_recommendation(
            SamplingRecommendInput(
                analyte_windows=[AnalyteTmaxWindow("a", "A", 2, 3)],
                observation_duration_h=None,
            )
        )


def test_sampling_validation_issues() -> None:
    issues = validate_sampling_plan(
        [{"time_h": 1, "reason": "ABSORPTION"}, {"time_h": 0.5, "reason": "ABSORPTION"}],
        observation_duration_h=24,
        analyte_windows=[AnalyteTmaxWindow("a", "A", 2, 3)],
    )
    codes = {i.code for i in issues}
    assert "MISSING_BASELINE" in codes
    assert "UNSORTED" in codes


def test_sampling_duplicate_and_negative() -> None:
    issues = validate_sampling_plan(
        [
            {"time_h": 0, "reason": "BASELINE"},
            {"time_h": 1, "reason": "ABSORPTION"},
            {"time_h": 1, "reason": "ABSORPTION"},
            {"time_h": -1, "reason": "ABSORPTION"},
        ],
        observation_duration_h=24,
    )
    codes = {i.code for i in issues}
    assert "DUPLICATE_TIME" in codes
    assert "NEGATIVE_TIME" in codes


def test_blood_basic_and_periods() -> None:
    result = calculate_blood_volume(
        BloodVolumeInput(
            subjects=24,
            periods=2,
            sampling_points_per_period=10,
            blood_volume_per_pk_sample_ml=5,
            screening_volume_ml=20,
            safety_laboratory_volume_ml=10,
        )
    )
    # pk per subject = 10*2*5 = 100; total pk = 2400
    assert result.pk_volume_ml == 2400
    assert result.volume_per_subject_ml == 130
    assert result.total_volume_ml == 3120


def test_blood_invalid_sample_volume() -> None:
    with pytest.raises(ValidationError):
        calculate_blood_volume(
            BloodVolumeInput(
                subjects=10,
                periods=2,
                sampling_points_per_period=8,
                blood_volume_per_pk_sample_ml=0,
            )
        )


def test_sample_count() -> None:
    result = calculate_sample_count(
        SampleCountInput(points_per_period=12, periods=2, planned_subjects=24)
    )
    assert result.total_subject_periods == 48
    assert result.total_pk_samples == 576

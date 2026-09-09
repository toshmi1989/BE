"""Unit tests for Phase 4 Statistics / CV / Sample Size engines."""

from __future__ import annotations

import pytest

from app.domain.cv_pooling import pool_cv
from app.domain.cv_selection import select_cv_for_sample_size
from app.domain.cv_validation import CVStudyData, check_cv_compatibility, validate_cv_study
from app.domain.exceptions import ValidationError
from app.domain.sample_size import SampleSizeInput, calculate_sample_size
from app.domain.stats_rules import ROUNDING_2X2, RULE_STAT_DEFAULTS
from app.domain.subject_reserve import ReserveInput, apply_subject_reserve


def _cv(**kwargs) -> CVStudyData:
    base = dict(
        analyte_id="a1",
        parameter="Cmax",
        design="CROSSOVER_2X2",
        condition="FED",
        dose="400 mg",
        n_total=46,
        n_be_analysis=40,
        cv_value=25.0,
        cv_unit="percent",
        source_id="src-1",
        cv_type="WITHIN_SUBJECT",
    )
    base.update(kwargs)
    return CVStudyData(**base)


def test_valid_cv() -> None:
    validate_cv_study(_cv())


def test_invalid_cv_zero() -> None:
    with pytest.raises(ValidationError):
        validate_cv_study(_cv(cv_value=0))


def test_invalid_cv_too_high() -> None:
    with pytest.raises(ValidationError):
        validate_cv_study(_cv(cv_value=250))


def test_missing_source() -> None:
    with pytest.raises(ValidationError):
        validate_cv_study(_cv(source_id=None))


def test_n_be_gt_n_total() -> None:
    with pytest.raises(ValidationError):
        validate_cv_study(_cv(n_total=30, n_be_analysis=40))


def test_parameter_mismatch_compatibility() -> None:
    result = check_cv_compatibility([_cv(parameter="Cmax"), _cv(parameter="AUC0_t")])
    assert result.compatible is False
    assert "parameter" in result.mismatches
    assert result.status == "NEEDS_REVIEW"


def test_analyte_mismatch_compatibility() -> None:
    result = check_cv_compatibility([_cv(analyte_id="a1"), _cv(analyte_id="a2")])
    assert result.compatible is False
    assert "analyte_id" in result.mismatches


def test_incompatible_studies_pooling_blocked() -> None:
    result = pool_cv([_cv(parameter="Cmax"), _cv(parameter="AUC0_t")])
    assert result.status == "NEEDS_REVIEW"
    assert result.pooled_cv is None


def test_compatible_studies_and_pooling() -> None:
    result = pool_cv(
        [
            _cv(cv_value=20, n_be_analysis=30, source_id="s1"),
            _cv(cv_value=30, n_be_analysis=40, source_id="s2"),
        ]
    )
    assert result.status == "PROPOSED"
    assert result.pooled_cv is not None
    assert 20 < result.pooled_cv < 30
    assert result.method == "INVERSE_VARIANCE_WEIGHTED_LOG_CV"
    assert result.algorithm_version


def test_cv_selection_single_not_max() -> None:
    studies = [_cv(cv_value=20, source_id="low"), _cv(cv_value=40, source_id="high")]
    selected = select_cv_for_sample_size(
        method="SINGLE_STUDY", studies=studies, selected_study_index=0
    )
    assert selected.selected_cv == 20.0
    assert selected.selection_method == "SINGLE_STUDY"


def test_cv_selection_pooled_and_expert() -> None:
    pooled = select_cv_for_sample_size(method="POOLED", pooled_cv=28.5)
    assert pooled.selected_cv == 28.5
    expert = select_cv_for_sample_size(method="EXPERT_SELECTED", expert_cv=22)
    assert expert.status == "NEEDS_REVIEW"


def test_sample_size_2x2_valid() -> None:
    result = calculate_sample_size(
        SampleSizeInput(
            design_type="CROSSOVER_2X2",
            selected_cv_percent=20.0,
            expected_ratio=1.0,
            alpha=0.05,
            power=0.8,
            be_lower=0.8,
            be_upper=1.25,
        )
    )
    assert result.status == "PROPOSED"
    assert result.evaluable_n is not None
    assert result.evaluable_n % 2 == 0
    assert result.evaluable_n >= 12
    assert result.algorithm_version.startswith("BE_TOST_2X2_NCT")
    assert result.software_version is not None
    assert "scipy" in result.software_version or "t_dist" in result.software_version


def test_sample_size_invalid_cv() -> None:
    with pytest.raises(ValidationError):
        calculate_sample_size(
            SampleSizeInput(
                design_type="CROSSOVER_2X2",
                selected_cv_percent=0,
                expected_ratio=1.0,
                alpha=0.05,
                power=0.8,
                be_lower=0.8,
                be_upper=1.25,
            )
        )


def test_sample_size_changed_ratio_power_alpha_limits() -> None:
    base = dict(
        design_type="CROSSOVER_2X2",
        selected_cv_percent=25.0,
        expected_ratio=1.0,
        alpha=0.05,
        power=0.8,
        be_lower=0.8,
        be_upper=1.25,
    )
    n0 = calculate_sample_size(SampleSizeInput(**base)).evaluable_n
    n_ratio = calculate_sample_size(SampleSizeInput(**{**base, "expected_ratio": 0.95})).evaluable_n
    n_power = calculate_sample_size(SampleSizeInput(**{**base, "power": 0.9})).evaluable_n
    n_alpha = calculate_sample_size(SampleSizeInput(**{**base, "alpha": 0.025})).evaluable_n
    n_limits = calculate_sample_size(
        SampleSizeInput(**{**base, "be_lower": 0.9, "be_upper": 1.11})
    ).evaluable_n
    assert n_ratio > n0
    assert n_power > n0
    assert n_alpha > n0
    assert n_limits > n0


def test_rounding_policy_even() -> None:
    assert ROUNDING_2X2.round_n(23.1) == 24
    assert ROUNDING_2X2.round_n(24.0) == 24


def test_dropout_and_reserve() -> None:
    result = apply_subject_reserve(
        ReserveInput(evaluable_n=40, dropout_pct=10, reserve_pct=5, screen_failure_pct=20)
    )
    assert result.evaluable_n == 40
    assert result.randomized_n > 40
    assert result.screened_n >= result.randomized_n
    assert "dropout_pct" in result.formula


def test_reproducibility_same_input_same_output() -> None:
    inp = SampleSizeInput(
        design_type="CROSSOVER_2X2",
        selected_cv_percent=30.0,
        expected_ratio=0.95,
        alpha=0.05,
        power=0.8,
        be_lower=0.8,
        be_upper=1.25,
        dropout_pct=10,
        reserve_pct=0,
    )
    a = calculate_sample_size(inp)
    b = calculate_sample_size(inp)
    assert a.evaluable_n == b.evaluable_n
    assert a.randomized_n == b.randomized_n
    assert a.screened_n == b.screened_n
    assert a.achieved_power == b.achieved_power
    assert a.inputs_snapshot == b.inputs_snapshot


def test_parallel_and_replicate_not_crossover_formula() -> None:
    parallel = calculate_sample_size(
        SampleSizeInput(
            design_type="PARALLEL",
            selected_cv_percent=20,
            expected_ratio=1.0,
            alpha=0.05,
            power=0.8,
            be_lower=0.8,
            be_upper=1.25,
        )
    )
    assert parallel.status == "NOT_IMPLEMENTED"
    assert parallel.evaluable_n is None

    replicate = calculate_sample_size(
        SampleSizeInput(
            design_type="REPLICATE_2X2X4",
            selected_cv_percent=20,
            expected_ratio=1.0,
            alpha=0.05,
            power=0.8,
            be_lower=0.8,
            be_upper=1.25,
        )
    )
    assert replicate.status == "NOT_IMPLEMENTED"


def test_adaptive_needs_review() -> None:
    result = calculate_sample_size(
        SampleSizeInput(
            design_type="ADAPTIVE",
            selected_cv_percent=20,
            expected_ratio=1.0,
            alpha=0.05,
            power=0.8,
            be_lower=0.8,
            be_upper=1.25,
        )
    )
    assert result.status == "NEEDS_REVIEW"
    assert "stage_1_n" in result.inputs_snapshot


def test_stat_defaults_explicit() -> None:
    assert RULE_STAT_DEFAULTS.rule_id == "STAT.DEFAULTS.ABE.v1"
    assert RULE_STAT_DEFAULTS.parameters["alpha"] == 0.05
    assert RULE_STAT_DEFAULTS.parameters["power"] == 0.80
    assert RULE_STAT_DEFAULTS.source

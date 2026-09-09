"""Regression: Sampling and Validation share TmaxCaptureWindow."""

from __future__ import annotations

from app.domain.pk_rules import RULE_SAMPLING_DENSITY
from app.domain.sampling import (
    AnalyteTmaxWindow,
    SamplingRecommendInput,
    generate_sampling_recommendation,
    merge_sampling_requirements,
    validate_sampling_plan,
)
from app.domain.tmax_capture_window import (
    compute_merged_tmax_capture_window,
    compute_tmax_capture_window,
)


def test_point_tmax_6_6_capture_window_4_5_to_7_5() -> None:
    """Phase 10 defect: Tmax=6–6 must expand to 4.5–7.5 under PK.SAMP.DENSITY.v1."""
    cap = compute_tmax_capture_window(6.0, 6.0, rule=RULE_SAMPLING_DENSITY)
    assert cap.window_min == 4.5
    assert cap.window_max == 7.5
    assert cap.rule_id == "PK.SAMP.DENSITY.v1"
    assert cap.status == "PROPOSED"
    assert cap.density_requirement.min_points_in_window == 2
    assert "not a verified regulatory" in cap.rationale.lower() or "PROPOSED" in cap.rationale


def test_sampling_generated_plan_passes_same_validation_rule() -> None:
    """Auto-generated plan for point Tmax must not fail INSUFFICIENT_TMAX_COVERAGE."""
    windows = [AnalyteTmaxWindow("a", "bosutinib", 6, 6, "h")]
    result = generate_sampling_recommendation(
        SamplingRecommendInput(analyte_windows=windows, observation_duration_h=72)
    )
    capture = compute_tmax_capture_window(6, 6, rule=RULE_SAMPLING_DENSITY, observation_duration_h=72)
    times = [p.time_h for p in result.points]
    assert capture.meets_density(times)
    assert any(abs(t - 4.5) < 1e-9 for t in times)
    assert any(abs(t - 7.5) < 1e-9 for t in times)

    issues = validate_sampling_plan(
        [{"time_h": p.time_h, "reason": p.reason} for p in result.points],
        observation_duration_h=72,
        analyte_windows=windows,
    )
    codes = {i.code for i in issues}
    assert "INSUFFICIENT_TMAX_COVERAGE" not in codes


def test_tmax_2_3_sampling_and_validation_identical_window() -> None:
    gen_cap = compute_tmax_capture_window(2.0, 3.0, rule=RULE_SAMPLING_DENSITY, observation_duration_h=36)
    assert gen_cap.window_min == 2.0 * (1 - 0.25)
    assert gen_cap.window_max == 3.0 * (1 + 0.25)

    windows = [AnalyteTmaxWindow("a", "Parent", 2, 3, "h")]
    result = generate_sampling_recommendation(
        SamplingRecommendInput(analyte_windows=windows, observation_duration_h=36)
    )
    # Points labeled TMAX_CAPTURE must lie inside the same canonical window
    for p in result.points:
        if p.reason == "TMAX_CAPTURE":
            assert gen_cap.contains(p.time_h)

    issues = validate_sampling_plan(
        [{"time_h": p.time_h, "reason": p.reason} for p in result.points],
        observation_duration_h=36,
        analyte_windows=windows,
    )
    assert "INSUFFICIENT_TMAX_COVERAGE" not in {i.code for i in issues}


def test_multiple_analytes_merged_window_consistent_with_validation() -> None:
    windows = [
        AnalyteTmaxWindow("a", "A", 1, 2, "h"),
        AnalyteTmaxWindow("b", "B", 4, 6, "h"),
    ]
    cmin, cmax, _ = merge_sampling_requirements(windows)
    merged = compute_merged_tmax_capture_window(
        [(1.0, 2.0), (4.0, 6.0)],
        rule=RULE_SAMPLING_DENSITY,
        observation_duration_h=36,
    )
    per_a = compute_tmax_capture_window(1, 2, rule=RULE_SAMPLING_DENSITY, observation_duration_h=36)
    per_b = compute_tmax_capture_window(4, 6, rule=RULE_SAMPLING_DENSITY, observation_duration_h=36)
    assert merged.tmax_min_h == cmin
    assert merged.tmax_max_h == cmax
    assert merged.window_min == per_a.window_min  # min of expanded starts from earliest tmin
    assert merged.window_max == per_b.window_max

    result = generate_sampling_recommendation(
        SamplingRecommendInput(analyte_windows=windows, observation_duration_h=36)
    )
    times = [p.time_h for p in result.points]
    assert per_a.meets_density(times)
    assert per_b.meets_density(times)
    assert merged.meets_density(times)

    issues = validate_sampling_plan(
        [{"time_h": p.time_h, "reason": p.reason} for p in result.points],
        observation_duration_h=36,
        analyte_windows=windows,
    )
    assert "INSUFFICIENT_TMAX_COVERAGE" not in {i.code for i in issues}


def test_manual_override_uses_same_canonical_capture_window() -> None:
    """manual_override must not invent a different Tmax capture definition."""
    windows = [AnalyteTmaxWindow("a", "x", 6, 6, "h")]
    result = generate_sampling_recommendation(
        SamplingRecommendInput(analyte_windows=windows, observation_duration_h=72)
    )
    points = [{"time_h": p.time_h, "reason": p.reason} for p in result.points]
    # Drop final so FINAL_MISMATCH fires; coverage must still use 4.5–7.5
    trimmed = [p for p in points if p["time_h"] < 72]
    trimmed.append({"time_h": 70.0, "reason": "FINAL"})

    cap = compute_tmax_capture_window(6, 6, rule=RULE_SAMPLING_DENSITY, observation_duration_h=72)
    assert cap.window_min == 4.5 and cap.window_max == 7.5

    issues_default = validate_sampling_plan(
        trimmed,
        observation_duration_h=72,
        analyte_windows=windows,
        manual_override=False,
    )
    issues_manual = validate_sampling_plan(
        trimmed,
        observation_duration_h=72,
        analyte_windows=windows,
        manual_override=True,
    )
    assert "INSUFFICIENT_TMAX_COVERAGE" not in {i.code for i in issues_default}
    assert "INSUFFICIENT_TMAX_COVERAGE" not in {i.code for i in issues_manual}
    # Severity of FINAL_MISMATCH may differ; capture window identity must not
    assert any(i.code == "FINAL_MISMATCH" for i in issues_default)
    assert any(i.code == "FINAL_MISMATCH" for i in issues_manual)


def test_phase10_defect_regression_sparse_point_still_fails() -> None:
    """Aligned window still rejects truly insufficient coverage (single point at Tmax)."""
    issues = validate_sampling_plan(
        [
            {"time_h": 0, "reason": "BASELINE"},
            {"time_h": 6, "reason": "TMAX_CAPTURE"},
            {"time_h": 72, "reason": "FINAL"},
        ],
        observation_duration_h=72,
        analyte_windows=[AnalyteTmaxWindow("a", "bosutinib", 6, 6, "h")],
    )
    assert "INSUFFICIENT_TMAX_COVERAGE" in {i.code for i in issues}

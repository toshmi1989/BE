"""Phase 5 validation engine unit/matrix tests."""

from __future__ import annotations

from app.domain.study_snapshot import build_canonical_snapshot, build_consistency_snapshot
from app.domain.validation_engine import validate_project
from app.domain.validation_graph import change_impact, dependents_of


def _base_ctx(**overrides):
    ctx = {
        "project_id": "p1",
        "study": {"id": "s1", "protocol_number": "BE-001", "title": "Test"},
        "sponsor": {"id": "sp1", "name": "Test Sponsor", "country": "RU"},
        "product": {"trade_name": "T", "inn": "inn", "dosage": "400 mg"},
        "reference_product": {
            "id": "r1",
            "trade_name": "R",
            "inn": "inn",
            "status": "PROPOSED",
            "source_ids": ["src1"],
            "purchased_status": "UNKNOWN",
        },
        "sources": [{"id": "src1", "type": "SmPC", "title": "label"}],
        "design": {
            "id": "d1",
            "type": "CROSSOVER_2X2",
            "periods": 2,
            "sequences": [["T", "R"], ["R", "T"]],
            "treatments": ["T", "R"],
            "food_condition": "FED",
        },
        "food": {"id": "f1", "condition": "FED", "meal_type": "HIGH_CALORIE"},
        "eligibility": {"inclusion": [{"id": "e1", "number": 1, "text": "HV"}], "non_inclusion": [], "exclusion": []},
        "subjects": {
            "target_evaluable_n": 24,
            "planned_randomized_n": 28,
            "planned_screened_n": 40,
            "reserve_n": 0,
        },
        "analytes": [
            {
                "id": "a1",
                "name": "parent",
                "type": "PARENT",
                "active": True,
                "tmax_min": 2,
                "tmax_max": 3,
                "tmax_unit": "h",
                "status": "PROPOSED",
            }
        ],
        "pk_parameters": [
            {
                "analyte_id": "a1",
                "parameter_code": "Tmax",
                "range_min": 2,
                "range_max": 3,
            }
        ],
        "washout": {
            "id": "w1",
            "selected_value": 5,
            "unit": "day",
            "requires_washout": True,
            "manual_override": False,
            "issues": [],
        },
        "observation": {"selected_duration": 36, "unit": "h", "final_sampling_time": 36},
        "sampling": {
            "id": "sp1",
            "manual_override": False,
            "total_points_per_period": 8,
            "points": [
                {"time_h": 0, "reason": "BASELINE"},
                {"time_h": 1, "reason": "PRE_TMAX"},
                {"time_h": 2, "reason": "TMAX"},
                {"time_h": 2.5, "reason": "TMAX"},
                {"time_h": 3, "reason": "TMAX"},
                {"time_h": 6, "reason": "POST"},
                {"time_h": 24, "reason": "TERMINAL"},
                {"time_h": 36, "reason": "FINAL"},
            ],
        },
        "blood_volume": {"sampling_points_per_period": 8, "total_volume_ml": 100},
        "cv_studies": [
            {
                "id": "cv1",
                "evidence": [{"source_id": "src1", "extracted_text": "CV 25%"}],
                "cv_value": 25,
            }
        ],
        "cv_selection": {
            "selected_cv": 25,
            "status": "PROPOSED",
            "source_study_ids": ["src1"],
        },
        "sample_size": {
            "evaluable_n": 24,
            "randomized_n": 28,
            "screened_n": 40,
            "status": "PROPOSED",
        },
        "statistical_config": {"alpha": 0.05, "power": 0.8},
    }
    ctx.update(overrides)
    return ctx


def _codes(issues):
    return {i.rule_id for i in issues}


def test_empty_project_blocking() -> None:
    issues = validate_project({"project_id": "empty"})
    assert any(i.blocking for i in issues)
    assert "VAL.DESIGN.MISSING.v1" in _codes(issues)
    assert "VAL.REF.MISSING.v1" in _codes(issues)


def test_missing_reference() -> None:
    ctx = _base_ctx(reference_product=None)
    assert "VAL.REF.MISSING.v1" in _codes(validate_project(ctx))


def test_verified_reference_without_source() -> None:
    ctx = _base_ctx(
        reference_product={
            "id": "r1",
            "status": "VERIFIED",
            "source_ids": [],
            "provenance": {"status": "VERIFIED", "source_ids": []},
        }
    )
    assert "VAL.REF.VERIFIED_NO_SOURCE.v1" in _codes(validate_project(ctx))


def test_invalid_design_and_missing_periods() -> None:
    ctx = _base_ctx(design={"type": "CROSSOVER_2X2", "periods": None, "sequences": [["T", "R"], ["R", "T"]]})
    codes = _codes(validate_project(ctx))
    assert "VAL.DESIGN.PERIODS_MISSING.v1" in codes


def test_fed_without_meal() -> None:
    ctx = _base_ctx(food={"condition": "FED", "meal_type": None})
    assert "VAL.FOOD.FED_MEAL.v1" in _codes(validate_project(ctx))


def test_missing_analyte_and_tmax() -> None:
    assert "VAL.ANALYTE.MISSING.v1" in _codes(validate_project(_base_ctx(analytes=[])))
    ctx = _base_ctx(
        analytes=[{"id": "a1", "name": "x", "active": True, "tmax_min": None, "tmax_max": None}],
        pk_parameters=[],
    )
    codes = _codes(validate_project(ctx))
    assert "VAL.ANALYTE.TMAX.v1" in codes


def test_sampling_tmax_and_observation() -> None:
    ctx = _base_ctx(
        sampling={
            "id": "sp1",
            "manual_override": False,
            "points": [{"time_h": 0, "reason": "BASELINE"}, {"time_h": 36, "reason": "FINAL"}],
            "total_points_per_period": 2,
        },
        blood_volume={"sampling_points_per_period": 2},
    )
    codes = _codes(validate_project(ctx))
    assert any("TMAX" in c or "PRE_TMAX" in c or "POST_TMAX" in c for c in codes)

    ctx2 = _base_ctx(
        observation={"selected_duration": 24},
        sampling={
            "manual_override": False,
            "points": [
                {"time_h": 0, "reason": "BASELINE"},
                {"time_h": 1, "reason": "PRE"},
                {"time_h": 2, "reason": "TMAX"},
                {"time_h": 2.5, "reason": "TMAX"},
                {"time_h": 36, "reason": "FINAL"},
            ],
            "total_points_per_period": 5,
        },
        blood_volume={"sampling_points_per_period": 5},
    )
    assert any("FINAL_EXCEEDS_OBS" in c for c in _codes(validate_project(ctx2)))


def test_blood_volume_inconsistent() -> None:
    ctx = _base_ctx(blood_volume={"sampling_points_per_period": 3})
    assert "VAL.BLOOD.STALE.v1" in _codes(validate_project(ctx))


def test_statistics_without_cv() -> None:
    ctx = _base_ctx(cv_selection=None, sample_size={"evaluable_n": 24})
    codes = _codes(validate_project(ctx))
    assert "VAL.STAT.CV_MISSING.v1" in codes


def test_n_inconsistency() -> None:
    ctx = _base_ctx(
        subjects={
            "target_evaluable_n": 40,
            "planned_randomized_n": 30,
            "planned_screened_n": 50,
        },
        sample_size=None,
    )
    codes = _codes(validate_project(ctx))
    assert "VAL.SUBJECTS.STRUCTURE.v1" in codes or "VAL.N.ORDER.v1" in codes


def test_valid_complete_study_no_blocking() -> None:
    issues = validate_project(_base_ctx())
    blocking = [i for i in issues if i.blocking]
    assert blocking == [], [i.rule_id for i in blocking]


def test_manual_overrides_info() -> None:
    ctx = _base_ctx(
        washout={
            "selected_value": 5,
            "unit": "day",
            "requires_washout": True,
            "manual_override": True,
            "issues": [],
        },
        sampling={
            "manual_override": True,
            "total_points_per_period": 8,
            "points": _base_ctx()["sampling"]["points"],
        },
    )
    codes = _codes(validate_project(ctx))
    assert "VAL.WASHOUT.MANUAL.v1" in codes
    assert "VAL.SAMP.MANUAL.v1" in codes


def test_change_impact_design_sampling_stats() -> None:
    design_impact = change_impact("design")
    assert "washout" in design_impact["revalidate"]
    assert "sampling" in design_impact["revalidate"]
    assert "statistics" in design_impact["revalidate"]

    samp = change_impact("sampling")
    assert "blood_volume" in samp["revalidate"]

    tmax = change_impact("tmax")
    assert "sampling" in tmax["revalidate"]
    assert dependents_of("pk")


def test_snapshot_deterministic() -> None:
    ctx = _base_ctx()
    a = build_canonical_snapshot(ctx).fingerprint()
    b = build_canonical_snapshot(ctx).fingerprint()
    assert a == b
    snap = build_consistency_snapshot(ctx)
    assert snap["design"] == "CROSSOVER_2X2"
    assert snap["evaluable_n"] == 24

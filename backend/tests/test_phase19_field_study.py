"""Phase 19 — Real package field study infrastructure (0.30.0)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.field_study import (
    aggregate_timing_metrics,
    assert_no_auto_medical,
    classify_field,
    extraction_classification_summary,
    record_timings,
    reset_field_study,
    start_case,
)
from app.domain.conflict_benchmark import conflict_benchmark_summary, evaluate_updcb_conflicts
from app.domain.population_gap import investigate_population_gap
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.real_package_registry import (
    population_status,
    validate_intake_filenames,
)
from app.main import create_app


def setup_function() -> None:
    reset_field_study()
    get_settings.cache_clear()


def test_version_0_24_0() -> None:
    assert Settings().app_version == "0.30.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.30.0"
    assert get_settings().app_version == "0.30.0"


def test_real_population_does_not_meet_10_and_not_synthetic() -> None:
    st = population_status()
    assert st["synthetic_counted_as_real"] is False
    assert st["real_full_sanitized"] == 1
    assert st["real_partial_sanitized"] == 1
    assert st["meets_minimum_10_full_real"] is False
    assert st["production_gate"] == "READY-WITH-BLOCKERS"
    assert len(st["empty_intake_slots"]) >= 8


def test_intake_filename_blocks_patientish_names() -> None:
    ok = validate_intake_filenames(["synopsis.pdf", "checklist.docx"])
    assert ok["ok"] is True
    bad = validate_intake_filenames(["patient_list.xlsx", "creds.pem"])
    assert bad["ok"] is False
    assert "patient_list.xlsx" in bad["blocked_filenames"]
    assert "creds.pem" in bad["blocked_filenames"]


def test_timing_saving_requires_direct_observation() -> None:
    s = start_case(case_id="REAL-UPDCB-02-BE-2026", writer_id="W-A", system_used=True, mode="SYSTEM_ASSISTED")
    sid = s["session_id"]
    # Estimated / not observed → no saving published
    row = record_timings(
        sid,
        T_manual_minutes=120,
        T_system_minutes=40,
        T_review_minutes=30,
        observed_directly=False,
    )
    assert row["time_saving_percent"] is None
    assert row["timing_observed_directly"] is False

    row2 = record_timings(
        sid,
        T_manual_minutes=120,
        T_system_minutes=40,
        T_review_minutes=30,
        observed_directly=True,
    )
    assert row2["T_total_minutes"] == 70
    assert row2["time_saving_percent"] == round((120 - 70) / 120, 4)
    assert row2["timing_observed_directly"] is True

    agg = aggregate_timing_metrics()
    assert agg["sessions_with_observed_timing"] == 1
    assert agg["roi_claimed"] is False
    # Phase 20: aggregates unpublished until meaningful sample size
    assert agg["aggregates_published"] is False
    assert agg["time_saving_percent"]["median"] is None
    assert agg["manual_minutes"]["mean_not_used_alone"] is True
    # Per-session saving still recorded when observed directly
    assert row2["time_saving_percent"] is not None


def test_writer_correction_not_auto_success() -> None:
    s = start_case(case_id="REAL-UPDCB-02-BE-2026", writer_id="W-B", system_used=True)
    classify_field(s["session_id"], "dose", "CORRECT_AFTER_REVIEW")
    classify_field(s["session_id"], "sponsor", "CORRECT_AUTO")
    summary = extraction_classification_summary(s["session_id"])
    assert summary["tallies"]["CORRECT_AFTER_REVIEW"] == 1
    assert summary["tallies"]["CORRECT_AUTO"] == 1
    # Auto-only accuracy excludes review corrections
    assert summary["field_accuracy_auto_only"] == 0.5
    assert "AFTER_REVIEW is not counted" in summary["note"]


def test_population_gap_no_invented_medical_rule() -> None:
    gap = investigate_population_gap()
    assert gap["issue"] == "B-002"
    assert gap["proposed_model_change"]["required"] is False
    assert "full_package" in gap
    assert "partial_package" in gap


def test_updcb_conflict_benchmark_dose_detected() -> None:
    row = evaluate_updcb_conflicts()
    assert row["labels_reliable"] is True
    assert "dose" in row["true_positives"]
    assert row["missed_conflicts"] == []
    assert row["b001_still_blocker"] is False
    summary = conflict_benchmark_summary()
    assert summary["real_cases_with_reliable_labels"] == 1
    assert summary["aggregate_recall"] == 1.0


def test_no_auto_medical_guards() -> None:
    s = start_case(case_id="REAL-UPDCB-02-BE-2026", writer_id="W-C", system_used=True)
    g = assert_no_auto_medical(s)
    assert g["ai_cannot_approve_decision"] is True
    assert g["ai_cannot_resolve_conflict"] is True
    assert g["ai_cannot_approve_sample_size"] is True
    assert g["ai_cannot_approve_statistics"] is True
    assert g["ai_cannot_finalize_protocol"] is True


def test_field_study_api_routes() -> None:
    client = TestClient(create_app())
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["version"] == "0.30.0"

    pop = client.get("/api/field-study/population-status")
    assert pop.status_code == 200
    assert pop.json()["meets_minimum_10_full_real"] is False

    pkgs = client.get("/api/field-study/real-packages")
    assert pkgs.status_code == 200
    origins = {p["origin"] for p in pkgs.json()["packages"]}
    assert "REAL" in origins
    assert "SYNTHETIC" not in origins

    created = client.post(
        "/api/field-study/sessions",
        json={
            "case_id": "REAL-UPDCB-02-BE-2026",
            "writer_id": "W-API",
            "system_used": False,
            "mode": "MANUAL",
            "case_order": 1,
        },
    )
    assert created.status_code == 200
    sid = created.json()["session_id"]

    ev = client.post(
        f"/api/field-study/sessions/{sid}/events",
        json={"event": "DOCUMENT_REVIEWED", "meta": {"excerpt": "SHOULD_STRIP", "doc": "synopsis"}},
    )
    assert ev.status_code == 200
    assert "excerpt" not in (ev.json().get("meta") or {})

    bad_intake = client.post(
        "/api/field-study/intake/validate-filenames",
        json={"filenames": ["subject_001_lab.pdf"]},
    )
    assert bad_intake.status_code == 200
    assert bad_intake.json()["ok"] is False

    gap = client.get("/api/field-study/population-gap")
    assert gap.status_code == 200
    assert gap.json()["proposed_model_change"]["required"] is False

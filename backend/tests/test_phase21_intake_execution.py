"""Phase 21 — Real intake & writer session execution (0.32.0). No fabricated data."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.field_study import (
    complete_case,
    create_paired_study,
    list_events,
    production_readiness,
    reset_field_study,
)
from app.domain.field_study_intake import (
    assign_writer,
    bootstrap_from_registry,
    create_intake_case,
    mark_ready_for_session,
    reset_intake_store,
    submit_sanitization_review,
)
from app.domain.field_study_status import data_quality_check, field_study_status
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.real_package_registry import population_status
from app.main import create_app


def setup_function() -> None:
    reset_field_study()
    reset_intake_store(clear_disk=True)
    get_settings.cache_clear()


def test_version_0_26_0() -> None:
    assert Settings().app_version == "0.32.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.32.0"


def test_no_fabricated_packages_still_below_10() -> None:
    st = population_status()
    assert st["real_full_sanitized"] == 1
    assert st["meets_minimum_10_full_real"] is False
    assert st["synthetic_counted_as_real"] is False


def test_intake_lifecycle_to_ready() -> None:
    bootstrap_from_registry()
    row = create_intake_case(
        case_id="REAL-INTAKE-META-ONLY",
        source_origin="writer_pending_upload",
        origin="REAL",
        study_pattern=["fed"],
        filenames=["synopsis.docx"],
        document_inventory={"Synopsis_Design": "PRESENT", "Checklist": "ABSENT"},
    )
    assert row["state"] == "INTAKE"
    submit_sanitization_review("REAL-INTAKE-META-ONLY", sanitized=True, notes="writer attested")
    assign_writer("REAL-INTAKE-META-ONLY", "W-21")
    ready = mark_ready_for_session("REAL-INTAKE-META-ONLY")
    assert ready["state"] == "READY_FOR_SESSION"
    assert ready["ready_for_session"] is True
    # Meta-only intake must NOT inflate registry full REAL count
    assert population_status()["real_full_sanitized"] == 1


def test_refuse_synthetic_origin() -> None:
    try:
        create_intake_case(
            case_id="SYN-X",
            source_origin="test",
            origin="SYNTHETIC",
        )
        assert False
    except ValueError as e:
        assert "REAL" in str(e)


def test_session_required_events_on_complete() -> None:
    pair = create_paired_study(case_id="REAL-UPDCB-02-BE-2026", writer_id="W-21A")
    sid = pair["assisted_session"]["session_id"]
    complete_case(sid)
    names = {e["event"] for e in list_events(sid)}
    assert "CASE_STARTED" in names
    assert "SESSION_STARTED" in names
    assert "SESSION_COMPLETED" in names
    assert "CASE_COMPLETED" in names


def test_status_excludes_synthetic_and_reports_postgres_blocked() -> None:
    st = field_study_status()
    assert st["synthetic_excluded_from_counters"] is True
    assert st["full_packages"] == 1
    assert st["paired_sessions_complete"] == 0
    assert st["postgres_status"] == "POSTGRES_EXECUTION_BLOCKED"


def test_dq_never_silent_drop() -> None:
    dq = data_quality_check()
    assert dq["silent_drops"] is False


def test_production_gate_not_ready() -> None:
    gate = production_readiness()
    assert gate["gate"] == "NOT READY"
    assert gate["controlled_beta_criteria"]["full_packages_ge_10"] is False
    assert gate["controlled_beta_criteria"]["paired_sessions_ge_5"] is False
    assert gate["controlled_beta_criteria"]["postgres_execution_completed"] is False


def test_api_status_and_intake() -> None:
    client = TestClient(create_app())
    assert client.get("/api/health").json()["version"] == "0.32.0"
    s = client.get("/api/field-study/status")
    assert s.status_code == 200
    body = s.json()
    assert body["full_packages"] == 1
    assert "synthetic" not in str(body.get("full_packages"))
    cases = client.get("/api/field-study/intake/cases")
    assert cases.status_code == 200
    assert "INTAKE" in cases.json()["states"]
    ready = client.get("/api/field-study/production-readiness")
    assert ready.json()["gate"] == "NOT READY"

"""Phase 22 — Controlled beta preparation (0.30.0). No fabricated evidence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.controlled_beta import (
    export_field_study,
    intake_slots_dashboard,
    session_start_gate,
    start_timed_session,
    stop_timed_session,
)
from app.domain.field_study import production_readiness, reset_field_study
from app.domain.field_study_intake import reset_intake_store
from app.domain.field_study_status import field_study_status
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.main import create_app


def setup_function() -> None:
    reset_field_study()
    reset_intake_store(clear_disk=True)
    get_settings.cache_clear()


def test_version_0_27_0() -> None:
    assert Settings().app_version == "0.30.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.30.0"


def test_status_beta_not_ready_reasons() -> None:
    st = field_study_status()
    assert st["beta_label"] == "BETA NOT READY"
    assert st["production_gate"] == "NOT READY"
    assert any("full real" in r for r in st["reasons"])
    assert any("Postgres" in r for r in st["reasons"])
    assert st["auth"]["secret_value_exposed"] is False
    assert "B-002-PACK" in st["open_P1"]


def test_intake_dashboard_no_fake_entries() -> None:
    dash = intake_slots_dashboard()
    assert dash["full"] == 1
    assert dash["partial"] == 1
    assert dash["empty"] == 8
    assert len(dash["slots"]) == 10
    assert all(s["fabricated"] is False for s in dash["slots"])
    assert "1 / 10" in dash["display"] or dash["display"].startswith("1")


def test_session_gate_blocks_unknown() -> None:
    g = session_start_gate("NOT-REAL", "W1")
    assert g["result"] == "BLOCK"
    assert g["reasons"]


def test_timed_manual_assisted_pair() -> None:
    out = start_timed_session(
        case_id="REAL-UPDCB-02-BE-2026",
        writer_id="W-22",
        session_type="MANUAL",
    )
    assert out["ok"] is True
    pair_id = out["pair_id"]
    sid = out["session"]["session_id"]
    stopped = stop_timed_session(sid)
    assert stopped["ok"] is True
    assert stopped["elapsed_minutes"] is not None

    assisted = start_timed_session(
        case_id="REAL-UPDCB-02-BE-2026",
        writer_id="W-22",
        session_type="SYSTEM_ASSISTED",
        pair_id=pair_id,
    )
    assert assisted["ok"] is True
    stop2 = stop_timed_session(assisted["session"]["session_id"], review_minutes=0.0)
    assert stop2["ok"] is True


def test_export_has_no_secrets() -> None:
    exp = export_field_study()
    assert exp["secrets_included"] is False
    assert exp["document_contents_included"] is False


def test_production_not_ready() -> None:
    assert production_readiness()["gate"] == "NOT READY"


def test_api_beta_endpoints() -> None:
    client = TestClient(create_app())
    assert client.get("/api/health").json()["version"] == "0.30.0"
    st = client.get("/api/field-study/status")
    assert st.status_code == 200
    assert st.json()["beta_label"] == "BETA NOT READY"
    assert client.get("/api/field-study/dashboard/intake").status_code == 200
    assert client.get("/api/field-study/export").status_code == 200
    br = client.get("/api/field-study/beta-readiness")
    assert br.status_code == 200
    assert br.json()["label"] == "BETA NOT READY"

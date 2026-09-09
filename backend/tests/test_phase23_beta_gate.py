"""Phase 23 — Controlled beta entry gate (0.33.0). No fabricated evidence."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.beta_entry_gate import (
    beta_gate_checks,
    evaluate_entry_criteria,
    select_beta_cases,
)
from app.domain.field_study import reset_field_study
from app.domain.field_study_intake import reset_intake_store
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.main import create_app


def setup_function() -> None:
    reset_field_study()
    reset_intake_store(clear_disk=True)
    get_settings.cache_clear()


def test_version_0_28_0() -> None:
    assert Settings().app_version == "0.33.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.33.0"


def test_entry_gate_not_ready() -> None:
    ev = evaluate_entry_criteria()
    assert ev["state"] == "BETA_NOT_READY"
    assert ev["entry_ready"] is False
    assert ev["classification"] == "NOT_READY"
    assert ev["secrets_exposed"] is False
    assert ev["production_ready_claimed"] is False
    assert any("REAL_FULL" in b or "PAIRED" in b or "POSTGRES" in b for b in ev["blockers"])


def test_beta_gate_script_logic_blocks() -> None:
    report = beta_gate_checks()
    assert report["overall"] == "BLOCK"
    assert report["secrets_exposed"] is False
    assert report["block_count"] >= 1


def test_case_selection_no_fabrication() -> None:
    sel = select_beta_cases()
    assert sel["fabricated"] is False
    assert sel["full_selected"] == 1
    assert sel["partial_selected"] == 1
    assert sel["count"] == 2


def test_cannot_start_running_without_entry() -> None:
    client = TestClient(create_app())
    r = client.post(
        "/api/field-study/beta-gate/state",
        json={"state": "CONTROLLED_BETA_RUNNING", "note": "attempt"},
    )
    assert r.status_code == 400
    assert "entry_not_ready" in str(r.json())


def test_api_beta_gate_and_cases() -> None:
    client = TestClient(create_app())
    assert client.get("/api/health").json()["version"] == "0.33.0"
    g = client.get("/api/field-study/beta-gate")
    assert g.status_code == 200
    assert g.json()["overall"] == "BLOCK"
    c = client.get("/api/field-study/beta-cases")
    assert c.status_code == 200
    assert c.json()["fabricated"] is False
    br = client.get("/api/field-study/beta-readiness")
    assert br.status_code == 200
    assert br.json()["entry_gate"]["state"] == "BETA_NOT_READY"

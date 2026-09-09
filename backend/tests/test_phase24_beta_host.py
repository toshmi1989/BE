"""Phase 24 — Beta host activation (0.30.0). No fabricated evidence."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.beta_entry_gate import evaluate_entry_criteria
from app.domain.field_study import reset_field_study
from app.domain.field_study_intake import reset_intake_store
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.real_package_registry import REPO_ROOT, population_status
from app.main import create_app

EVIDENCE = REPO_ROOT / "fixtures" / "field_study" / "phase24_postgres_evidence.json"
ACTIVATION = REPO_ROOT / "fixtures" / "field_study" / "phase24_activation_result.json"


def setup_function() -> None:
    reset_field_study()
    reset_intake_store(clear_disk=True)
    get_settings.cache_clear()


def test_version_0_29_0() -> None:
    assert Settings().app_version == "0.30.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.30.0"


def test_packages_still_below_10_not_invented() -> None:
    st = population_status()
    assert st["real_full_sanitized"] == 1
    assert st["meets_minimum_10_full_real"] is False
    assert st["synthetic_counted_as_real"] is False


def test_phase24_evidence_honest_if_present() -> None:
    assert EVIDENCE.exists(), "Run scripts/phase24_beta_host_activation.py first"
    data = json.loads(EVIDENCE.read_text(encoding="utf-8-sig"))
    assert data.get("fabricated") is False
    assert data.get("POSTGRES_EXECUTION_BLOCKED") is True
    assert data.get("BACKUP_OK") is False
    assert data.get("RESTORE_OK") is False


def test_activation_did_not_advance_ready() -> None:
    assert ACTIVATION.exists()
    act = json.loads(ACTIVATION.read_text(encoding="utf-8-sig"))
    assert act["advanced_to_BETA_READY"] is False
    assert act["advanced_to_CONTROLLED_BETA_RUNNING"] is False
    assert act["beta_gate"] == "BETA_NOT_READY"
    assert act["roi_published"] is False


def test_entry_gate_still_not_ready() -> None:
    ev = evaluate_entry_criteria()
    assert ev["state"] == "BETA_NOT_READY"
    assert ev["entry_ready"] is False


def test_api_activation() -> None:
    client = TestClient(create_app())
    assert client.get("/api/health").json()["version"] == "0.30.0"
    r = client.get("/api/field-study/activation/phase24")
    assert r.status_code == 200
    body = r.json()
    assert body["fabricated"] is False
    assert body["entry_gate"]["state"] == "BETA_NOT_READY"

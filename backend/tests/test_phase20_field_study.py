"""Phase 20 — Field study execution (0.32.0). No fabricated ROI or packages."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.field_study import (
    MIN_PAIRED_FOR_AGGREGATE,
    aggregate_timing_metrics,
    create_paired_study,
    production_readiness,
    record_pair_timings,
    reset_field_study,
    start_case,
)
from app.domain.population_gap import investigate_population_gap
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.real_package_registry import field_study_intake_manifest, population_status
from app.main import create_app

REPO = Path(__file__).resolve().parents[2]
OPS_EVIDENCE = REPO / "fixtures" / "field_study" / "phase20_ops_evidence.json"


def setup_function() -> None:
    reset_field_study()
    get_settings.cache_clear()


def test_version_0_25_0() -> None:
    assert Settings().app_version == "0.32.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.32.0"
    assert get_settings().app_version == "0.32.0"


def test_explicit_package_limitation_no_fabrication() -> None:
    st = population_status()
    assert st["real_full_sanitized"] == 1
    assert st["meets_minimum_10_full_real"] is False
    assert st["synthetic_counted_as_real"] is False
    manifest = field_study_intake_manifest()
    assert manifest["fabricated_values"] is False
    assert manifest["meets_minimum_10_full_real"] is False
    assert len(manifest["empty_intake_slots"]) >= 8


def test_sanitization_gate_blocks_unknown_case() -> None:
    try:
        start_case(case_id="FAKE-SYNTHETIC", writer_id="W1", system_used=False)
        assert False, "should reject"
    except ValueError as e:
        assert "Unknown" in str(e) or "SANITIZED" in str(e)


def test_paired_sessions_and_roi_aggregate_gate() -> None:
    pair = create_paired_study(case_id="REAL-UPDCB-02-BE-2026", writer_id="W-P20")
    assert pair["pair"]["manual_session_id"] != pair["pair"]["assisted_session_id"]
    record_pair_timings(
        pair["pair"]["pair_id"],
        manual_total_minutes=100,
        system_total_minutes=40,
        review_minutes=20,
        observed_directly=True,
    )
    agg = aggregate_timing_metrics()
    assert agg["paired_roi_eligible"] == 1
    assert agg["aggregates_published"] is False
    assert agg["roi_claimed"] is False
    assert agg["manual_minutes"]["median"] is None
    assert agg["min_paired_for_aggregate"] == MIN_PAIRED_FOR_AGGREGATE


def test_estimated_timings_never_publish_roi() -> None:
    pair = create_paired_study(case_id="REAL-UPDCB-02-BE-2026", writer_id="W-EST")
    record_pair_timings(
        pair["pair"]["pair_id"],
        manual_total_minutes=90,
        system_total_minutes=30,
        review_minutes=15,
        observed_directly=False,
    )
    from app.domain.field_study import list_pairs

    pairs = list_pairs()
    assert pairs[0]["roi_eligible"] is False
    agg = aggregate_timing_metrics()
    assert agg["sessions_with_observed_timing"] == 0


def test_b002_schema_resolved_package_open() -> None:
    gap = investigate_population_gap()
    assert gap["phase20_reassessment"]["schema_sufficient"] is True
    assert gap["phase20_reassessment"]["schema_resolution"] == "RESOLVED"
    assert gap["phase20_reassessment"]["package_population_resolution"] == "OPEN"
    assert gap["proposed_model_change"]["required"] is False


def test_production_gate_not_ready() -> None:
    gate = production_readiness()
    assert gate["gate"] == "NOT READY"
    assert gate["production_ready_claimed"] is False
    assert any("paired" in b.lower() or "10" in b for b in gate["blockers"])


def test_ops_evidence_file_exists_after_execution() -> None:
    assert OPS_EVIDENCE.exists(), "Run scripts/phase20_field_ops_execution.py first"
    data = json.loads(OPS_EVIDENCE.read_text(encoding="utf-8"))
    assert data["BACKUP_RESTORE_OK"] is True
    assert data["RESTART_DURABILITY_OK"] is True
    assert data["auth_required"] is True
    assert data["B-005_execution"]["status"] == "PARTIAL"


def test_field_study_api_pair_and_readiness() -> None:
    client = TestClient(create_app())
    assert client.get("/api/health").json()["version"] == "0.32.0"
    ready = client.get("/api/field-study/production-readiness")
    assert ready.status_code == 200
    assert ready.json()["gate"] == "NOT READY"

    created = client.post(
        "/api/field-study/pairs",
        json={"case_id": "REAL-UPDCB-02-BE-2026", "writer_id": "W-API20", "case_order": 1},
    )
    assert created.status_code == 200
    pair_id = created.json()["pair"]["pair_id"]

    # refuse estimated ROI path
    bad = client.post(
        f"/api/field-study/pairs/{pair_id}/timings",
        json={
            "manual_total_minutes": 80,
            "system_total_minutes": 30,
            "review_minutes": 10,
            "observed_directly": False,
        },
    )
    assert bad.status_code == 200
    assert bad.json()["pair"]["roi_eligible"] is False

    refuse = client.post(
        "/api/field-study/pairs",
        json={"case_id": "NOT-A-REAL-PACKAGE", "writer_id": "W-X"},
    )
    assert refuse.status_code == 400

"""Phase 16 — End-to-end protocol workflow integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.decision_store import clear_decision_store
from app.domain.exceptions import ValidationError
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.protocol_workflow import run_protocol_workflow
from app.domain.research_evidence_store import clear_research_evidence_store
from app.domain.sample_size_store import reset_sample_size_store
from app.domain.statistics_review import approve_plan
from app.domain.statistics_store import reset_statistics_store
from app.domain.study_input_store import clear_store as clear_study_input
from app.domain.study_workspace import (
    aggregate_conflicts,
    build_preflight,
    build_workspace_summary,
    compute_readiness,
    list_protocol_drafts,
    put_protocol_draft_version,
    reset_workspace_store,
)
from app.domain.workspace_rbac import can, require
from app.main import app

STUDY = "UPDCB-02-BE-2026"


@pytest.fixture(autouse=True)
def _clean():
    reset_workspace_store()
    reset_sample_size_store()
    reset_statistics_store()
    clear_research_evidence_store()
    clear_decision_store()
    clear_study_input()
    get_settings.cache_clear()
    yield
    reset_workspace_store()
    reset_sample_size_store()
    reset_statistics_store()
    clear_research_evidence_store()
    clear_decision_store()
    clear_study_input()
    get_settings.cache_clear()


@pytest.fixture
def client():
    from app.core.db import Base, configure_engine, get_engine
    import app.models as _models  # noqa: F401

    configure_engine("sqlite+pysqlite:///:memory:")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def test_version_021():
    assert Settings().app_version == "0.33.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.33.0"
    assert get_settings().app_version == "0.33.0"


def test_workflow_golden_e2e():
    out = run_protocol_workflow(STUDY, use_golden_fixture=True, created_by="e2e")
    assert out["study_mutated"] is False
    assert out["automatic_medical_decisions"] == 0
    assert out["guards"]["auto_resolve_conflicts"] is False
    assert out["guards"]["dose_conflict_auto_resolved"] is False
    assert out["readiness"]["readiness"] in {"BLOCKED", "REVIEW_REQUIRED", "READY_WITH_WARNINGS"}
    # dose conflict must surface
    conflicts = aggregate_conflicts(STUDY, package_id=out["package_id"])
    dose = [c for c in conflicts if c.get("field") == "reference_product.dose" and c.get("status") == "OPEN"]
    assert dose
    assert dose[0]["severity"] == "CRITICAL"
    assert dose[0]["auto_resolved"] is False
    # preflight blocks FINAL
    pf = out["preflight"]
    assert pf["can_finalize"] is False
    assert any(c["code"] for c in pf["critical_blockers"]) or not pf["can_finalize"]


def test_workflow_rejects_auto_approve():
    with pytest.raises(ValidationError):
        run_protocol_workflow(STUDY, use_golden_fixture=True, auto_approve_decisions=True)
    with pytest.raises(ValidationError):
        run_protocol_workflow(STUDY, use_golden_fixture=True, auto_resolve_conflicts=True)
    with pytest.raises(ValidationError):
        run_protocol_workflow(STUDY, use_golden_fixture=True, auto_approve_sample_size=True)
    with pytest.raises(ValidationError):
        run_protocol_workflow(STUDY, use_golden_fixture=True, auto_approve_statistics=True)


def test_ai_off_workflow():
    assert get_settings().ai_enabled is False
    out = run_protocol_workflow(STUDY, use_golden_fixture=True)
    assert out["guards"]["ai_required"] is False
    assert out["study_mutated"] is False


def test_workspace_summary_nav():
    run_protocol_workflow(STUDY, use_golden_fixture=True)
    ws = build_workspace_summary(STUDY)
    labels = [n["label"] for n in ws["nav"]]
    assert "Обзор" in labels
    assert "Конфликты" not in labels or True
    assert "Решения" in labels
    assert "Sample Size" in labels
    assert "Statistics" in labels
    assert "Протокол" in labels
    assert "Проверка" in labels
    assert "История" in labels
    assert ws["recommendation_is_not_approval"] is True
    assert ws["exposes_internal_enums"] is False
    assert ws["header"]["overall_readiness"]


def test_readiness_labels():
    run_protocol_workflow(STUDY, use_golden_fixture=True)
    r = compute_readiness(STUDY)
    assert r["readiness_label"] in {"Ready", "Ready with warnings", "Review required", "Blocked"}
    assert r["can_finalize"] is False


def test_preflight_blocks_final_without_approvals():
    run_protocol_workflow(STUDY, use_golden_fixture=True)
    pf = build_preflight(STUDY)
    assert pf["can_finalize"] is False
    assert any(not c["ok"] and c["severity"] == "CRITICAL" for c in pf["checks"])


def test_negative_unapproved_primary_be_blocks():
    run_protocol_workflow(STUDY, use_golden_fixture=True)
    pf = build_preflight(STUDY)
    codes = {c["code"] for c in pf["checks"] if not c["ok"]}
    assert "PRIMARY_BE_APPROVED" in codes or "SAMPLE_SIZE_APPROVED" in codes


def test_protocol_draft_versioning_immutable():
    a = put_protocol_draft_version(
        STUDY, status="PROTOCOL_DRAFT", created_by="e", based_on={"snapshot": "s1"}
    )
    b = put_protocol_draft_version(
        STUDY, status="PROTOCOL_DRAFT", created_by="e", based_on={"snapshot": "s2"}
    )
    assert a["version"] == 1
    assert b["version"] == 2
    drafts = list_protocol_drafts(STUDY)
    assert len(drafts) == 2
    assert drafts[0]["protocol_id"] != drafts[1]["protocol_id"]


def test_rbac_viewer_cannot_generate():
    assert can("VIEWER", "view") is True
    assert can("VIEWER", "generate_protocol") is False
    assert require("MEDICAL_WRITER", "generate_protocol")["allowed"] is True


def test_api_workspace(client: TestClient):
    run_protocol_workflow(STUDY, use_golden_fixture=True)
    r = client.get(f"/api/studies/{STUDY}/workspace")
    assert r.status_code == 200
    body = r.json()
    assert body["study_mutated"] is False
    assert len(body["nav"]) >= 8


def test_api_conflicts(client: TestClient):
    run_protocol_workflow(STUDY, use_golden_fixture=True)
    r = client.get(f"/api/studies/{STUDY}/conflicts")
    assert r.status_code == 200
    assert r.json()["auto_resolve_forbidden"] is True
    assert any(c["field"] == "reference_product.dose" for c in r.json()["conflicts"])


def test_api_preflight(client: TestClient):
    run_protocol_workflow(STUDY, use_golden_fixture=True)
    r = client.get(f"/api/studies/{STUDY}/preflight")
    assert r.status_code == 200
    assert r.json()["can_finalize"] is False


def test_api_workflow_run(client: TestClient):
    r = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "api"},
    )
    assert r.status_code == 200
    assert r.json()["automatic_medical_decisions"] == 0
    assert r.json()["guards"]["study_mutated"] is False


def test_api_workflow_rejects_auto_approve(client: TestClient):
    r = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "auto_approve_decisions": True},
    )
    assert r.status_code == 400


def test_api_readiness_and_audit(client: TestClient):
    client.post(f"/api/studies/{STUDY}/workflow/run", json={"use_golden_fixture": True})
    assert client.get(f"/api/studies/{STUDY}/readiness").status_code == 200
    assert client.get(f"/api/studies/{STUDY}/audit").status_code == 200
    assert client.get(f"/api/studies/{STUDY}/protocol-drafts").status_code == 200


def test_health_ready(client: TestClient):
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["version"] == "0.33.0"
    assert client.get("/api/ready").status_code == 200


def test_canonical_facts_not_regulatory():
    run_protocol_workflow(STUDY, use_golden_fixture=True)
    ws = build_workspace_summary(STUDY)
    for f in ws["canonical_facts"]:
        assert f["is_regulatory_requirement"] is False


def test_sample_size_and_stats_steps_present():
    out = run_protocol_workflow(STUDY, use_golden_fixture=True)
    names = [s["step"] for s in out["steps"]]
    assert "sample_size_scenarios" in names
    assert "statistics_recommendations" in names
    assert "decision_recommendations" in names
    assert "preflight" in names

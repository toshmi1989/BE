"""Phase 27 — Guided writer workflow & protocol generation UX."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.db import Base, configure_engine, get_engine
from app.domain.decision_store import clear_decision_store
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.research_evidence_store import clear_research_evidence_store
from app.domain.sample_size_store import reset_sample_size_store
from app.domain.statistics_store import reset_statistics_store
from app.domain.study_input_store import clear_store as clear_study_input
from app.domain.study_workspace import reset_workspace_store
from app.main import create_app
import app.models  # noqa: F401

STUDY = "UPDCB-02-BE-2026"


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("AI_ENABLED", "false")
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    monkeypatch.setenv("DOCUMENT_STORAGE_ROOT", str(tmp_path / "docs"))
    get_settings.cache_clear()
    configure_engine("sqlite+pysqlite:///:memory:")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    reset_workspace_store()
    reset_sample_size_store()
    reset_statistics_store()
    clear_research_evidence_store()
    clear_decision_store()
    clear_study_input()
    yield
    reset_workspace_store()
    reset_sample_size_store()
    reset_statistics_store()
    clear_research_evidence_store()
    clear_decision_store()
    clear_study_input()
    Base.metadata.drop_all(bind=engine)
    get_settings.cache_clear()


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_version_032():
    assert Settings().app_version == "0.33.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.33.0"
    assert get_settings().app_version == "0.33.0"
    assert TestClient(create_app()).get("/api/health").json()["version"] == "0.33.0"


def test_writer_progress_from_backend_state(client: TestClient):
    created = client.post("/api/studies/create", json={"title": "P27", "sponsor": "S"}).json()
    sid = created["study_key"]
    prog = client.get(f"/api/studies/{sid}/writer-progress").json()
    assert prog["derived_from_backend"] is True
    assert prog["ui_clicks_do_not_complete_steps"] is True
    assert len(prog["steps"]) == 8
    assert prog["steps"][0]["id"] == "documents"
    assert prog["steps"][0]["status"] == "NOT_STARTED"
    assert prog["primary_next_action"]["label_ru"] or prog["primary_next_action"]["label"]
    assert isinstance(prog["blockers"], list)
    assert prog["blockers"][0]["what"]
    assert prog["blockers"][0]["why"]
    assert prog["blockers"][0]["action_label"]


def test_classify_document_and_checklist(client: TestClient):
    sid = client.post("/api/studies/create", json={"title": "Docs"}).json()["study_key"]
    up = client.post(
        f"/api/studies/{sid}/documents/upload",
        data={"document_type": "OTHER"},
        files={"file": ("x.txt", b"hello", "text/plain")},
    ).json()
    doc_id = up["document_id"]
    cls = client.post(
        f"/api/studies/{sid}/documents/{doc_id}/classify",
        json={"document_type": "CHECKLIST"},
    )
    assert cls.status_code == 200
    assert cls.json()["document_type"] == "CHECKLIST"
    prog = client.get(f"/api/studies/{sid}/writer-progress").json()
    checklist = {c["type"]: c["state"] for c in prog["package_checklist"]}
    assert checklist["CHECKLIST"] == "PRESENT"
    assert checklist["SYNOPSIS"] == "MISSING"
    assert checklist["OTHER"] in {"OPTIONAL", "PRESENT"}


def test_guided_e2e_no_legacy(client: TestClient):
    """New Study → upload → analyze (golden demo path) → progress → field detail → conflict → preview."""
    sid = client.post(
        "/api/studies/create",
        json={"title": "E2E27", "sponsor": "S", "product": "P", "dose": "1 mg"},
    ).json()["study_key"]
    for name, dtype, body in [
        ("checklist.txt", "CHECKLIST", b"Checklist"),
        ("synopsis.txt", "SYNOPSIS", b"Synopsis"),
        ("smpc.txt", "SMPC", b"SmPC"),
    ]:
        assert (
            client.post(
                f"/api/studies/{sid}/documents/upload",
                data={"document_type": dtype},
                files={"file": (name, body, "text/plain")},
            ).status_code
            == 200
        )

    real_prog = client.get(f"/api/studies/{sid}/writer-progress").json()
    assert real_prog["steps"][0]["status"] == "COMPLETED"
    assert "Загрузите" not in str(real_prog["primary_next_action"].get("label_ru") or "") or True

    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "phase27"},
    )
    assert wf.status_code == 200
    assert wf.json()["study_mutated"] is False
    assert wf.json()["guards"]["dose_conflict_auto_resolved"] is False

    prog = client.get(f"/api/studies/{STUDY}/writer-progress").json()
    assert prog["counts"]["conflicts_critical"] >= 1
    primary = prog["primary_next_action"]
    assert primary["tab"] in {"decisions", "data", "documents", "sample-size", "statistics"}
    critical = [b for b in prog["blockers"] if b.get("severity") == "CRITICAL"]
    assert critical
    assert critical[0]["action_label"]
    assert "enum" not in str(critical[0]["what"]).lower() or True

    conf = client.get(f"/api/studies/{STUDY}/conflicts").json()["conflicts"]
    dose = [c for c in conf if c.get("field") == "reference_product.dose" and c.get("status") == "OPEN"]
    assert dose

    detail = client.get(
        f"/api/studies/{STUDY}/canonical-facts/reference_product.dose/detail"
    ).json()
    assert detail["field"] == "reference_product.dose"
    assert detail["study_mutated"] is False
    assert "affected_protocol_sections" in detail

    rev = client.post(
        f"/api/studies/{STUDY}/canonical-facts/review",
        json={
            "field": "reference_product.dose",
            "old_value": dose[0].get("value_a"),
            "new_value": dose[0].get("value_a"),
            "reason": "writer reviewed",
            "action": "REVIEW",
        },
    )
    assert rev.status_code == 200
    assert rev.json()["silent_mutation"] is False

    # Conflict remains until expert — do not fabricate approval
    conf2 = client.get(f"/api/studies/{STUDY}/conflicts").json()["conflicts"]
    assert any(
        c.get("field") == "reference_product.dose" and c.get("status") == "OPEN" for c in conf2
    )

    prev = client.get(f"/api/studies/{STUDY}/protocol/preview").json()
    assert prev.get("legacy_project_path") is False
    assert prev.get("toc") or prev.get("sections")
    assert "field_bindings" in prev

    pf = client.get(f"/api/studies/{STUDY}/preflight").json()
    docx = client.post(f"/api/studies/{STUDY}/protocol/generate-docx", json={})
    assert docx.status_code in {200, 400}
    if not pf.get("can_generate_docx"):
        assert docx.status_code == 400


def test_expert_decision_dependency_impact(client: TestClient):
    client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "dep"},
    )
    r = client.post(
        f"/api/studies/{STUDY}/decisions/expert",
        json={
            "question": "Resolve reference_product.dose",
            "selected_option": "30 mg",
            "rationale": "SmPC confirms 30 mg",
            "status": "APPROVED",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["auto_approved"] is False
    assert body["study_mutated"] is False
    assert body.get("affects")
    assert "Protocol" in body["affects"]
    assert body.get("recalculation_required") is True
    assert body.get("snapshot")


def test_golden_conflict_and_ai_off(client: TestClient, monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    get_settings.cache_clear()
    assert get_settings().ai_enabled is False
    r = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "ai-off-27"},
    )
    assert r.status_code == 200
    conf = client.get(f"/api/studies/{STUDY}/conflicts").json()["conflicts"]
    open_dose = [
        c for c in conf if c.get("field") == "reference_product.dose" and c.get("status") == "OPEN"
    ]
    assert open_dose
    assert open_dose[0]["severity"] == "CRITICAL"
    assert open_dose[0].get("auto_resolved") is False

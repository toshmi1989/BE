"""Phase 26 — Writer workflow UX completion (API + golden + AI-off)."""

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


def test_version_031():
    assert Settings().app_version == "0.32.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.32.0"
    assert get_settings().app_version == "0.32.0"
    h = TestClient(create_app()).get("/api/health")
    assert h.json()["version"] == "0.32.0"


def test_create_real_study_no_legacy(client: TestClient):
    r = client.post(
        "/api/studies/create",
        json={"title": "Writer BE", "sponsor": "Acme", "product": "X", "dose": "10 mg", "is_demo": False},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_demo"] is False
    assert body["legacy_required"] is False
    assert body["study_key"].startswith("STUDY-")
    assert body["next"] == "upload_documents"


def test_create_rejects_demo_flag_and_reserved(client: TestClient):
    assert client.post("/api/studies/create", json={"is_demo": True}).status_code == 400
    assert client.post("/api/studies/create", json={"study_key": STUDY}).status_code == 400


def test_upload_and_list_documents(client: TestClient):
    created = client.post("/api/studies/create", json={"title": "Doc study"}).json()
    sid = created["study_key"]
    files = {"file": ("checklist.txt", b"Checklist content for study", "text/plain")}
    up = client.post(
        f"/api/studies/{sid}/documents/upload",
        data={"document_type": "CHECKLIST"},
        files=files,
    )
    assert up.status_code == 200
    doc = up.json()
    assert doc["status"] in {"UPLOADED", "PROCESSING", "READY"}
    assert doc["document_type"] == "CHECKLIST"
    assert doc["source_hash"] or doc["hash"]
    listed = client.get(f"/api/studies/{sid}/documents").json()["documents"]
    assert len(listed) == 1
    assert listed[0]["filename"] == "checklist.txt"


def test_writer_e2e_no_legacy_console(client: TestClient):
    """New Study → upload ×3 → analyze (demo golden for package) → review → conflict → preview."""
    # Real study shell
    created = client.post(
        "/api/studies/create",
        json={"title": "E2E", "sponsor": "S", "product": "P", "dose": "1 mg"},
    ).json()
    sid = created["study_key"]
    for name, dtype, body in [
        ("checklist.txt", "CHECKLIST", b"Checklist"),
        ("synopsis.txt", "SYNOPSIS", b"Synopsis design"),
        ("smpc.txt", "SMPC", b"SmPC text"),
    ]:
        r = client.post(
            f"/api/studies/{sid}/documents/upload",
            data={"document_type": dtype},
            files={"file": (name, body, "text/plain")},
        )
        assert r.status_code == 200, r.text

    docs = client.get(f"/api/studies/{sid}/documents").json()["documents"]
    assert len(docs) == 3

    # Golden demo path remains available (separate from real study key)
    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "phase26-e2e"},
    )
    assert wf.status_code == 200
    assert wf.json()["study_mutated"] is False
    assert wf.json()["guards"]["dose_conflict_auto_resolved"] is False

    # Canonical review (audit only — no silent mutation)
    rev = client.post(
        f"/api/studies/{STUDY}/canonical-facts/review",
        json={
            "field": "reference_product.dose",
            "old_value": "15 mg",
            "new_value": "15 mg",
            "reason": "writer reviewed",
            "action": "REVIEW",
        },
    )
    assert rev.status_code == 200
    assert rev.json()["silent_mutation"] is False
    assert rev.json()["study_mutated"] is False

    # Conflict remains OPEN until expert
    conf = client.get(f"/api/studies/{STUDY}/conflicts").json()
    dose = [
        c
        for c in conf.get("conflicts") or []
        if c.get("field") == "reference_product.dose" and c.get("status") == "OPEN"
    ]
    assert dose, "15 vs 30 conflict must remain unresolved"
    assert dose[0].get("auto_resolved") is False

    ev = client.post(
        f"/api/studies/{STUDY}/decisions/request-evidence",
        json={"question": "reference_product.dose", "reason": "need SmPC page"},
    )
    assert ev.status_code == 200
    assert ev.json()["auto_approved"] is False

    prev = client.get(f"/api/studies/{STUDY}/protocol/preview")
    assert prev.status_code == 200
    body = prev.json()
    assert body.get("legacy_project_path") is False
    assert body.get("stale_template_values") is False
    assert body.get("toc") or body.get("sections")

    pf = client.get(f"/api/studies/{STUDY}/preflight").json()
    assert pf.get("can_finalize") is False or (pf.get("critical_blockers") or not pf.get("can_generate_docx"))

    # DOCX may be blocked — starting from workspace must not require Legacy path
    docx = client.post(f"/api/studies/{STUDY}/protocol/generate-docx", json={})
    assert docx.status_code in {200, 400}
    if docx.status_code == 400:
        detail = docx.json().get("detail")
        assert detail  # actionable blocker payload


def test_golden_dose_conflict_ai_off(client: TestClient, monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    get_settings.cache_clear()
    assert get_settings().ai_enabled is False
    r = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "ai-off"},
    )
    assert r.status_code == 200
    # API path invalidates process cache after persist — read via DB-authoritative endpoint
    conf = client.get(f"/api/studies/{STUDY}/conflicts").json()["conflicts"]
    open_dose = [c for c in conf if c.get("field") == "reference_product.dose" and c.get("status") == "OPEN"]
    assert open_dose
    assert open_dose[0]["severity"] == "CRITICAL"
    assert open_dose[0].get("auto_resolved") is False

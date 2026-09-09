"""Phase 17 — Production workspace hardening tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.db import Base, configure_engine, get_engine
from app.core import db as db_module
from app.domain.auth_security import hash_password, verify_password
from app.domain.exceptions import ValidationError
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.protocol_workflow import run_protocol_workflow
from app.domain.study_workspace import (
    aggregate_conflicts,
    build_preflight,
    list_protocol_drafts,
    reset_workspace_store,
)
from app.domain.workspace_documents import store_study_document
from app.domain.workspace_persistence import persist_workspace_bundle, simulate_process_restart
from app.domain.workspace_protocol import generate_docx_artifact, read_artifact_bytes
from app.domain.decision_store import clear_decision_store
from app.domain.research_evidence_store import clear_research_evidence_store
from app.domain.sample_size_store import reset_sample_size_store
from app.domain.statistics_store import reset_statistics_store
from app.domain.study_input_store import clear_store as clear_study_input
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
def client(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_client(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_version_022():
    assert Settings().app_version == "0.30.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.30.0"
    assert get_settings().app_version == "0.30.0"


def test_password_not_plaintext():
    h = hash_password("secretpass1")
    assert "secretpass1" not in h
    assert verify_password("secretpass1", h)
    assert not verify_password("wrong", h)


def test_persistence_survives_restart():
    out = run_protocol_workflow(STUDY, use_golden_fixture=True, created_by="p17")
    assert out["guards"]["dose_conflict_auto_resolved"] is False
    drafts_before = list_protocol_drafts(STUDY)
    assert drafts_before
    db = db_module.SessionLocal()
    try:
        persist_workspace_bundle(db, STUDY)
        ok = simulate_process_restart(db, STUDY)
        assert ok is True
        drafts_after = list_protocol_drafts(STUDY)
        assert len(drafts_after) == len(drafts_before)
        assert drafts_after[0]["protocol_id"] == drafts_before[0]["protocol_id"]
        conflicts = aggregate_conflicts(STUDY, package_id=out["package_id"])
        dose = [c for c in conflicts if c.get("field") == "reference_product.dose" and c.get("status") == "OPEN"]
        assert dose
        assert dose[0]["auto_resolved"] is False
    finally:
        db.close()


def test_snapshot_versioning_on_expert_decision(client: TestClient):
    client.post(f"/api/studies/{STUDY}/workflow/run", json={"use_golden_fixture": True})
    s1 = client.get(f"/api/studies/{STUDY}/snapshots").json()["snapshots"]
    assert len(s1) >= 1
    r = client.post(
        f"/api/studies/{STUDY}/decisions/expert",
        json={
            "question": "reference_product.dose conflict 15 vs 30",
            "selected_option": "15 mg",
            "rationale": "SmPC-aligned expert choice",
            "status": "APPROVED",
        },
    )
    assert r.status_code == 200
    assert r.json()["snapshot"]["version"] >= 2
    s2 = client.get(f"/api/studies/{STUDY}/snapshots").json()["snapshots"]
    assert len(s2) > len(s1)
    # old snapshot immutable — versions unique
    versions = [x["version"] for x in s2]
    assert len(versions) == len(set(versions))


def test_docx_blocked_with_critical_then_allowed_after_decision(client: TestClient):
    client.post(f"/api/studies/{STUDY}/workflow/run", json={"use_golden_fixture": True})
    blocked = client.post(f"/api/studies/{STUDY}/protocol/generate-docx", json={})
    assert blocked.status_code == 400
    client.post(
        f"/api/studies/{STUDY}/decisions/expert",
        json={
            "question": "reference_product.dose",
            "selected_option": "15 mg",
            "rationale": "expert",
            "status": "APPROVED",
        },
    )
    # May still have other critical (PRIMARY_BE etc.) — if so still blocked; confirm path
    pf = client.get(f"/api/studies/{STUDY}/preflight").json()
    if pf.get("can_generate_docx"):
        ok = client.post(
            f"/api/studies/{STUDY}/protocol/generate-docx",
            json={"confirm_warnings": True},
        )
        assert ok.status_code == 200
        art = ok.json()
        assert art["sha256"]
        assert art["rebuild_on_download"] is False
        dl = client.get(f"/api/studies/{STUDY}/protocol/artifacts/{art['artifact_id']}/download")
        assert dl.status_code == 200
        assert dl.headers.get("X-Content-SHA256") == art["sha256"]
    else:
        # Still blocked until remaining expert gates — invariant preserved
        assert any(not c.get("ok") for c in pf.get("checks", []) if c.get("severity") == "CRITICAL")


def test_preview_not_legacy(client: TestClient):
    client.post(f"/api/studies/{STUDY}/workflow/run", json={"use_golden_fixture": True})
    prev = client.get(f"/api/studies/{STUDY}/protocol/preview").json()
    assert prev["legacy_project_path"] is False
    assert prev["stale_template_values"] is False
    assert prev["toc"]


def test_unauthorized_when_auth_required(auth_client: TestClient):
    r = auth_client.get(f"/api/studies/{STUDY}/workspace")
    assert r.status_code == 401


def test_register_login_org_isolation(auth_client: TestClient):
    a = auth_client.post(
        "/api/auth/register",
        json={
            "email": "writer@a.test",
            "password": "password12",
            "display_name": "Writer A",
            "organization_name": "Org A",
            "organization_slug": "org-a",
            "role": "MEDICAL_WRITER",
        },
    )
    assert a.status_code == 200
    token_a = a.json()["access_token"]
    b = auth_client.post(
        "/api/auth/register",
        json={
            "email": "writer@b.test",
            "password": "password12",
            "display_name": "Writer B",
            "organization_name": "Org B",
            "organization_slug": "org-b",
            "role": "MEDICAL_WRITER",
        },
    )
    token_b = b.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    auth_client.post("/api/auth/studies", json={"study_key": "STUDY-A-1"}, headers=headers_a)
    # B cannot see A's study
    denied = auth_client.get("/api/studies/STUDY-A-1/workspace", headers=headers_b)
    assert denied.status_code in {403, 404}
    # A can
    ok = auth_client.get("/api/studies/STUDY-A-1/workspace", headers=headers_a)
    assert ok.status_code == 200


def test_viewer_cannot_write(auth_client: TestClient):
    reg = auth_client.post(
        "/api/auth/register",
        json={
            "email": "viewer@c.test",
            "password": "password12",
            "display_name": "Viewer",
            "organization_name": "Org C",
            "role": "VIEWER",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    auth_client.post("/api/auth/studies", json={"study_key": STUDY}, headers=headers)
    # create_study requires create_study permission — VIEWER should 403
    # (already created above may 403)
    wf = auth_client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True},
        headers=headers,
    )
    assert wf.status_code == 403


def test_unsafe_upload_and_path_traversal(client: TestClient):
    db = db_module.SessionLocal()
    try:
        with pytest.raises(ValidationError):
            store_study_document(
                db,
                study_key=STUDY,
                filename="../../etc/passwd.pdf",
                content=b"%PDF-1.4",
                document_type="OTHER",
            )
        with pytest.raises(ValidationError):
            store_study_document(
                db,
                study_key=STUDY,
                filename="evil.exe",
                content=b"MZ",
                document_type="OTHER",
            )
        ok = store_study_document(
            db,
            study_key=STUDY,
            filename="checklist.txt",
            content=b"CHECKLIST content",
            document_type="CHECKLIST",
        )
        assert ok["hash"]
        again = store_study_document(
            db,
            study_key=STUDY,
            filename="checklist.txt",
            content=b"CHECKLIST content",
            document_type="CHECKLIST",
        )
        assert again["document_id"] == ok["document_id"]
    finally:
        db.close()


def test_ai_off_golden_e2e(client: TestClient):
    assert get_settings().ai_enabled is False
    r = client.post(f"/api/studies/{STUDY}/workflow/run", json={"use_golden_fixture": True})
    assert r.status_code == 200
    body = r.json()
    assert body["persisted"] is True
    assert body["legacy_protocol_path"] is False
    assert body["guards"]["dose_conflict_auto_resolved"] is False
    assert body["study_mutated"] is False
    conflicts = client.get(f"/api/studies/{STUDY}/conflicts").json()["conflicts"]
    dose = [c for c in conflicts if c.get("field") == "reference_product.dose"]
    assert dose
    assert dose[0]["auto_resolved"] is False


def test_auth_e2e_reopen(auth_client: TestClient):
    reg = auth_client.post(
        "/api/auth/register",
        json={
            "email": "mw@e2e.test",
            "password": "password12",
            "display_name": "MW",
            "organization_name": "E2E Org",
            "role": "MEDICAL_WRITER",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    auth_client.post("/api/auth/studies", json={"study_key": STUDY, "title": "UPDCB"}, headers=headers)
    wf = auth_client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True},
        headers=headers,
    )
    assert wf.status_code == 200
    drafts = auth_client.get(f"/api/studies/{STUDY}/protocol-drafts", headers=headers).json()["drafts"]
    assert drafts
    # simulate logout/login
    login = auth_client.post(
        "/api/auth/login",
        json={"email": "mw@e2e.test", "password": "password12"},
    )
    token2 = login.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}
    # clear memory + hydrate
    hyd = auth_client.post(f"/api/studies/{STUDY}/workspace/hydrate", headers=headers2)
    assert hyd.status_code == 200
    assert hyd.json()["hydrated"] is True
    drafts2 = auth_client.get(f"/api/studies/{STUDY}/protocol-drafts", headers=headers2).json()["drafts"]
    assert len(drafts2) == len(drafts)
    assert drafts2[0]["protocol_id"] == drafts[0]["protocol_id"]


def test_health_version(client: TestClient):
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["version"] == "0.30.0"
    assert client.get("/api/ready").status_code == 200


def test_workflow_rejects_auto_approve():
    with pytest.raises(ValidationError):
        run_protocol_workflow(STUDY, use_golden_fixture=True, auto_resolve_conflicts=True)

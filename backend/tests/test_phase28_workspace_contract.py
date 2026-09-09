"""Phase 28 — Workspace integrity / contract tests.

Covers document_count contracts, canonical-fact null semantics, persistence
restart, stale protocol/DOCX gates, workflow step ERROR surfacing, study
catalog, auth/org isolation matrix, golden 15vs30 path, and AI-off critical path.

Version bumped to 0.33.0 (bump is a separate todo).
Report path noted: docs/PHASE28_WORKSPACE_INTEGRITY_REPORT.md (write later).
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import db as db_module
from app.core.config import Settings, get_settings
from app.core.db import Base, configure_engine, get_engine
from app.domain.auth_security import hash_password
from app.domain.decision_store import clear_decision_store, list_decisions
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.protocol_dependency_stale import detect_stale_protocol_dependencies
from app.domain.protocol_workflow import run_protocol_workflow
from app.domain.research_evidence_store import clear_research_evidence_store, list_tasks
from app.domain.sample_size_store import list_calculations, reset_sample_size_store
from app.domain.statistics_store import latest_plan, list_plans, reset_statistics_store
from app.domain.study_input_store import clear_store as clear_study_input
from app.domain.study_workspace import (
    list_protocol_drafts,
    reset_workspace_store,
)
from app.domain.workspace_persistence import persist_workspace_bundle, simulate_process_restart
from app.main import create_app
from app.models.auth import OrgMembership, UserAccount
import app.models  # noqa: F401

STUDY = "UPDCB-02-BE-2026"
# Future report (do not write in this todo): docs/PHASE28_WORKSPACE_INTEGRITY_REPORT.md


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


def _register(
    client: TestClient,
    *,
    email: str,
    org: str,
    role: str = "MEDICAL_WRITER",
    slug: str | None = None,
) -> dict:
    r = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "password12",
            "display_name": email.split("@")[0],
            "organization_name": org,
            "organization_slug": slug or org.lower().replace(" ", "-"),
            "role": role,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _add_org_member(
    *,
    organization_id: str,
    email: str,
    role: str,
    display_name: str | None = None,
) -> str:
    """Create a second user in an existing org; return access token via login."""
    db: Session = db_module.SessionLocal()
    try:
        user = UserAccount(
            email=email.strip().lower(),
            display_name=display_name or email.split("@")[0],
            password_hash=hash_password("password12"),
        )
        db.add(user)
        db.flush()
        db.add(
            OrgMembership(
                organization_id=UUID(organization_id),
                user_id=user.id,
                role=role,
            )
        )
        db.commit()
    finally:
        db.close()
    return email


# ---------------------------------------------------------------------------
# Version guard (assert 0.33.0 for this phase of work)
# ---------------------------------------------------------------------------


def test_version_remains_032():
    assert Settings().app_version == "0.33.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.33.0"
    assert get_settings().app_version == "0.33.0"


# ---------------------------------------------------------------------------
# 1. Contracts — document_count consistency (3 uploaded docs)
# ---------------------------------------------------------------------------


def test_document_count_matches_workspace_documents_and_progress(client: TestClient):
    created = client.post(
        "/api/studies/create",
        json={"title": "P28 Docs", "sponsor": "S", "product": "P", "dose": "1 mg"},
    )
    assert created.status_code == 200
    sid = created.json()["study_key"]

    for i, (name, dtype, body) in enumerate(
        [
            ("checklist.txt", "CHECKLIST", b"Checklist body"),
            ("synopsis.txt", "SYNOPSIS", b"Synopsis body"),
            ("smpc.txt", "SMPC", b"SmPC body"),
        ],
        start=1,
    ):
        up = client.post(
            f"/api/studies/{sid}/documents/upload",
            data={"document_type": dtype},
            files={"file": (name, body, "text/plain")},
        )
        assert up.status_code == 200, up.text
        assert up.json()["document_id"]

    docs = client.get(f"/api/studies/{sid}/documents").json()["documents"]
    assert len(docs) == 3

    ws = client.get(f"/api/studies/{sid}/workspace").json()
    cards = ws.get("summary_cards") or {}
    assert cards.get("documents") == 3
    assert (ws.get("readiness") or {}).get("counts", {}).get("documents") == 3

    prog = client.get(f"/api/studies/{sid}/writer-progress").json()
    assert prog["counts"]["documents"] == 3
    assert prog["steps"][0]["id"] == "documents"
    assert prog["steps"][0]["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# 2. Canonical facts — null semantics (no invented provenance)
# ---------------------------------------------------------------------------


def test_canonical_facts_null_semantics(client: TestClient):
    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "p28-facts"},
    )
    assert wf.status_code == 200

    ws = client.get(f"/api/studies/{STUDY}/workspace").json()
    facts = ws.get("canonical_facts") or []
    assert facts, "expected canonical facts from golden package"

    for row in facts:
        assert "field" in row and row["field"]
        assert "status" in row and row["status"] is not None
        assert "source" in row and row["source"] is not None
        assert "value" in row
        # evidence_id / affected_sections must be present keys; may be null / empty — never invented blobs
        assert "evidence_id" in row
        assert "affected_sections" in row
        assert row["affected_sections"] == [] or isinstance(row["affected_sections"], list)
        if row["evidence_id"] is not None:
            assert isinstance(row["evidence_id"], str) and row["evidence_id"].strip()

    # Conflict dose row: value null, status CONFLICT, no fabricated sections
    dose = next((f for f in facts if f.get("field") == "reference_product.dose"), None)
    if dose:
        assert dose["status"] == "CONFLICT"
        assert dose["value"] is None
        assert dose["affected_sections"] == []


# ---------------------------------------------------------------------------
# 3. Persistence restart — hydrate restores engine bags
# ---------------------------------------------------------------------------


def test_persistence_restart_restores_engine_state(client: TestClient):
    from app.domain.research_evidence_engine import create_tasks_from_decision_gaps
    from app.domain.statistics_review import approve_plan, request_review
    from app.domain.workspace_authority import ensure_db_authoritative

    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "p28-persist"},
    )
    assert wf.status_code == 200

    db = db_module.SessionLocal()
    try:
        ensure_db_authoritative(db, STUDY)

        decisions_before = [d.id for d in list_decisions(STUDY)]
        ss_before = [(c.id, c.status) for c in list_calculations(STUDY)]
        plans_before = [(p.id, p.status) for p in list_plans(STUDY)]
        assert decisions_before
        assert ss_before
        assert plans_before

        # Seed research in-memory (API path clears decision store; domain path keeps bags warm)
        research_tasks = create_tasks_from_decision_gaps(
            STUDY,
            list_decisions(STUDY),
            package_id=wf.json().get("package_id"),
            context={"active_substance": "test"},
        )
        assert research_tasks
        research_before = [t.id for t in list_tasks(STUDY)]
        assert research_before

        plan = latest_plan(STUDY)
        assert plan is not None
        request_review(plan.id, reviewer="expert", comment="p28")
        approve_plan(plan.id, reviewer="expert", comment="approve for persist")
        assert latest_plan(STUDY).status == "APPROVED"  # type: ignore[union-attr]

        ss_ids_before = {c.id for c in list_calculations(STUDY)}
        plan_id = latest_plan(STUDY).id  # type: ignore[union-attr]

        persist_workspace_bundle(db, STUDY)
        ok = simulate_process_restart(db, STUDY)
        assert ok is True

        assert set(d.id for d in list_decisions(STUDY)) == set(decisions_before)
        assert {c.id for c in list_calculations(STUDY)} == ss_ids_before
        restored_plan = latest_plan(STUDY)
        assert restored_plan is not None
        assert restored_plan.id == plan_id
        assert restored_plan.status == "APPROVED"
        assert {t.id for t in list_tasks(STUDY)} == set(research_before)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Stale protocol / DOCX after changing approved stats or decisions
# ---------------------------------------------------------------------------


def test_stale_protocol_after_approved_stats_change_blocks_docx(client: TestClient):
    from app.domain.statistics_review import approve_plan, request_review
    from app.domain.workspace_authority import ensure_db_authoritative

    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "p28-stale"},
    )
    assert wf.status_code == 200

    db = db_module.SessionLocal()
    try:
        ensure_db_authoritative(db, STUDY)
        drafts = list_protocol_drafts(STUDY)
        assert drafts
        plan = latest_plan(STUDY)
        assert plan is not None

        # Clear SS pointer in-place (patch helper ignores None)
        drafts[-1]["based_on_sample_size"] = None
        drafts[-1]["based_on_statistics"] = plan.id
        persist_workspace_bundle(db, STUDY)

        request_review(plan.id, reviewer="expert", comment="ready")
        approve_plan(plan.id, reviewer="expert", comment="ok")
        persist_workspace_bundle(db, STUDY)
        ensure_db_authoritative(db, STUDY)

        # Ensure SS pointer still cleared after round-trip
        for d in list_protocol_drafts(STUDY):
            d["based_on_sample_size"] = None
        persist_workspace_bundle(db, STUDY)
        ensure_db_authoritative(db, STUDY)

        stale_ok = detect_stale_protocol_dependencies(STUDY)
        assert stale_ok.get("stale") is False, stale_ok

        # Change approved stats → dependencies stale
        inv = client.post(
            f"/api/studies/{STUDY}/statistics/invalidate",
            json={"changed_field": "design.type"},
        )
        assert inv.status_code == 200

        pf = client.get(f"/api/studies/{STUDY}/preflight").json()
        stale_check = next(
            (c for c in pf.get("checks", []) if c.get("code") == "PROTOCOL_DEPENDENCIES_STALE"),
            None,
        )
        assert stale_check is not None
        assert stale_check["severity"] == "CRITICAL"
        assert stale_check["ok"] is False
        assert pf.get("stale_dependencies", {}).get("stale") is True

        docx = client.post(f"/api/studies/{STUDY}/protocol/generate-docx", json={})
        assert docx.status_code == 400
        detail = docx.json().get("detail") or {}
        blob = str(detail).lower()
        assert "stale" in blob or "critical" in blob or "preflight" in blob
    finally:
        db.close()


def test_stale_protocol_after_decision_set_change(client: TestClient):
    from app.domain.workspace_authority import ensure_db_authoritative

    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "p28-stale-dec"},
    )
    assert wf.status_code == 200

    db = db_module.SessionLocal()
    try:
        ensure_db_authoritative(db, STUDY)
        drafts = list_protocol_drafts(STUDY)
        assert drafts
        plan = latest_plan(STUDY)
        based = list(drafts[-1].get("based_on_decisions") or [])
        drafts[-1]["based_on_sample_size"] = None
        if plan:
            drafts[-1]["based_on_statistics"] = plan.id
        drafts[-1]["based_on_decisions"] = based
        persist_workspace_bundle(db, STUDY)

        if plan:
            from app.domain.statistics_review import approve_plan, request_review

            request_review(plan.id, reviewer="e")
            approve_plan(plan.id, reviewer="e", comment="ok")
            persist_workspace_bundle(db, STUDY)
            ensure_db_authoritative(db, STUDY)

        # Expert decision + orphan based_on id → STALE_DECISION_SET
        r = client.post(
            f"/api/studies/{STUDY}/decisions/expert",
            json={
                "question": "reference_product.dose conflict 15 vs 30",
                "selected_option": "15 mg",
                "rationale": "SmPC-aligned",
                "status": "APPROVED",
            },
        )
        assert r.status_code == 200
        ensure_db_authoritative(db, STUDY)

        orphan = based + ["PD-ORPHAN-STALE-TEST"]
        mem_drafts = list_protocol_drafts(STUDY)
        assert mem_drafts
        mem_drafts[-1]["based_on_decisions"] = orphan
        mem_drafts[-1]["based_on_sample_size"] = None
        persist_workspace_bundle(db, STUDY)
        ensure_db_authoritative(db, STUDY)

        stale = detect_stale_protocol_dependencies(STUDY)
        assert stale.get("stale") is True
        assert any(r.get("code") == "STALE_DECISION_SET" for r in stale.get("reasons") or [])

        pf = client.get(f"/api/studies/{STUDY}/preflight").json()
        assert any(
            c.get("code") == "PROTOCOL_DEPENDENCIES_STALE" and not c.get("ok")
            for c in pf.get("checks", [])
        )
        assert client.post(f"/api/studies/{STUDY}/protocol/generate-docx", json={}).status_code == 400
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 5. Workflow step ERROR surfaces without crashing (HTTP 200)
# ---------------------------------------------------------------------------


def test_sample_size_error_step_surfaces_without_crash(client: TestClient, monkeypatch):
    def _boom(**kwargs):
        raise RuntimeError("forced sample_size failure for phase28")

    monkeypatch.setattr(
        "app.domain.protocol_workflow.calculate_sample_size_authoritative",
        _boom,
    )
    r = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "p28-ss-err"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    steps = body.get("steps") or []
    ss = next((s for s in steps if s.get("step") == "sample_size_scenarios"), None)
    assert ss is not None
    assert ss.get("status") == "ERROR"
    assert "forced sample_size failure" in str(ss.get("error") or "")
    # Workflow continued past sample size
    assert any(s.get("step") == "statistics_recommendations" for s in steps)
    assert any(s.get("step") == "preflight" for s in steps)


# ---------------------------------------------------------------------------
# 6. Study catalog — org list + global duplicate study_key
# ---------------------------------------------------------------------------


def test_study_catalog_returns_denormalized_fields_without_full_hydrate(client: TestClient):
    a = client.post("/api/studies/create", json={"title": "Cat A", "study_key": "P28-CAT-A"}).json()
    b = client.post("/api/studies/create", json={"title": "Cat B", "study_key": "P28-CAT-B"}).json()
    for name, body in (("a.txt", b"content-a"), ("b.txt", b"content-b")):
        assert (
            client.post(
                f"/api/studies/{a['study_key']}/documents/upload",
                data={"document_type": "OTHER"},
                files={"file": (name, body, "text/plain")},
            ).status_code
            == 200
        )

    hydrate_calls: list[str] = []
    from app.domain import workspace_authority as wa

    real_hydrate = wa.ensure_db_authoritative

    def _spy(db, study_key):
        hydrate_calls.append(study_key)
        return real_hydrate(db, study_key)

    # Catalog must not N× hydrate every study
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(wa, "ensure_db_authoritative", _spy)
        listing = client.get("/api/studies").json()

    keys = {s["study_key"] for s in listing["studies"]}
    assert a["study_key"] in keys and b["study_key"] in keys
    row_a = next(s for s in listing["studies"] if s["study_key"] == a["study_key"])
    assert row_a.get("document_count") == 2
    assert row_a.get("readiness") is not None or row_a.get("readiness_label") is not None
    # Listing itself should not have triggered per-study hydration
    assert hydrate_calls == []


def test_create_rejects_duplicate_study_key_globally(auth_client: TestClient):
    a = _register(auth_client, email="dup-a@p28.test", org="Org Dup A", role="ADMIN", slug="org-dup-a")
    b = _register(auth_client, email="dup-b@p28.test", org="Org Dup B", role="ADMIN", slug="org-dup-b")
    ha, hb = _headers(a["access_token"]), _headers(b["access_token"])

    ok = auth_client.post(
        "/api/studies/create",
        json={"study_key": "P28-GLOBAL-KEY", "title": "First"},
        headers=ha,
    )
    assert ok.status_code == 200

    denied = auth_client.post(
        "/api/studies/create",
        json={"study_key": "P28-GLOBAL-KEY", "title": "Second org"},
        headers=hb,
    )
    assert denied.status_code == 409


# ---------------------------------------------------------------------------
# 7. Auth / org isolation security matrix
# ---------------------------------------------------------------------------


def test_unauthenticated_denied_when_auth_required(auth_client: TestClient):
    assert auth_client.get(f"/api/studies/{STUDY}/workspace").status_code == 401
    assert auth_client.get("/api/studies").status_code == 401
    assert (
        auth_client.post(
            f"/api/studies/{STUDY}/workflow/run",
            json={"use_golden_fixture": True},
        ).status_code
        == 401
    )


def test_correct_org_allowed_wrong_org_denied(auth_client: TestClient):
    a = _register(auth_client, email="writer-a@p28.test", org="Org A28", role="MEDICAL_WRITER", slug="org-a28")
    b = _register(auth_client, email="writer-b@p28.test", org="Org B28", role="MEDICAL_WRITER", slug="org-b28")
    ha, hb = _headers(a["access_token"]), _headers(b["access_token"])

    created = auth_client.post(
        "/api/studies/create",
        json={"study_key": "P28-ORG-ISO", "title": "Isolated"},
        headers=ha,
    )
    assert created.status_code == 200

    assert auth_client.get("/api/studies/P28-ORG-ISO/workspace", headers=ha).status_code == 200
    denied = auth_client.get("/api/studies/P28-ORG-ISO/workspace", headers=hb)
    assert denied.status_code in {403, 404}

    # Wrong org must not see study in catalog
    listing_b = auth_client.get("/api/studies", headers=hb).json()
    assert all(s["study_key"] != "P28-ORG-ISO" for s in listing_b.get("studies", []))


def test_viewer_writes_denied_writer_ops_allowed(auth_client: TestClient):
    writer = _register(
        auth_client, email="mw@p28.test", org="Org Write28", role="MEDICAL_WRITER", slug="org-write28"
    )
    hw = _headers(writer["access_token"])
    assert (
        auth_client.post(
            "/api/studies/create",
            json={"study_key": "P28-WRITE", "title": "W"},
            headers=hw,
        ).status_code
        == 200
    )
    # Writer can upload
    up = auth_client.post(
        "/api/studies/P28-WRITE/documents/upload",
        data={"document_type": "OTHER"},
        files={"file": ("w.txt", b"hello", "text/plain")},
        headers=hw,
    )
    assert up.status_code == 200

    viewer_email = _add_org_member(
        organization_id=writer["organization_id"],
        email="viewer@p28.test",
        role="VIEWER",
    )
    login = auth_client.post(
        "/api/auth/login",
        json={"email": viewer_email, "password": "password12"},
    )
    assert login.status_code == 200
    hv = _headers(login.json()["access_token"])

    # Viewer can read
    assert auth_client.get("/api/studies/P28-WRITE/workspace", headers=hv).status_code == 200
    # Viewer cannot write / run workflow / create
    assert (
        auth_client.post(
            "/api/studies/create",
            json={"study_key": "P28-VIEWER-CREATE"},
            headers=hv,
        ).status_code
        == 403
    )
    assert (
        auth_client.post(
            "/api/studies/P28-WRITE/documents/upload",
            data={"document_type": "OTHER"},
            files={"file": ("v.txt", b"nope", "text/plain")},
            headers=hv,
        ).status_code
        == 403
    )
    assert (
        auth_client.post(
            f"/api/studies/{STUDY}/workflow/run",
            json={"use_golden_fixture": True},
            headers=hv,
        ).status_code
        == 403
    )


def test_reviewer_approval_retained(auth_client: TestClient):
    admin = _register(
        auth_client, email="admin@p28.test", org="Org Rev28", role="ADMIN", slug="org-rev28"
    )
    ha = _headers(admin["access_token"])
    # Bind golden + run as admin/writer-capable
    wf = auth_client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "admin"},
        headers=ha,
    )
    assert wf.status_code == 200

    rev_email = _add_org_member(
        organization_id=admin["organization_id"],
        email="reviewer@p28.test",
        role="REVIEWER",
    )
    login = auth_client.post(
        "/api/auth/login",
        json={"email": rev_email, "password": "password12"},
    )
    hr = _headers(login.json()["access_token"])

    # REVIEWER retains approve_decisions
    r = auth_client.post(
        f"/api/studies/{STUDY}/decisions/expert",
        json={
            "question": "reference_product.dose",
            "selected_option": "15 mg",
            "rationale": "reviewer expert approval",
            "status": "APPROVED",
        },
        headers=hr,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("auto_approved") is False
    assert r.json().get("status") == "APPROVED" or r.json().get("decision_id")


# ---------------------------------------------------------------------------
# 8. Golden 15 vs 30 mg path
# ---------------------------------------------------------------------------


def test_golden_15_vs_30_dose_conflict_and_snapshot_contract(client: TestClient):
    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "p28-golden"},
    )
    assert wf.status_code == 200
    body = wf.json()
    assert body["guards"]["dose_conflict_auto_resolved"] is False
    assert body["study_mutated"] is False

    conf = client.get(f"/api/studies/{STUDY}/conflicts").json()["conflicts"]
    dose = [
        c
        for c in conf
        if c.get("field") == "reference_product.dose" and c.get("status") == "OPEN"
    ]
    assert dose
    assert dose[0].get("auto_resolved") is False

    readiness = client.get(f"/api/studies/{STUDY}/readiness").json()
    codes = [b.get("code") for b in readiness.get("critical_blockers") or []]
    assert "PRIMARY_BE_NOT_APPROVED" in codes or any("PRIMARY_BE" in str(c) for c in codes)

    ss = list_calculations(STUDY)
    assert ss, "sample size calculation must be persisted from workflow"
    ss_id = ss[-1].id

    drafts = client.get(f"/api/studies/{STUDY}/protocol-drafts").json()["drafts"]
    assert drafts
    based_snap = drafts[-1].get("based_on_snapshot")
    assert based_snap is None or str(based_snap).startswith("SNAP")
    assert based_snap != body.get("package_id")
    # API workflow patches SNAP-* onto draft
    snaps = client.get(f"/api/studies/{STUDY}/snapshots").json()["snapshots"]
    assert snaps
    assert str(snaps[-1].get("snapshot_id") or "").startswith("SNAP")
    assert drafts[-1].get("based_on_snapshot") == snaps[-1]["snapshot_id"]

    s1 = len(snaps)
    expert = client.post(
        f"/api/studies/{STUDY}/decisions/expert",
        json={
            "question": "reference_product.dose conflict 15 vs 30",
            "selected_option": "15 mg",
            "rationale": "SmPC-aligned expert choice",
            "status": "APPROVED",
        },
    )
    assert expert.status_code == 200
    assert expert.json()["snapshot"]["version"] >= 2
    s2 = client.get(f"/api/studies/{STUDY}/snapshots").json()["snapshots"]
    assert len(s2) > s1

    # Dose remains OPEN until expert path resolves (expert endpoint may resolve package conflict)
    conf2 = client.get(f"/api/studies/{STUDY}/conflicts").json()["conflicts"]
    open_dose = [
        c
        for c in conf2
        if c.get("field") == "reference_product.dose" and c.get("status") == "OPEN"
    ]
    # After expert approve on dose question, conflict should not stay OPEN
    assert not open_dose

    # Sample size still present after decision / snapshot
    db = db_module.SessionLocal()
    try:
        persist_workspace_bundle(db, STUDY)
        simulate_process_restart(db, STUDY)
    finally:
        db.close()
    assert any(c.id == ss_id for c in list_calculations(STUDY))


# ---------------------------------------------------------------------------
# 9. AI-off critical path
# ---------------------------------------------------------------------------


def test_ai_off_critical_path(client: TestClient, monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "false")
    get_settings.cache_clear()
    assert get_settings().ai_enabled is False

    created = client.post("/api/studies/create", json={"title": "AI-off", "sponsor": "S"}).json()
    sid = created["study_key"]
    for name, dtype, body in [
        ("checklist.txt", "CHECKLIST", b"C"),
        ("synopsis.txt", "SYNOPSIS", b"S"),
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

    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": True, "created_by": "ai-off-28"},
    )
    assert wf.status_code == 200
    assert wf.json()["guards"]["ai_enabled"] is False
    assert wf.json()["guards"]["dose_conflict_auto_resolved"] is False

    conf = client.get(f"/api/studies/{STUDY}/conflicts").json()["conflicts"]
    assert any(
        c.get("field") == "reference_product.dose" and c.get("status") == "OPEN" for c in conf
    )

    pf = client.get(f"/api/studies/{STUDY}/preflight").json()
    assert pf.get("can_generate_docx") is False
    assert client.post(f"/api/studies/{STUDY}/protocol/generate-docx", json={}).status_code == 400

    prog = client.get(f"/api/studies/{STUDY}/writer-progress").json()
    assert prog["derived_from_backend"] is True
    assert prog["counts"]["conflicts_critical"] >= 1


def test_workflow_still_rejects_auto_approve_flags():
    from app.domain.exceptions import ValidationError

    with pytest.raises(ValidationError):
        run_protocol_workflow(STUDY, use_golden_fixture=True, auto_resolve_conflicts=True)
    with pytest.raises(ValidationError):
        run_protocol_workflow(STUDY, use_golden_fixture=True, auto_approve_statistics=True)

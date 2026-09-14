"""Workspace uploads must feed Analyze via StudyInputPackage bridge."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import Base, configure_engine, get_engine
from app.domain.decision_store import clear_decision_store
from app.domain.research_evidence_store import clear_research_evidence_store
from app.domain.sample_size_store import reset_sample_size_store
from app.domain.statistics_store import reset_statistics_store
from app.domain.study_input_store import clear_store as clear_study_input
from app.domain.study_workspace import find_study_package, reset_workspace_store
from app.main import create_app
import app.models  # noqa: F401

STUDY = "WS-BRIDGE-ANALYZE-01"


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


def test_analyze_uses_workspace_uploads_not_missing_package(client: TestClient, tmp_path):
    created = client.post(
        "/api/studies/create",
        json={"study_key": STUDY, "title": "Bridge study", "product": "Test"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["study_key"] == STUDY

    for dtype, name in [
        ("CHECKLIST", "checklist.txt"),
        ("SYNOPSIS", "synopsis.txt"),
        ("SMPC", "smpc.txt"),
    ]:
        p = tmp_path / name
        p.write_text(f"{dtype} content for {STUDY}\nProduct Test\n", encoding="utf-8")
        r = client.post(
            f"/api/studies/{STUDY}/documents/upload",
            files={"file": (name, p.read_bytes(), "text/plain")},
            data={"document_type": dtype},
        )
        assert r.status_code == 200, r.text

    docs = client.get(f"/api/studies/{STUDY}/documents").json()["documents"]
    assert len(docs) >= 3

    # Simulate cold memory: uploads exist on disk/DB, package store empty
    clear_study_input()
    assert find_study_package(STUDY) is None

    wf = client.post(
        f"/api/studies/{STUDY}/workflow/run",
        json={"use_golden_fixture": False, "created_by": "bridge-test"},
    )
    assert wf.status_code == 200, wf.text
    body = wf.json()
    assert "Нет загруженного пакета" not in str(body)
    assert body.get("study_mutated") is False
    steps = {s.get("step") for s in (body.get("steps") or [])}
    assert "validate_source_documents" in steps or "ingest_extract_normalize" in steps

    # after_mutation clears process cache — reload from DB
    from app.core.db import get_engine
    from sqlalchemy.orm import sessionmaker
    from app.domain.workspace_authority import ensure_db_authoritative

    Session = sessionmaker(bind=get_engine())
    db = Session()
    try:
        ensure_db_authoritative(db, STUDY)
        pkg = find_study_package(STUDY)
        assert pkg is not None
        assert pkg.study_id == STUDY
        assert len(pkg.documents) >= 1
    finally:
        db.close()


def test_find_package_does_not_leak_updcb_onto_real_study(client: TestClient):
    """UPDCB fixture in memory must not satisfy an unrelated real study."""
    from app.domain.study_input_pipeline import load_real_fixture_package
    from app.domain.study_input_store import put_package

    golden = load_real_fixture_package()
    put_package(golden)
    assert find_study_package("STUDY-REAL-NO-DOCS") is None

"""DRAFT DOCX gate: approvals are warnings; only hard CRITICAL checks block."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.db import Base, configure_engine, get_engine
from app.domain.decision_store import clear_decision_store
from app.domain.protocol_workflow import run_protocol_workflow
from app.domain.research_evidence_store import clear_research_evidence_store
from app.domain.sample_size_store import reset_sample_size_store
from app.domain.statistics_store import reset_statistics_store
from app.domain.study_input_store import clear_store as clear_study_input
from app.domain.study_workspace import build_preflight, reset_workspace_store
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


def test_primary_be_and_sample_size_are_warnings_for_draft_docx():
    run_protocol_workflow(STUDY, use_golden_fixture=True, prepare_protocol_draft=True)
    pf = build_preflight(STUDY)
    by_code = {c["code"]: c for c in pf["checks"]}
    assert by_code["PRIMARY_BE_APPROVED"]["severity"] == "WARNING"
    assert by_code["SAMPLE_SIZE_APPROVED"]["severity"] == "WARNING"
    assert by_code["NO_CRITICAL_CONFLICT"]["severity"] == "CRITICAL"
    # Golden fixture has open dose conflict — that alone may block DOCX (fail-closed)
    if not by_code["NO_CRITICAL_CONFLICT"]["ok"]:
        assert pf["can_generate_docx"] is False
        assert any(c["code"] == "NO_CRITICAL_CONFLICT" for c in pf["critical_blockers"])
    else:
        assert pf["can_generate_docx"] is True


def test_docx_not_blocked_solely_by_unapproved_statistics():
    run_protocol_workflow(STUDY, use_golden_fixture=True, prepare_protocol_draft=True)
    pf = build_preflight(STUDY)
    # Strip the effect of the golden dose conflict for this assertion
    hard = [c for c in pf["critical_blockers"] if c["code"] != "NO_CRITICAL_CONFLICT"]
    assert not any(c["code"] in {"PRIMARY_BE_APPROVED", "SAMPLE_SIZE_APPROVED"} for c in hard)
    # Approvals must not appear as CRITICAL blockers
    assert not any(
        c["code"] in {"PRIMARY_BE_APPROVED", "SAMPLE_SIZE_APPROVED"} and c["severity"] == "CRITICAL"
        for c in pf["checks"]
    )

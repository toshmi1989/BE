"""Phase 18 — Real-world beta validation harness tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.db import Base, configure_engine, get_engine
from app.domain.beta_observability import reset_beta_observability
from app.domain.beta_registry import case_summary, list_cases
from app.domain.beta_runner import evaluate_all, evaluate_case, writer_review_bundle
from app.domain.decision_store import clear_decision_store
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.protocol_workflow import run_protocol_workflow
from app.domain.research_evidence_store import clear_research_evidence_store
from app.domain.sample_size_store import reset_sample_size_store
from app.domain.statistics_store import reset_statistics_store
from app.domain.study_input_store import clear_store as clear_study_input
from app.domain.study_workspace import aggregate_conflicts, reset_workspace_store
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
    reset_beta_observability()
    yield
    reset_workspace_store()
    reset_sample_size_store()
    reset_statistics_store()
    clear_research_evidence_store()
    clear_decision_store()
    clear_study_input()
    reset_beta_observability()
    Base.metadata.drop_all(bind=engine)
    get_settings.cache_clear()


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


def test_version_023():
    assert Settings().app_version == "0.33.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.33.0"


def test_registry_has_twelve_cases_with_limitation():
    cases = list_cases()
    assert len(cases) >= 10
    summary = case_summary()
    assert summary["synthetic"] >= 1
    assert summary["real_available"] >= 1
    assert "SYNTHETIC" in summary["limitation"]


def test_categories_a_to_l_present():
    cats = {c["category"] for c in list_cases()}
    for letter in "ABCDEFGHIJKL":
        assert letter in cats


def test_evaluate_all_ai_off():
    assert get_settings().ai_enabled is False
    out = evaluate_all(include_synthetic=True)
    assert out["n"] >= 10
    assert out["population"]["real"] >= 1
    assert out["population"]["synthetic"] >= 1


def test_case_i_golden_conflict():
    r = evaluate_case("CASE-I-CONFLICTING-DOCS")
    assert r["origin"] == "REAL"
    assert r["golden_invariants"]["no_auto_resolution"] is True
    assert r["conflicts"]["auto_resolved"] is False
    assert r["conflicts"]["true_positive"] >= 1 or r["conflicts"]["dose_conflict_open"]
    assert r["extraction"]["counts"]
    assert r["evidence"]["excerpt_attached_rate"] >= 0
    assert r["writer_time"]["time_saving_pct"] is None
    assert r["missing_handling"]["forbidden_auto_na"] is True


def test_case_j_incomplete_package():
    r = evaluate_case("CASE-J-PARTIAL-SMPC")
    assert r["origin"] == "REAL_PARTIAL"
    assert r["availability"]["MISSING"] or r["missing_handling"]["observed_gaps"]


def test_synthetic_missing_cvintra():
    r = evaluate_case("CASE-F-MISSING-CVINTRA")
    assert r["origin"] == "SYNTHETIC"
    assert "cvintra" in (r["availability"]["MISSING"] or []) or "missing CVintra" in str(
        r["missing_handling"]["observed_gaps"]
    )
    assert r["sample_size"]["recommendation_is_not_approval"] is True


def test_golden_workflow_regression_after_decision(client: TestClient):
    wf = client.post(f"/api/studies/{STUDY}/workflow/run", json={"use_golden_fixture": True})
    assert wf.status_code == 200
    conf = client.get(f"/api/studies/{STUDY}/conflicts").json()["conflicts"]
    dose = [c for c in conf if c.get("field") == "reference_product.dose" and c.get("status") == "OPEN"]
    assert dose
    assert dose[0].get("auto_resolved") is False
    dec = client.post(
        f"/api/studies/{STUDY}/decisions/expert",
        json={
            "question": "reference_product.dose",
            "selected_option": "15 mg",
            "rationale": "beta expert",
            "status": "APPROVED",
            "decision_id": "ED-BETA-DOSE",
        },
    )
    assert dec.status_code == 200
    assert dec.json()["snapshot"]["version"] >= 2
    snaps = client.get(f"/api/studies/{STUDY}/snapshots").json()["snapshots"]
    assert len({s["version"] for s in snaps}) == len(snaps)


def test_writer_review_api(client: TestClient):
    evaluate_case("CASE-I-CONFLICTING-DOCS")
    r = client.get(f"/api/beta/studies/{STUDY}/writer-review")
    assert r.status_code == 200
    body = r.json()
    assert body["never_auto_na"] is True
    assert body["layout"]["left"] == "canonical"
    assert "Needs source" in body["missing_labels"] or "Not available" in body["missing_labels"]


def test_beta_api_cases(client: TestClient):
    r = client.get("/api/beta/cases")
    assert r.status_code == 200
    assert r.json()["summary"]["total"] >= 10
    ev = client.post("/api/beta/cases/CASE-A-2X2-FASTING/evaluate")
    assert ev.status_code == 200
    assert ev.json()["origin"] == "SYNTHETIC"


def test_ai_off_beta_and_workflow():
    assert get_settings().ai_enabled is False
    evaluate_case("CASE-I-CONFLICTING-DOCS")
    out = run_protocol_workflow(STUDY, use_golden_fixture=True)
    assert out["guards"]["ai_required"] is False
    assert out["study_mutated"] is False


def test_writer_review_bundle_direct():
    evaluate_case("CASE-L-STALE-LEGACY")
    bundle = writer_review_bundle("CASE-L-STALE-LEGACY")
    assert bundle["never_auto_na"] is True

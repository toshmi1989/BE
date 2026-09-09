"""Phase 25 — Handoff portability (0.33.0)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.domain.protocol_constants import PROTOCOL_GENERATOR_VERSION
from app.domain.real_package_registry import population_status
from app.domain.sample_classes import assert_not_counted_as_real
from app.main import create_app

REPO = Path(__file__).resolve().parents[2]


def setup_function() -> None:
    get_settings.cache_clear()


def test_version_0_30_0() -> None:
    assert Settings().app_version == "0.33.0"
    assert PROTOCOL_GENERATOR_VERSION == "0.33.0"


def test_env_example_and_handoff_docs_exist() -> None:
    assert (REPO / ".env.example").exists()
    assert (REPO / "docs" / "BETA_HOST_HANDOFF.md").exists()
    assert (REPO / "docs" / "ENVIRONMENT_INVENTORY.md").exists()
    assert (REPO / "docs" / "WRITER_BETA_PROTOCOL.md").exists()
    assert (REPO / "scripts" / "start_beta.sh").exists()
    assert (REPO / "scripts" / "start_beta.ps1").exists()
    assert (REPO / "scripts" / "beta_smoke_test.py").exists()
    assert (REPO / "scripts" / "collect_beta_diagnostics.py").exists()


def test_test_and_synthetic_not_counted_as_real() -> None:
    assert assert_not_counted_as_real("TEST")["test_or_synthetic"] is True
    assert assert_not_counted_as_real("SYNTHETIC")["test_or_synthetic"] is True
    assert assert_not_counted_as_real("REAL")["counts_as_real_full_or_partial"] is True
    st = population_status()
    assert st["synthetic_counted_as_real"] is False
    assert st["real_full_sanitized"] == 1


def test_api_version_no_secrets() -> None:
    client = TestClient(create_app())
    r = client.get("/api/version")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "0.33.0"
    assert body["secrets_included"] is False
    assert "auth_secret" not in body
    assert "password" not in body


def test_health_still_ok() -> None:
    client = TestClient(create_app())
    assert client.get("/api/health").json()["version"] == "0.33.0"

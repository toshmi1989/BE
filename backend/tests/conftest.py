import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import Base, configure_engine, get_engine
from app.main import create_app
import app.models  # noqa: F401 — register metadata


@pytest.fixture(autouse=True)
def _reset_ai_runtime():
    """AI overrides are process-global — never let one test enable AI for the next."""
    from app.domain.ai_runtime_settings import reset_runtime

    reset_runtime()
    yield
    reset_runtime()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    from app.domain.workspace_authority import invalidate_study_cache

    # The API gets a fresh DB per test; the process-local working set must match it.
    invalidate_study_cache("*")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("AI_ENABLED", "false")
    get_settings.cache_clear()
    configure_engine("sqlite+pysqlite:///:memory:")
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    app = create_app()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
    get_settings.cache_clear()

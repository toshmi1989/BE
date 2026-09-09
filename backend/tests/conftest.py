import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import Base, configure_engine, get_engine
from app.main import create_app
import app.models  # noqa: F401 — register metadata


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
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

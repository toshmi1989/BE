from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.schemas.health import HealthResponse, ReadyResponse, VersionResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        ai_enabled=settings.ai_enabled,
        external_ai_enabled=settings.external_ai_enabled,
    )


@router.get("/version", response_model=VersionResponse)
def version_info(settings: Settings = Depends(get_settings)) -> VersionResponse:
    """Safe build information — no secrets."""
    import subprocess
    from pathlib import Path

    git_rev = None
    try:
        root = Path(__file__).resolve().parents[3]
        git_rev = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(root),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        git_rev = None

    migration_rev = None
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        migration_rev = script.get_current_head()
    except Exception:
        migration_rev = None

    return VersionResponse(
        version=settings.app_version,
        git_revision=git_rev,
        migration_revision=migration_rev,
        auth_required=bool(settings.auth_required),
        ai_enabled=settings.ai_enabled,
        secrets_included=False,
    )


@router.get("/ready", response_model=ReadyResponse)
def ready(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> ReadyResponse:
    # In-memory SQLite (default for tests / no Postgres) still counts as ready.
    if settings.database_url.startswith("sqlite"):
        try:
            db.execute(text("SELECT 1"))
            return ReadyResponse(status="ready", database="ok")
        except Exception:
            return ReadyResponse(status="not_ready", database="unavailable")

    try:
        db.execute(text("SELECT 1"))
        return ReadyResponse(status="ready", database="ok")
    except Exception:
        return ReadyResponse(status="not_ready", database="unavailable")

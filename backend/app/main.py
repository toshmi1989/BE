from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import Settings, get_settings
from app.domain.exceptions import DomainError


def _static_dir(settings: Settings) -> Path:
    if settings.static_dir:
        return Path(settings.static_dir)
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / "static",
        here.parents[2] / "frontend" / "dist",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def _mount_spa(app: FastAPI, settings: Settings) -> None:
    frontend = _static_dir(settings)
    index = frontend / "index.html"
    if not index.is_file():
        return

    base = settings.normalized_base_path
    assets = frontend / "assets"
    if assets.is_dir():
        app.mount(
            f"{base}/assets" if base else "/assets",
            StaticFiles(directory=assets),
            name="assets",
        )

    @app.get(base or "/")
    @app.get(f"{base}/" if base else "/index.html")
    def spa_index() -> FileResponse:
        return FileResponse(index)

    if base:

        @app.get(f"{base}/{{full_path:path}}")
        def spa_asset(full_path: str) -> FileResponse:
            if full_path.startswith("api/") or full_path == "api":
                raise HTTPException(status_code=404, detail="Not Found")
            candidate = frontend / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(index)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Deterministic BE protocol platform. "
            "AI is optional; core path works with AI disabled."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.mounted_api_prefix)

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        status_code = {
            "NOT_FOUND": 404,
            "CONFLICT": 409,
            "PROVENANCE_GUARD": 409,
            "VALIDATION_ERROR": 422,
        }.get(exc.code, 400)
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "field": exc.field,
                    "severity": "ERROR",
                    "details": exc.details,
                }
            },
        )

    _mount_spa(app, settings)
    return app


app = create_app()

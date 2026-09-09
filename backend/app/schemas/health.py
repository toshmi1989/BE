from pydantic import BaseModel, Field

from app.domain.constants import RULES_CATALOG_VERSION, SCHEMA_VERSION


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str
    schema_version: str = SCHEMA_VERSION
    rules_catalog_version: str = RULES_CATALOG_VERSION
    ai_enabled: bool = False
    external_ai_enabled: bool = False


class ReadyResponse(BaseModel):
    status: str
    database: str = Field(description="ok | unavailable | skipped")


class VersionResponse(BaseModel):
    version: str
    git_revision: str | None = None
    migration_revision: str | None = None
    auth_required: bool = False
    ai_enabled: bool = False
    secrets_included: bool = False

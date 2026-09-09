from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "BE Protocol Platform"
    app_version: str = "0.33.0"
    api_prefix: str = "/api"
    base_path: str = ""
    app_port: int = 8000
    static_dir: str = ""

    database_url: str = "sqlite+pysqlite:///:memory:"
    cors_origins: str = "http://localhost:5173"

    ai_enabled: bool = False
    external_ai_enabled: bool = False
    ai_provider: str = "openai"
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_timeout: float = 60.0
    ai_max_tokens: int = 2048
    ai_temperature: float = 0.0
    openai_api_key: str = ""  # env OPENAI_API_KEY; prefer UI runtime settings for local use

    document_storage_root: str = "storage/documents"
    max_upload_bytes: int = 26214400

    research_web_enabled: bool = True
    research_http_timeout: float = 20.0
    research_http_max_retries: int = 2
    research_http_backoff_s: float = 0.5
    research_max_results: int = 10
    research_user_agent: str = "BE-Protocol-Platform-Research/0.30 (+local; assistive-only)"

    auth_required: bool = False
    auth_secret: str = "dev-only-change-me-phase17"
    auth_token_ttl_seconds: int = 86400

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def normalized_base_path(self) -> str:
        raw = (self.base_path or "").strip()
        if not raw or raw == "/":
            return ""
        return "/" + raw.strip("/")

    @property
    def mounted_api_prefix(self) -> str:
        prefix = self.api_prefix if self.api_prefix.startswith("/") else f"/{self.api_prefix}"
        base = self.normalized_base_path
        return f"{base}{prefix}" if base else prefix


@lru_cache
def get_settings() -> Settings:
    return Settings()

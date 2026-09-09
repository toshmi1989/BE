"""Process-local AI runtime overrides (UI settings). Never logs the API key."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class AIRuntimeSettings:
    enabled: bool | None = None  # None = fall back to env Settings.ai_enabled
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    updated_at: str | None = None


_lock = Lock()
_runtime = AIRuntimeSettings()


def get_runtime() -> AIRuntimeSettings:
    with _lock:
        return AIRuntimeSettings(
            enabled=_runtime.enabled,
            provider=_runtime.provider,
            model=_runtime.model,
            base_url=_runtime.base_url,
            api_key=_runtime.api_key,
            updated_at=_runtime.updated_at,
        )


def update_runtime(
    *,
    enabled: bool | None = None,
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    clear_api_key: bool = False,
) -> AIRuntimeSettings:
    from datetime import datetime, timezone

    with _lock:
        if enabled is not None:
            _runtime.enabled = bool(enabled)
        if provider is not None and str(provider).strip():
            _runtime.provider = str(provider).strip().lower()
        if model is not None and str(model).strip():
            _runtime.model = str(model).strip()
        if base_url is not None and str(base_url).strip():
            _runtime.base_url = str(base_url).strip().rstrip("/")
        if clear_api_key:
            _runtime.api_key = None
        elif api_key is not None:
            key = str(api_key).strip()
            if key:
                _runtime.api_key = key
        _runtime.updated_at = datetime.now(timezone.utc).isoformat()
        return AIRuntimeSettings(
            enabled=_runtime.enabled,
            provider=_runtime.provider,
            model=_runtime.model,
            base_url=_runtime.base_url,
            api_key=_runtime.api_key,
            updated_at=_runtime.updated_at,
        )


def reset_runtime() -> None:
    """Drop process-local overrides so env Settings decide again."""
    with _lock:
        _runtime.enabled = None
        _runtime.provider = None
        _runtime.model = None
        _runtime.base_url = None
        _runtime.api_key = None
        _runtime.updated_at = None


def mask_api_key(key: str | None) -> str | None:
    if not key:
        return None
    k = key.strip()
    if len(k) <= 8:
        return "••••" + k[-2:]
    return k[:3] + "…" + k[-4:]


def public_settings_view() -> dict[str, Any]:
    rt = get_runtime()
    from app.core.config import get_settings

    s = get_settings()
    effective_enabled = s.ai_enabled if rt.enabled is None else bool(rt.enabled)
    effective_provider = (rt.provider or s.ai_provider or "openai").lower()
    effective_model = rt.model or s.ai_model or "gpt-4o-mini"
    effective_base = rt.base_url or s.ai_base_url or "https://api.openai.com/v1"
    key = rt.api_key or (s.openai_api_key or None) or None
    return {
        "enabled": effective_enabled,
        "provider": effective_provider,
        "model": effective_model,
        "base_url": effective_base,
        "api_key_configured": bool(key),
        "api_key_masked": mask_api_key(key),
        "runtime_override": rt.enabled is not None or bool(rt.api_key) or bool(rt.provider),
        "updated_at": rt.updated_at,
        "assistive_only": True,
        "cannot_approve_decisions": True,
        "default_cloud_model": "gpt-4o-mini",
    }

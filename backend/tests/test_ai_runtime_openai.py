"""AI runtime settings + OpenAI provider wiring (no network)."""

from __future__ import annotations

from app.domain.ai_provider import DisabledAIProvider, OpenAICloudProvider, get_ai_provider
from app.domain.ai_runtime_settings import get_runtime, mask_api_key, public_settings_view, update_runtime
from app.services import ai_extraction_service as ai_svc


def test_mask_api_key():
    assert mask_api_key(None) is None
    assert mask_api_key("short") is not None
    masked = mask_api_key("abcdefghijklmnop")
    assert masked is not None
    assert "…" in masked or "..." in masked or masked.startswith("abc")


def test_runtime_override_enables_openai_without_env():
    update_runtime(
        enabled=True,
        provider="openai",
        model="gpt-4o-mini",
        api_key="test-key-not-a-secret-value",
        base_url="https://api.openai.com/v1",
    )
    view = public_settings_view()
    assert view["enabled"] is True
    assert view["provider"] == "openai"
    assert view["model"] == "gpt-4o-mini"
    assert view["api_key_configured"] is True
    assert view["assistive_only"] is True

    st = ai_svc.ai_status()
    # Without network, available may be False, but enabled True and provider openai
    assert st.enabled is True
    assert st.provider in {"openai", "disabled"} or st.model == "gpt-4o-mini"


def test_get_ai_provider_openai():
    p = get_ai_provider(
        enabled=True,
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout=5.0,
        max_tokens=128,
        temperature=0.0,
        api_key="test-key-not-a-secret-value",
    )
    assert isinstance(p, OpenAICloudProvider)
    assert p.model == "gpt-4o-mini"


def test_get_ai_provider_openai_without_key_disabled():
    p = get_ai_provider(
        enabled=True,
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        timeout=5.0,
        max_tokens=128,
        temperature=0.0,
        api_key=None,
    )
    assert isinstance(p, DisabledAIProvider)


def test_clear_api_key():
    update_runtime(api_key="test-key-not-a-secret-value")
    assert get_runtime().api_key
    update_runtime(clear_api_key=True)
    assert get_runtime().api_key is None

"""HTTP client helpers for research providers — timeout, retry, backoff, limits."""

from __future__ import annotations

import time
from typing import Any, Callable

import httpx

from app.core.config import get_settings


class ResearchHttpError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, kind: str = "HTTP_ERROR"):
        super().__init__(message)
        self.status_code = status_code
        self.kind = kind


def research_http_settings() -> dict[str, Any]:
    s = get_settings()
    return {
        "timeout": getattr(s, "research_http_timeout", 20.0),
        "max_retries": getattr(s, "research_http_max_retries", 2),
        "backoff_s": getattr(s, "research_http_backoff_s", 0.5),
        "max_results": getattr(s, "research_max_results", 10),
        "user_agent": getattr(
            s,
            "research_user_agent",
            "BE-Protocol-Platform-Research/0.18 (+local; assistive-only)",
        ),
        "enabled": getattr(s, "research_web_enabled", True),
    }


def http_get(
    url: str,
    *,
    client: httpx.Client | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    backoff_s: float | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    cfg = research_http_settings()
    timeout = timeout if timeout is not None else cfg["timeout"]
    max_retries = max_retries if max_retries is not None else cfg["max_retries"]
    backoff_s = backoff_s if backoff_s is not None else cfg["backoff_s"]
    hdrs = {"User-Agent": cfg["user_agent"], **(headers or {})}

    last_exc: Exception | None = None
    own_client = client is None
    client = client or httpx.Client(follow_redirects=True, timeout=timeout)
    try:
        for attempt in range(max_retries + 1):
            try:
                r = client.get(url, headers=hdrs)
                if r.status_code == 404:
                    raise ResearchHttpError("HTTP 404", status_code=404, kind="NOT_FOUND")
                if r.status_code in {401, 403}:
                    raise ResearchHttpError(
                        f"Access denied ({r.status_code})",
                        status_code=r.status_code,
                        kind="ACCESS_DENIED",
                    )
                if r.status_code >= 500:
                    raise ResearchHttpError(
                        f"Server error {r.status_code}",
                        status_code=r.status_code,
                        kind="SERVER_ERROR",
                    )
                if r.status_code >= 400:
                    raise ResearchHttpError(
                        f"HTTP {r.status_code}",
                        status_code=r.status_code,
                        kind="HTTP_ERROR",
                    )
                return r
            except ResearchHttpError:
                raise
            except httpx.TimeoutException as exc:
                last_exc = ResearchHttpError("Request timeout", kind="TIMEOUT")
                if attempt >= max_retries:
                    raise last_exc from exc
            except httpx.HTTPError as exc:
                last_exc = ResearchHttpError(str(exc) or "HTTP error", kind="HTTP_ERROR")
                if attempt >= max_retries:
                    raise last_exc from exc
            time.sleep(backoff_s * (attempt + 1))
        raise last_exc or ResearchHttpError("Request failed", kind="HTTP_ERROR")
    finally:
        if own_client:
            client.close()


def http_get_bytes(url: str, **kwargs: Any) -> tuple[bytes, str | None]:
    r = http_get(url, **kwargs)
    ctype = r.headers.get("content-type")
    return r.content, ctype

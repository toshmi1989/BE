"""Phase 17 — Password hashing (stdlib scrypt) + signed session tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from uuid import UUID

from app.core.config import get_settings

_TOKEN_PREFIX = "be1"


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.urlsafe_b64encode(salt + digest).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algo, payload = password_hash.split("$", 1)
        if algo != "scrypt":
            return False
        raw = base64.urlsafe_b64decode(payload.encode("ascii"))
        salt, expected = raw[:16], raw[16:]
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(digest, expected)
    except Exception:  # noqa: BLE001
        return False


def _secret() -> bytes:
    settings = get_settings()
    return str(getattr(settings, "auth_secret", None) or "dev-only-change-me-phase17").encode("utf-8")


def create_access_token(
    *,
    user_id: UUID | str,
    email: str,
    organization_id: UUID | str | None,
    role: str,
    ttl_seconds: int | None = None,
) -> str:
    settings = get_settings()
    ttl = ttl_seconds or int(getattr(settings, "auth_token_ttl_seconds", 86400))
    payload = {
        "sub": str(user_id),
        "email": email,
        "org": str(organization_id) if organization_id else None,
        "role": role,
        "exp": int(time.time()) + ttl,
        "iat": int(time.time()),
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{_TOKEN_PREFIX}.{body}.{sig}"


def decode_access_token(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != _TOKEN_PREFIX:
        raise ValueError("Invalid token")
    body, sig = parts[1], parts[2]
    expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValueError("Invalid token signature")
    pad = "=" * (-len(body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(body + pad))
    if int(payload.get("exp") or 0) < int(time.time()):
        raise ValueError("Token expired")
    return payload

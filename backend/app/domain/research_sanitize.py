"""Sanitize untrusted external research content — Phase 15.3."""

from __future__ import annotations

import html
import re
from urllib.parse import urlparse

from app.domain.document_ingest import FORBIDDEN_SUFFIXES, safe_filename


_SCRIPT_RE = re.compile(r"<\s*script[^>]*>.*?<\s*/\s*script\s*>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    t = _SCRIPT_RE.sub(" ", text)
    t = _TAG_RE.sub(" ", t)
    t = html.unescape(t)
    t = _CTRL_RE.sub(" ", t)
    return " ".join(t.split())


def sanitize_title(title: str | None, *, max_len: int = 500) -> str:
    t = strip_html(title)[:max_len].strip()
    return t or "Untitled"


def sanitize_snippet(snippet: str | None, *, max_len: int = 2000) -> str:
    return strip_html(snippet)[:max_len].strip()


def sanitize_url(url: str | None) -> str | None:
    """Allow only http(s) URLs. Reject file://, javascript:, data:, local paths."""
    if not url or not str(url).strip():
        return None
    u = str(url).strip()
    if u.startswith(("javascript:", "data:", "file:", "vbscript:")):
        raise ValueError("Forbidden URL scheme")
    # Reject Windows/Unix local paths
    if re.match(r"^[a-zA-Z]:[\\/]", u) or u.startswith(("/", "\\\\", "./", "../")):
        if not u.startswith(("http://", "https://")):
            raise ValueError("Local paths are not allowed as research URLs")
    parsed = urlparse(u)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme or 'none'}")
    if not parsed.netloc:
        raise ValueError("URL missing host")
    # Normalize — drop fragments that may carry scripts
    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        clean += f"?{parsed.query}"
    return clean


def sanitize_filename_meta(name: str | None) -> str:
    safe = safe_filename(name or "download.bin")
    suffix = ("." + safe.rsplit(".", 1)[-1].lower()) if "." in safe else ""
    if suffix in FORBIDDEN_SUFFIXES:
        raise ValueError("Executable content not allowed")
    return safe


def sanitize_metadata(meta: dict | None) -> dict:
    """Shallow sanitize string values; drop executable-looking keys/values."""
    out: dict = {}
    for k, v in (meta or {}).items():
        key = strip_html(str(k))[:80]
        if key.lower() in {"onclick", "onload", "script"}:
            continue
        if isinstance(v, str):
            out[key] = strip_html(v)[:2000]
        elif isinstance(v, (int, float, bool)) or v is None:
            out[key] = v
        elif isinstance(v, dict):
            out[key] = sanitize_metadata(v)
        elif isinstance(v, list):
            out[key] = [strip_html(str(x))[:500] if isinstance(x, str) else x for x in v[:50]]
    return out

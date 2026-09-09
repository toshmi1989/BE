"""Fetch & snapshot external sources — HTML / PDF / DOCX / text — Phase 15.3."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.domain.document_ingest import FORBIDDEN_SUFFIXES, MAX_UPLOAD_BYTES
from app.domain.research_http import ResearchHttpError, http_get_bytes
from app.domain.research_sanitize import sanitize_snippet, sanitize_url, strip_html
from app.domain.research_search_result import SourceSnapshot
from app.domain.study_input_binary_ingest import ingest_binary_bytes


SUPPORTED_FETCH_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/html",
    "text/plain",
    "application/xhtml+xml",
}


class UnsupportedContentTypeError(ResearchHttpError):
    def __init__(self, mime: str | None):
        super().__init__(f"Unsupported content type: {mime}", kind="UNSUPPORTED_CONTENT")


def _guess_filename(url: str, mime: str | None) -> str:
    path = url.rstrip("/").split("/")[-1] or "download"
    if "." not in path:
        if mime and "pdf" in mime:
            path += ".pdf"
        elif mime and "wordprocessingml" in (mime or ""):
            path += ".docx"
        elif mime and "html" in (mime or ""):
            path += ".html"
        else:
            path += ".bin"
    return path


def fetch_and_snapshot(
    locator: str,
    *,
    client=None,
    allow_local_mock_text: str | None = None,
) -> tuple[SourceSnapshot, str]:
    """Fetch URL content and build snapshot + extracted text.

    Returns (snapshot, extracted_text). Never mutates Study.
    For tests, pass allow_local_mock_text to skip network when locator is mock://
    """
    if locator.startswith("mock://") or locator.startswith("local://"):
        text = allow_local_mock_text or ""
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        snap = SourceSnapshot(
            locator=locator,
            content_hash=h[:32],
            mime_type="text/plain",
            text_excerpt=text[:2000],
            snapshot_complete=True,
            document_metadata={"mode": "mock_or_local"},
        )
        return snap, text

    try:
        url = sanitize_url(locator)
    except ValueError as exc:
        raise ResearchHttpError(str(exc), kind="INVALID_URL") from exc
    if not url:
        raise ResearchHttpError("Empty URL", kind="INVALID_URL")

    try:
        content, ctype = http_get_bytes(url, client=client)
    except ResearchHttpError:
        raise

    mime = (ctype or "application/octet-stream").split(";")[0].strip().lower()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ResearchHttpError("Fetched content exceeds size limit", kind="TOO_LARGE")

    filename = _guess_filename(url, mime)
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if suffix in FORBIDDEN_SUFFIXES:
        raise ResearchHttpError("Executable content not allowed", kind="FORBIDDEN_CONTENT")

    # HTML / plain text
    if "html" in mime or mime == "text/plain" or suffix in {".html", ".htm", ".txt"}:
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            raise ResearchHttpError(f"HTML/text parse failure: {exc}", kind="PARSE_FAILURE") from exc
        if "html" in mime or suffix in {".html", ".htm"}:
            text = strip_html(text)
        h = hashlib.sha256(content).hexdigest()
        snap = SourceSnapshot(
            locator=url,
            content_hash=h,
            mime_type=mime,
            text_excerpt=sanitize_snippet(text[:2000]),
            document_metadata={"filename": filename},
            snapshot_complete=True,
        )
        return snap, text

    # PDF / DOCX via Phase 14.1 ingest
    if "pdf" in mime or suffix == ".pdf" or "wordprocessingml" in mime or suffix == ".docx":
        try:
            result = ingest_binary_bytes(content, filename=filename, mime_type=mime)
        except Exception as exc:  # noqa: BLE001
            kind = "PDF_PARSE_FAILURE" if "pdf" in mime or suffix == ".pdf" else "DOCX_PARSE_FAILURE"
            raise ResearchHttpError(f"Document parse failure: {exc}", kind=kind) from exc
        snap = SourceSnapshot(
            locator=url,
            content_hash=result.content_hash,
            source_version_id=result.source_version_id,
            mime_type=result.mime_type or mime,
            text_excerpt=sanitize_snippet((result.extracted_text or "")[:2000]),
            page_count=result.page_count,
            paragraph_count=result.paragraph_count,
            table_count=result.table_count,
            document_metadata={
                "filename": filename,
                "extraction_status": result.extraction_status,
                "pages": result.pages[:5] if result.pages else [],
                "paragraphs_sample": (result.paragraphs or [])[:3],
                "tables_sample": (result.tables or [])[:2],
                "warnings": result.warnings,
            },
            snapshot_complete=result.extraction_status in {"SUCCESS", "PARTIAL"},
            snapshot_limitations=[]
            if result.extraction_status == "SUCCESS"
            else [f"extraction_status={result.extraction_status}"],
        )
        return snap, result.extracted_text or ""

    raise UnsupportedContentTypeError(mime)


def extract_claims_hint_from_text(text: str) -> dict[str, Any]:
    """Lightweight observability — full extraction uses research_extract."""
    flags = {
        "mentions_half_life": bool(re.search(r"half[- ]?life|t\s*1\s*/\s*2|t½", text, re.I)),
        "mentions_tmax": bool(re.search(r"\bTmax\b", text, re.I)),
        "mentions_cv": bool(re.search(r"\bCV\b|variability|CVintra", text, re.I)),
    }
    return flags

"""Binary document ingestion for Study Input Package — Phase 14.1.

First-class DOCX/PDF path. Never prefers text dumps.
Never mutates Study. FAILED must not become SUCCESS silently.
"""

from __future__ import annotations

import hashlib
import mimetypes
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.document_ingest import (
    MAX_UPLOAD_BYTES,
    FORBIDDEN_SUFFIXES,
    safe_filename,
)
from app.domain.exceptions import ValidationError


EXTRACTION_STATUSES = ("SUCCESS", "PARTIAL", "FAILED")
LOCATION_LEVELS = ("EXACT", "STRUCTURAL", "SECTION", "DOCUMENT_ONLY")


@dataclass
class DocxParagraph:
    index: int
    text: str
    style: str | None = None


@dataclass
class DocxTableCell:
    row: int
    col: int
    text: str


@dataclass
class DocxTable:
    index: int
    rows: list[list[str]] = field(default_factory=list)
    cells: list[DocxTableCell] = field(default_factory=list)


@dataclass
class PdfPage:
    page_number: int
    text: str
    heading_hint: str | None = None


@dataclass
class DocumentIngestionResult:
    source_id: str
    source_version_id: str
    filename: str
    mime_type: str | None
    content_hash: str
    file_size: int
    document_type: str | None
    extraction_status: str
    extracted_text: str
    page_count: int | None = None
    paragraph_count: int | None = None
    table_count: int | None = None
    warnings: list[str] = field(default_factory=list)
    paragraphs: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    pages: list[dict[str, Any]] = field(default_factory=list)
    duration_ms: float | None = None
    extraction_method: str = "DETERMINISTIC_BINARY"
    study_mutated: bool = False

    def __post_init__(self) -> None:
        if self.extraction_status not in EXTRACTION_STATUSES:
            raise ValueError(f"Invalid extraction_status: {self.extraction_status}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def observability(self) -> dict[str, Any]:
        return {
            "file": self.filename,
            "hash": self.content_hash,
            "document_type": self.document_type,
            "extraction_method": self.extraction_method,
            "status": self.extraction_status,
            "warnings": list(self.warnings),
            "file_size": self.file_size,
            "page_count": self.page_count,
            "paragraph_count": self.paragraph_count,
            "table_count": self.table_count,
            "duration_ms": self.duration_ms,
            "text_length": len(self.extracted_text or ""),
            "study_mutated": False,
        }


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_binary_upload(*, filename: str, mime_type: str | None, content: bytes) -> str:
    """Hardening wrapper — path traversal, size, MIME, magic bytes."""
    raw_name = filename.replace("\\", "/")
    if ".." in raw_name or raw_name.startswith("/") or (len(raw_name) > 1 and raw_name[1:3] == ":/"):
        # Reject traversal / absolute paths before basename sanitization
        if Path(filename).name != Path(filename).as_posix().split("/")[-1] or ".." in Path(filename).as_posix():
            raise ValidationError("Path traversal not allowed", field="filename")
    if ".." in Path(filename).as_posix():
        raise ValidationError("Path traversal not allowed", field="filename")
    safe = safe_filename(filename)
    suffix = Path(safe).suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES:
        raise ValidationError("Executable content not allowed", field="filename")
    if not content:
        raise ValidationError("Empty file", field="file")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValidationError(f"File exceeds {MAX_UPLOAD_BYTES} bytes", field="file")
    mime = (mime_type or mimetypes.guess_type(safe)[0] or "application/octet-stream").split(";")[0].strip().lower()
    if suffix not in {".pdf", ".docx", ".txt"} and mime not in {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "application/octet-stream",
    }:
        raise ValidationError(f"Unsupported MIME type: {mime}", field="mime_type")
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        raise ValidationError("File does not look like a PDF", field="file")
    if suffix == ".docx" and content[:2] != b"PK":
        raise ValidationError("File does not look like a DOCX (zip)", field="file")
    return safe


def _flatten_docx_text(paragraphs: list[DocxParagraph], tables: list[DocxTable]) -> str:
    lines: list[str] = []
    for p in paragraphs:
        if p.text.strip():
            lines.append(p.text.strip())
    for t in tables:
        for row in t.rows:
            uniq: list[str] = []
            for c in row:
                cell = (c or "").strip().replace("\n", " ")
                if not uniq or cell != uniq[-1]:
                    uniq.append(cell)
            line = " | ".join(uniq)
            if line.strip(" |"):
                lines.append(line)
    return "\n".join(lines)


def ingest_docx_bytes(
    content: bytes,
    *,
    filename: str,
    source_id: str | None = None,
    source_version_id: str | None = None,
    document_type: str | None = None,
) -> DocumentIngestionResult:
    t0 = time.perf_counter()
    warnings: list[str] = []
    digest = sha256_bytes(content)
    safe = validate_binary_upload(filename=filename, mime_type=None, content=content)
    sid = source_id or f"SRC-BIN-{uuid4().hex[:8]}"
    svid = source_version_id or f"SV-{digest[:12]}"

    try:
        from io import BytesIO

        from docx import Document

        doc = Document(BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        return DocumentIngestionResult(
            source_id=sid,
            source_version_id=svid,
            filename=safe,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            content_hash=digest,
            file_size=len(content),
            document_type=document_type,
            extraction_status="FAILED",
            extracted_text="",
            warnings=[f"DOCX open failed: {exc}"],
            duration_ms=(time.perf_counter() - t0) * 1000,
        )

    paragraphs: list[DocxParagraph] = []
    for i, para in enumerate(doc.paragraphs):
        style = None
        try:
            style = para.style.name if para.style is not None else None
        except Exception:  # noqa: BLE001
            style = None
        paragraphs.append(DocxParagraph(index=i, text=para.text or "", style=style))

    tables: list[DocxTable] = []
    for ti, table in enumerate(doc.tables):
        rows: list[list[str]] = []
        cells: list[DocxTableCell] = []
        for ri, row in enumerate(table.rows):
            row_cells: list[str] = []
            for ci, cell in enumerate(row.cells):
                txt = (cell.text or "").strip()
                row_cells.append(txt)
                cells.append(DocxTableCell(row=ri, col=ci, text=txt))
            rows.append(row_cells)
        tables.append(DocxTable(index=ti, rows=rows, cells=cells))

    text = _flatten_docx_text(paragraphs, tables)
    status = "SUCCESS"
    if not text.strip():
        status = "FAILED"
        warnings.append("DOCX produced empty text")
    elif not tables and sum(1 for p in paragraphs if p.text.strip()) < 2:
        status = "PARTIAL"
        warnings.append("Sparse DOCX content")

    return DocumentIngestionResult(
        source_id=sid,
        source_version_id=svid,
        filename=safe,
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        content_hash=digest,
        file_size=len(content),
        document_type=document_type,
        extraction_status=status,
        extracted_text=text,
        page_count=None,
        paragraph_count=len(paragraphs),
        table_count=len(tables),
        warnings=warnings,
        paragraphs=[{"index": p.index, "text": p.text, "style": p.style} for p in paragraphs],
        tables=[
            {
                "index": t.index,
                "row_count": len(t.rows),
                "rows": t.rows,
                "cells": [{"row": c.row, "col": c.col, "text": c.text} for c in t.cells],
            }
            for t in tables
        ],
        duration_ms=(time.perf_counter() - t0) * 1000,
    )


def ingest_pdf_bytes(
    content: bytes,
    *,
    filename: str,
    source_id: str | None = None,
    source_version_id: str | None = None,
    document_type: str | None = None,
) -> DocumentIngestionResult:
    t0 = time.perf_counter()
    warnings: list[str] = []
    digest = sha256_bytes(content)
    safe = validate_binary_upload(filename=filename, mime_type="application/pdf", content=content)
    sid = source_id or f"SRC-BIN-{uuid4().hex[:8]}"
    svid = source_version_id or f"SV-{digest[:12]}"

    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        return DocumentIngestionResult(
            source_id=sid,
            source_version_id=svid,
            filename=safe,
            mime_type="application/pdf",
            content_hash=digest,
            file_size=len(content),
            document_type=document_type,
            extraction_status="FAILED",
            extracted_text="",
            warnings=[f"PDF open failed: {exc}"],
            duration_ms=(time.perf_counter() - t0) * 1000,
        )

    pages: list[PdfPage] = []
    parts: list[str] = []
    empty_pages = 0
    for i, page in enumerate(reader.pages, start=1):
        try:
            t = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            t = ""
            warnings.append(f"page {i} extract error: {exc}")
        if not t.strip():
            empty_pages += 1
        heading = None
        for line in t.splitlines():
            if line.strip():
                heading = line.strip()[:120]
                break
        pages.append(PdfPage(page_number=i, text=t, heading_hint=heading))
        parts.append(t)

    text = "\n".join(parts)
    status = "SUCCESS"
    if not text.strip():
        status = "FAILED"
        warnings.append("PDF produced empty text")
    elif empty_pages > 0 and empty_pages < len(pages):
        status = "PARTIAL"
        warnings.append(f"{empty_pages} empty pages")

    return DocumentIngestionResult(
        source_id=sid,
        source_version_id=svid,
        filename=safe,
        mime_type="application/pdf",
        content_hash=digest,
        file_size=len(content),
        document_type=document_type,
        extraction_status=status,
        extracted_text=text,
        page_count=len(pages),
        paragraph_count=None,
        table_count=None,
        warnings=warnings,
        pages=[
            {"page_number": p.page_number, "text": p.text, "heading_hint": p.heading_hint}
            for p in pages
        ],
        duration_ms=(time.perf_counter() - t0) * 1000,
    )


def ingest_binary_file(
    path: Path,
    *,
    source_id: str | None = None,
    source_version_id: str | None = None,
    document_type: str | None = None,
    filename: str | None = None,
) -> DocumentIngestionResult:
    path = Path(path)
    content = path.read_bytes()
    name = filename or path.name
    return ingest_binary_bytes(
        content,
        filename=name,
        source_id=source_id,
        source_version_id=source_version_id,
        document_type=document_type,
    )


def ingest_binary_bytes(
    content: bytes,
    *,
    filename: str,
    mime_type: str | None = None,
    source_id: str | None = None,
    source_version_id: str | None = None,
    document_type: str | None = None,
) -> DocumentIngestionResult:
    """Ingest PDF/DOCX/TXT bytes — reused by Phase 15.3 source fetch."""
    safe = validate_binary_upload(filename=filename, mime_type=mime_type, content=content)
    suffix = Path(safe).suffix.lower()
    mime = (mime_type or "").lower()
    if suffix == ".docx" or "wordprocessingml" in mime:
        return ingest_docx_bytes(
            content,
            filename=safe,
            source_id=source_id,
            source_version_id=source_version_id,
            document_type=document_type,
        )
    if suffix == ".pdf" or "pdf" in mime:
        return ingest_pdf_bytes(
            content,
            filename=safe,
            source_id=source_id,
            source_version_id=source_version_id,
            document_type=document_type,
        )
    if suffix == ".txt" or mime.startswith("text/"):
        digest = sha256_bytes(content)
        text = content.decode("utf-8", errors="replace")
        return DocumentIngestionResult(
            source_id=source_id or f"SRC-BIN-{uuid4().hex[:8]}",
            source_version_id=source_version_id or f"SV-{digest[:12]}",
            filename=safe,
            mime_type="text/plain",
            content_hash=digest,
            file_size=len(content),
            document_type=document_type,
            extraction_status="SUCCESS",
            extracted_text=text,
        )
    raise ValidationError(f"Unsupported binary type for ingest: {suffix or mime}", field="mime_type")


def find_table_location(tables: list[dict[str, Any]], needle: str) -> str | None:
    """Return location string table=N|row=M|col=C for first cell containing needle."""
    n = (needle or "").lower()
    if not n:
        return None
    for t in tables:
        ti = int(t.get("index", 0))
        for cell in t.get("cells") or []:
            if n in str(cell.get("text") or "").lower():
                return f"table={ti}|row={cell.get('row')}|col={cell.get('col')}"
    return None


def find_pdf_page_location(pages: list[dict[str, Any]], needle: str) -> str | None:
    n = (needle or "").lower()
    for p in pages:
        if n in (p.get("text") or "").lower():
            return f"page={p.get('page_number')}"
    return None

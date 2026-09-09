"""Document validation, checksum, text extraction, chunking — no LLM."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.domain.exceptions import ValidationError

ALLOWED_MIME = {
    "application/pdf": {".pdf"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {".xlsx"},
    "text/plain": {".txt"},
    "application/octet-stream": {".pdf", ".docx", ".xlsx", ".txt"},  # browsers sometimes
}

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
FORBIDDEN_SUFFIXES = {".exe", ".bat", ".cmd", ".ps1", ".sh", ".dll", ".so", ".js", ".msi"}


@dataclass
class ExtractedPage:
    page_number: int
    text: str


@dataclass
class ExtractedChunk:
    page_number: int
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int


@dataclass
class ExtractionResult:
    pages: list[ExtractedPage] = field(default_factory=list)
    chunks: list[ExtractedChunk] = field(default_factory=list)
    tables_text: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\-()+ ]+", "_", base, flags=re.UNICODE).strip(" ._")
    if not base:
        base = "upload.bin"
    if len(base) > 180:
        stem = Path(base).stem[:140]
        suf = Path(base).suffix[:20]
        base = f"{stem}{suf}"
    return base


def validate_upload(*, filename: str, mime_type: str | None, size: int, content: bytes) -> str:
    if size <= 0 or len(content) <= 0:
        raise ValidationError("Empty file", field="file")
    if size > MAX_UPLOAD_BYTES or len(content) > MAX_UPLOAD_BYTES:
        raise ValidationError(f"File exceeds {MAX_UPLOAD_BYTES} bytes", field="file")
    safe = safe_filename(filename)
    suffix = Path(safe).suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES:
        raise ValidationError("Executable content not allowed", field="filename")
    mime = (mime_type or "application/octet-stream").split(";")[0].strip().lower()
    allowed_ext = ALLOWED_MIME.get(mime)
    if allowed_ext is None:
        # infer from extension
        if suffix not in {".pdf", ".docx", ".xlsx", ".txt"}:
            raise ValidationError(f"Unsupported MIME type: {mime}", field="mime_type")
    elif suffix not in allowed_ext and mime != "application/octet-stream":
        raise ValidationError("MIME/extension mismatch", field="mime_type")
    # magic sniff
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        raise ValidationError("File does not look like a PDF", field="file")
    if suffix == ".docx" and content[:2] != b"PK":
        raise ValidationError("File does not look like a DOCX (zip)", field="file")
    if suffix == ".xlsx" and content[:2] != b"PK":
        raise ValidationError("File does not look like an XLSX (zip)", field="file")
    return safe


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def chunk_text(text: str, *, page_number: int, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[ExtractedChunk]:
    text = text.replace("\r\n", "\n")
    if not text.strip():
        return []
    chunks: list[ExtractedChunk] = []
    start = 0
    idx = 0
    n = len(text)
    while start < n:
        end = min(n, start + size)
        piece = text[start:end]
        chunks.append(
            ExtractedChunk(
                page_number=page_number,
                chunk_index=idx,
                text=piece,
                start_offset=start,
                end_offset=end,
            )
        )
        if end >= n:
            break
        start = max(end - overlap, start + 1)
        idx += 1
    return chunks


def extract_txt(content: bytes) -> ExtractionResult:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("cp1251", errors="replace")
    # split on form feed or every ~4000 chars as pages
    raw_pages = text.split("\f") if "\f" in text else [text]
    pages: list[ExtractedPage] = []
    chunks: list[ExtractedChunk] = []
    for i, p in enumerate(raw_pages, start=1):
        pages.append(ExtractedPage(page_number=i, text=p))
        chunks.extend(chunk_text(p, page_number=i))
    return ExtractionResult(pages=pages, chunks=chunks)


def extract_docx(content: bytes) -> ExtractionResult:
    from io import BytesIO

    try:
        from docx import Document as DocxDocument
    except ImportError as exc:  # pragma: no cover
        raise ValidationError("python-docx not installed", field="file") from exc

    doc = DocxDocument(BytesIO(content))
    paras = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
    tables_text: list[str] = []
    for table in doc.tables:
        rows = []
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            rows.append(" | ".join(cells))
        tables_text.append("\n".join(rows))
    body = "\n".join(paras)
    if tables_text:
        body = body + "\n\n" + "\n\n".join(tables_text)
    pages = [ExtractedPage(page_number=1, text=body)]
    chunks = chunk_text(body, page_number=1)
    return ExtractionResult(pages=pages, chunks=chunks, tables_text=tables_text)


def extract_xlsx(content: bytes) -> ExtractionResult:
    from io import BytesIO

    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover
        raise ValidationError("openpyxl not installed", field="file") from exc

    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    pages: list[ExtractedPage] = []
    chunks: list[ExtractedChunk] = []
    tables: list[str] = []
    for i, name in enumerate(wb.sheetnames, start=1):
        ws = wb[name]
        lines = []
        for row in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v) for v in row]
            if any(v.strip() for v in vals):
                lines.append("\t".join(vals))
        text = f"[Sheet: {name}]\n" + "\n".join(lines)
        tables.append(text)
        pages.append(ExtractedPage(page_number=i, text=text))
        chunks.extend(chunk_text(text, page_number=i))
    return ExtractionResult(pages=pages, chunks=chunks, tables_text=tables)


def extract_pdf(content: bytes) -> ExtractionResult:
    from io import BytesIO

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise ValidationError("pypdf not installed", field="file") from exc

    reader = PdfReader(BytesIO(content))
    pages: list[ExtractedPage] = []
    chunks: list[ExtractedChunk] = []
    warnings: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            text = ""
            warnings.append(f"Failed to extract text from PDF page {i}")
        pages.append(ExtractedPage(page_number=i, text=text))
        chunks.extend(chunk_text(text, page_number=i))
    if not any(p.text.strip() for p in pages):
        warnings.append("PDF produced no extractable text (may be scanned images)")
    return ExtractionResult(pages=pages, chunks=chunks, warnings=warnings)


def extract_document(*, filename: str, content: bytes) -> ExtractionResult:
    suffix = Path(safe_filename(filename)).suffix.lower()
    if suffix in {".txt", ".json"}:
        # JSON fixtures are ingested as plain text (no schema invention).
        return extract_txt(content)
    if suffix == ".docx":
        return extract_docx(content)
    if suffix == ".xlsx":
        return extract_xlsx(content)
    if suffix == ".pdf":
        return extract_pdf(content)
    raise ValidationError(f"Unsupported extension: {suffix}", field="filename")

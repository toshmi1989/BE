"""Registry-driven scrub of stale template sample product strings.

Not a global find/replace of arbitrary text — only tokens listed in
`protocol_template_registry.STALE_TEMPLATE_PRODUCT_TOKENS`.
"""

from __future__ import annotations

from typing import Any

from docx.document import Document as DocumentObject

from app.domain.protocol_template_registry import (
    STALE_TEMPLATE_PRODUCT_TOKENS,
    study_is_bosutinib_sample,
)


def _paragraph_set_text(paragraph: Any, text: str) -> None:
    for r in list(paragraph.runs):
        r._element.getparent().remove(r._element)
    paragraph.add_run(text)


def _replace_tokens(text: str, replacement: str) -> tuple[str, int]:
    hits = 0
    out = text
    for tok in STALE_TEMPLATE_PRODUCT_TOKENS:
        if tok in out:
            count = out.count(tok)
            out = out.replace(tok, replacement)
            hits += count
    return out, hits


def _iter_header_footer_parts(section: Any) -> list[Any]:
    parts: list[Any] = []
    for attr in (
        "header",
        "footer",
        "first_page_header",
        "first_page_footer",
        "even_page_header",
        "even_page_footer",
    ):
        part = getattr(section, attr, None)
        if part is not None:
            parts.append(part)
    return parts


def _walk_tables(tables: Any) -> Any:
    """Yield tables including nested cell tables (depth-first)."""
    for table in tables:
        yield table
        for row in table.rows:
            for cell in row.cells:
                yield from _walk_tables(cell.tables)


def _collect_visible_blob(doc: DocumentObject) -> str:
    chunks: list[str] = []
    for p in doc.paragraphs:
        chunks.append(p.text or "")
    for table in _walk_tables(doc.tables):
        for row in table.rows:
            for cell in row.cells:
                chunks.append(cell.text or "")
    for section in doc.sections:
        for hf in _iter_header_footer_parts(section):
            for p in hf.paragraphs:
                chunks.append(p.text or "")
            for table in _walk_tables(hf.tables):
                for row in table.rows:
                    for cell in row.cells:
                        chunks.append(cell.text or "")
    return "\n".join(chunks)


def scrub_stale_template_products(doc: DocumentObject, study_ctx: dict[str, Any]) -> dict[str, Any]:
    """Overwrite Bosutinib/Bosulif sample strings with the study product name.

    If the study *is* the Bosutinib sample case, leave tokens alone.
    If study product is missing, report remaining stale hits for blocking.
    """
    product = study_ctx.get("product") or {}
    if study_is_bosutinib_sample(product):
        return {"scrubbed": 0, "remaining": 0, "skipped": "study_is_bosutinib_sample"}

    replacement = str(product.get("trade_name") or product.get("inn") or "").strip()
    scrubbed = 0

    def handle_paragraph(p: Any) -> None:
        nonlocal scrubbed
        text = p.text or ""
        if not text:
            return
        if not replacement:
            return
        new, hits = _replace_tokens(text, replacement)
        if hits and new != text:
            # Prefer clean identity line in header product cell
            if "Исследуемый препарат" in text:
                new = f"Исследуемый препарат: {replacement}"
            _paragraph_set_text(p, new)
            scrubbed += hits

    # Body paragraphs
    for p in doc.paragraphs:
        handle_paragraph(p)

    # Body tables (incl. nested)
    for table in _walk_tables(doc.tables):
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    handle_paragraph(p)

    # Headers / footers (incl. first/even + tables)
    for section in doc.sections:
        for hf in _iter_header_footer_parts(section):
            for p in hf.paragraphs:
                handle_paragraph(p)
            for table in _walk_tables(hf.tables):
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            handle_paragraph(p)

    blob = _collect_visible_blob(doc)
    remaining = sum(blob.count(t) for t in STALE_TEMPLATE_PRODUCT_TOKENS)

    return {
        "scrubbed": scrubbed,
        "remaining": remaining,
        "replacement": replacement or None,
    }

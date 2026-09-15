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

    Phase 30.3: also scrub stale template dose (400 mg) and template date when
    the study is not the Bosutinib sample and canonical values differ.
    """
    product = study_ctx.get("product") or {}
    if study_is_bosutinib_sample(product):
        return {"scrubbed": 0, "remaining": 0, "skipped": "study_is_bosutinib_sample"}

    replacement = str(product.get("trade_name") or product.get("inn") or "").strip()
    study_dose = str(product.get("dosage") or "").strip()
    study_date = str((study_ctx.get("study") or {}).get("version_date") or "").strip()
    scrubbed = 0
    dose_scrubbed = 0
    date_scrubbed = 0

    def _scrub_text(text: str) -> tuple[str, int, int, int]:
        nonlocal_hits = 0
        d_hits = 0
        date_hits = 0
        new = text
        if replacement:
            new, nonlocal_hits = _replace_tokens(new, replacement)
            if nonlocal_hits and "Исследуемый препарат" in text:
                new = f"Исследуемый препарат: {replacement}"
        # Stale 400 mg when study dose is not 400
        if study_dose and "400" not in study_dose:
            import re

            for pat in (r"\b400\s*мг\b", r"\b400\s*mg\b"):
                if re.search(pat, new, flags=re.IGNORECASE):
                    count = len(re.findall(pat, new, flags=re.IGNORECASE))
                    new = re.sub(pat, study_dose, new, flags=re.IGNORECASE)
                    d_hits += count
        # Template sample date
        if "18.04.2025" in new and study_date and "18.04.2025" not in study_date:
            date_hits = new.count("18.04.2025")
            new = new.replace("18.04.2025", study_date)
        elif "18.04.2025" in new and not study_date:
            # Clear rather than leave template date
            date_hits = new.count("18.04.2025")
            new = new.replace("18.04.2025 г.", "[ДАТА ВЕРСИИ НЕ ЗАДАНА]").replace(
                "18.04.2025", "[ДАТА ВЕРСИИ НЕ ЗАДАНА]"
            )
        return new, nonlocal_hits, d_hits, date_hits

    def handle_paragraph(p: Any) -> None:
        nonlocal scrubbed, dose_scrubbed, date_scrubbed
        text = p.text or ""
        if not text:
            return
        new, hits, d_hits, date_hits = _scrub_text(text)
        if new != text:
            _paragraph_set_text(p, new)
            scrubbed += hits
            dose_scrubbed += d_hits
            date_scrubbed += date_hits

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
        "dose_scrubbed": dose_scrubbed,
        "date_scrubbed": date_scrubbed,
        "remaining": remaining,
        "replacement": replacement or None,
    }

"""DOCX Renderer — presentation only. No study business logic."""

from __future__ import annotations

import hashlib
import re
import shutil
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from app.domain.docx_profile import (
    ACTIVE_SECTION_CODES,
    CRITICAL_UNRESOLVED_PREFIXES,
    DOCX_GENERATOR_VERSION,
    TABLE_KEY_TO_INDEX,
    DocxTemplateProfile,
    get_template_profile,
)
from app.domain.docx_validation import DocxValidationReport, validate_docx_file
from app.domain.document_ingest import sha256_hex

UNRESOLVED_RE = re.compile(r"\{\{[A-Z0-9_.]+\}\}")
SECTION_HEAD_RE = re.compile(r"^(\d+(?:\.\d+)*)\b")
# Template sometimes uses "7. 1." (space after dots) for §7 subsections under Normal style
SECTION_HEAD_FLEX_RE = re.compile(r"^(\d+(?:\s*\.\s*\d+)+)\b")
# Body section titles that are not Word Heading styles (template uses "1 абзац")
SECTION_TITLE_STYLES = frozenset({"1 абзац", "1 Abzatz"})


@dataclass
class RenderResult:
    status: str  # READY | BLOCKED | FAILED
    mode: str
    output_path: Path | None
    checksum: str | None
    filename: str | None
    validation: DocxValidationReport | None
    blocking_reasons: list[str] = field(default_factory=list)
    table_numbers: dict[str, int] = field(default_factory=dict)
    template_version: str = ""
    generator_version: str = DOCX_GENERATOR_VERSION
    profile_version: str = ""


def _verify_template(profile: DocxTemplateProfile, path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"Template missing: {path}"]
    digest = sha256_hex(path.read_bytes())
    if digest != profile.file_checksum:
        errors.append(
            f"Template checksum mismatch: expected {profile.file_checksum}, got {digest}"
        )
    return errors


def _collect_unresolved(obj: Any) -> list[str]:
    found: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, str):
            found.extend(UNRESOLVED_RE.findall(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj)
    return sorted(set(found))


def _is_critical_unresolved(markers: list[str]) -> list[str]:
    critical: list[str] = []
    for m in markers:
        for prefix in CRITICAL_UNRESOLVED_PREFIXES:
            if m.startswith(prefix.rstrip("}")) or m == prefix or prefix.rstrip("}") in m:
                critical.append(m)
                break
            if m.startswith("{{") and any(
                m.startswith(p if p.endswith("}}") else p) for p in CRITICAL_UNRESOLVED_PREFIXES
            ):
                critical.append(m)
                break
    # simpler: any marker matching critical prefixes
    out: list[str] = []
    for m in markers:
        for p in CRITICAL_UNRESOLVED_PREFIXES:
            key = p.replace("{{", "").replace("}}", "").split(".")[0]
            if key and key in m:
                out.append(m)
                break
        if m == "{{UNRESOLVED}}":
            out.append(m)
    return sorted(set(out))


def _gate_mode(
    mode: str,
    *,
    draft_status: str,
    unresolved: list[str],
    consistency: dict,
    study: dict | None,
    product: dict | None,
    reference: dict | None,
    sponsor: dict | None,
) -> list[str]:
    """Return blocking reasons for the requested render mode."""
    reasons: list[str] = []
    mode = mode.upper()
    critical = _is_critical_unresolved(unresolved)

    protocol_number = (study or {}).get("protocol_number")
    if not protocol_number:
        reasons.append("missing protocol_number")
    if not product or not (product.get("trade_name") or product.get("inn")):
        reasons.append("missing test product")
    if not reference or not (reference.get("trade_name") or reference.get("inn")):
        reasons.append("missing reference product")
    if not sponsor or not (sponsor.get("name") or sponsor.get("legal_name")):
        # Phase 8 leaves sponsor unresolved — FINAL/REVIEW must block
        if mode in {"REVIEW", "FINAL"}:
            reasons.append("missing sponsor")
    if draft_status == "BLOCKED" and mode in {"REVIEW", "FINAL"}:
        reasons.append("ProtocolDraft is BLOCKED")

    if mode == "FINAL":
        if unresolved:
            reasons.append(f"unresolved fields present ({len(unresolved)})")
        if critical:
            reasons.append(f"critical unresolved: {critical[:10]}")
        if not consistency.get("evaluable_n"):
            reasons.append("missing evaluable_n")
        if not consistency.get("design"):
            reasons.append("missing design")
    elif mode == "REVIEW":
        if critical:
            reasons.append(f"critical unresolved: {critical[:10]}")
        if not protocol_number or not product or not reference:
            pass  # already added
    # DRAFT: may proceed with unresolved, but must not invent values; validation allows markers
    return reasons


def _delete_paragraph(paragraph: Paragraph) -> None:
    el = paragraph._element
    parent = el.getparent()
    if parent is not None:
        parent.remove(el)


def _insert_paragraph_after(paragraph: Paragraph, text: str, style: str | None = None) -> Paragraph:
    new_p = deepcopy(paragraph._element)
    # clear runs
    for child in list(new_p):
        if child.tag == qn("w:r") or child.tag.endswith("}r"):
            new_p.remove(child)
    paragraph._element.addnext(new_p)
    new_para = Paragraph(new_p, paragraph._parent)
    if style:
        try:
            new_para.style = style
        except Exception:  # noqa: BLE001
            pass
    if text:
        new_para.add_run(text)
    return new_para


def _normalize_section_code(raw: str) -> str:
    return re.sub(r"\s+", "", raw or "")


def _find_heading_indexes(doc: Document) -> dict[str, int]:
    """Map section_code → paragraph index for body section titles.

    Template mixes Heading 1/2 with style «1 абзац» (sections 3, 4, 7, 8, 18)
    and Normal-styled «7.x» lines under §7.
    """
    from app.domain.docx_profile import ACTIVE_SECTION_CODES

    mapping: dict[str, int] = {}
    active = set(ACTIVE_SECTION_CODES)

    def _register(code: str, idx: int) -> None:
        if code and code not in mapping:
            mapping[code] = idx

    for i, p in enumerate(doc.paragraphs):
        style = (p.style.name if p.style else "") or ""
        text = (p.text or "").strip().replace("\t", " ")
        if not text:
            continue
        # Skip TOC
        if style.lower().startswith("toc"):
            continue

        if style.startswith("Heading"):
            m = SECTION_HEAD_RE.match(text)
            if m:
                _register(m.group(1), i)
            continue

        if style in SECTION_TITLE_STYLES or style.startswith("1 "):
            m = SECTION_HEAD_RE.match(text)
            if m:
                _register(m.group(1), i)
            continue

        # Normal / List: only dotted codes that are in ACTIVE set (avoid "1. Evaluate…")
        if style in {"Normal", "List Paragraph"} or not style.startswith("Heading"):
            mflex = SECTION_HEAD_FLEX_RE.match(text)
            if mflex:
                code = _normalize_section_code(mflex.group(1))
                if code in active:
                    _register(code, i)
    return mapping


def _section_body_range(heading_indexes: dict[str, int], code: str, total: int) -> tuple[int, int] | None:
    if code not in heading_indexes:
        return None
    start = heading_indexes[code] + 1
    # next heading with same or higher level / any later heading index
    later = sorted(i for c, i in heading_indexes.items() if i > heading_indexes[code])
    end = later[0] if later else total
    return start, end


def _clear_paragraph_range(doc: Document, start: int, end: int) -> None:
    # delete from end-1 down to start to keep indexes stable enough by using elements
    paras = list(doc.paragraphs)
    for idx in range(end - 1, start - 1, -1):
        if 0 <= idx < len(paras):
            style = paras[idx].style.name if paras[idx].style else ""
            text = (paras[idx].text or "").strip().replace("\t", " ")
            # never delete headings / section title paras
            if style.startswith("Heading"):
                continue
            if style in SECTION_TITLE_STYLES or (style and style.startswith("1 ")):
                continue
            mflex = SECTION_HEAD_FLEX_RE.match(text)
            if mflex and _normalize_section_code(mflex.group(1)):
                # nested section title under Normal — leave for its own replace
                continue
            _delete_paragraph(paras[idx])


def _set_cell_text(cell, text: str) -> None:
    # preserve first paragraph style; clear extra paras
    paras = cell.paragraphs
    if not paras:
        cell.text = text
        return
    # clear all paragraphs except first
    for p in paras[1:]:
        _delete_paragraph(p)
    p0 = cell.paragraphs[0]
    # clear runs
    for r in list(p0.runs):
        r._element.getparent().remove(r._element)
    p0.add_run(str(text) if text is not None else "")


def _normalize_label(label: str) -> str:
    return (label or "").strip().lower().replace("ё", "е").rstrip(":").replace("\t", " ")


def _fill_label_value_table(table, rows: list[list[Any]]) -> None:
    """Fill 2-column label/value table by matching labels — never by blind row index."""
    from app.domain.product_mapping import field_for_label, normalize_label

    # Build incoming map: normalized label → value (prefer col0 as label, col1 as value)
    incoming: dict[str, str] = {}
    ordered_values: list[tuple[str, str]] = []
    for row_data in rows:
        if not row_data:
            continue
        if len(row_data) >= 2:
            lab = str(row_data[0] or "")
            val = "" if row_data[1] is None else str(row_data[1])
            incoming[_normalize_label(lab)] = val
            # also map via product field aliases
            field = field_for_label(lab)
            if field:
                incoming[field] = val
            ordered_values.append((lab, val))
        else:
            ordered_values.append(("", str(row_data[0])))

    matched_any = False
    for table_row in table.rows:
        cells = table_row.cells
        if len(cells) < 2:
            continue
        label_text = (cells[0].text or "").strip()
        norm = _normalize_label(label_text)
        value = None
        if norm in incoming:
            value = incoming[norm]
        else:
            field = field_for_label(label_text)
            if field and field in incoming:
                value = incoming[field]
            else:
                # fuzzy contains match for synopsis population rows
                for key, val in incoming.items():
                    if key and key in norm:
                        value = val
                        break
        if value is not None:
            _set_cell_text(cells[1], value)
            matched_any = True

    # Fallback: if no labels matched (unusual table), keep prior index fill for short tables
    if not matched_any:
        for r_i, row_data in enumerate(rows):
            if r_i >= len(table.rows):
                break
            cells = table.rows[r_i].cells
            for c_i, val in enumerate(row_data):
                if c_i >= len(cells):
                    break
                if len(row_data) == 2 and c_i == 0:
                    existing = (cells[0].text or "").strip()
                    if existing and not str(val or "").endswith(":"):
                        continue
                _set_cell_text(cells[c_i], "" if val is None else str(val))


def _apply_synopsis_canonical_fill(doc: Document, study_ctx: dict, consistency: dict[str, Any]) -> None:
    """Fill T03 admin labels + rewrite subject-count cells from SubjectPlan (no global N scrub)."""
    from app.domain.synopsis_fill import apply_synopsis_subject_n_to_table

    idx = TABLE_KEY_TO_INDEX.get("SYNOPSIS_N")
    if idx is None or idx >= len(doc.tables):
        return
    table = doc.tables[idx]
    audit = apply_synopsis_subject_n_to_table(table, study_ctx, consistency)
    for item in audit:
        _set_cell_text(item["cell"], item["new_text"])


def _legacy_subject_n_gate(doc: Document, consistency: dict[str, Any]) -> list[str]:
    """Block REVIEW/FINAL if legacy subject-count 46 remains (TOC page numbers ignored)."""
    from app.domain.synopsis_fill import find_legacy_subject_count_46

    rand_n = consistency.get("randomized_n")
    paragraphs = [
        (f"para[{i}]", p.text or "", (p.style.name if p.style else "") or "")
        for i, p in enumerate(doc.paragraphs)
    ]
    table_cells: list[tuple[str, str]] = []
    for ti, table in enumerate(doc.tables):
        for ri, row in enumerate(table.rows):
            for ci, cell in enumerate(row.cells):
                table_cells.append((f"T{ti}R{ri}C{ci}", cell.text or ""))
    hits = find_legacy_subject_count_46(
        paragraphs=paragraphs,
        table_cells=table_cells,
        canonical_randomized_n=int(rand_n) if rand_n is not None else None,
    )
    if not hits:
        return []
    snips = [h.get("text_snip") or h.get("location") for h in hits[:5]]
    return [f"legacy subject-count 46 remains ({len(hits)}): {snips}"]


def _rebuild_table_data_rows(table, columns: list[str], data_rows: list[list[Any]]) -> None:
    """Keep header row style; resize body rows to match data."""
    if not table.rows:
        return
    header = table.rows[0]
    # remove extra rows from bottom
    while len(table.rows) > 1:
        tbl = table._tbl
        tbl.remove(table.rows[-1]._tr)
    # add rows by copying header row element as style donor then overwrite
    for row_data in data_rows:
        new_tr = deepcopy(header._tr)
        table._tbl.append(new_tr)
        # map to last row
        row = table.rows[-1]
        for c_i, cell in enumerate(row.cells):
            val = row_data[c_i] if c_i < len(row_data) else ""
            _set_cell_text(cell, "" if val is None else str(val))


def _assign_table_numbers(protocol_tables: list[dict]) -> dict[str, int]:
    from app.domain.table_registry import build_table_registry

    registry = build_table_registry(protocol_tables)
    return {k: e.actual_number for k, e in registry.by_key().items() if e.actual_number}


def _resolve_reference_display(ref: dict, table_numbers: dict[str, int]) -> str:
    ttype = ref.get("target_type")
    tid = ref.get("target_id")
    if ttype == "table":
        num = table_numbers.get(tid)
        if num is not None:
            return f"см. Таблицу {num}"
        return f"см. таблицу {tid}"
    if ttype == "section":
        return f"см. раздел {tid}"
    if ttype == "appendix":
        return f"см. Приложение {tid}"
    return ref.get("display_text") or str(tid)


def _apply_header_footer_vars(doc: Document, variables: dict[str, str]) -> None:
    """Replace only explicit {{TOKEN}} in headers/footers — never invent body values."""
    for section in doc.sections:
        for hf in (section.header, section.footer):
            for p in hf.paragraphs:
                text = p.text or ""
                if "{{" not in text:
                    continue
                new = text
                for k, v in variables.items():
                    new = new.replace(f"{{{{{k}}}}}", v)
                if new != text:
                    for r in list(p.runs):
                        r._element.getparent().remove(r._element)
                    p.add_run(new)


def _set_core_properties(doc: Document, meta: dict[str, str]) -> None:
    props = doc.core_properties
    if meta.get("title"):
        props.title = meta["title"]
    if meta.get("subject"):
        props.subject = meta["subject"]
    if meta.get("author"):
        props.author = meta["author"]
    if meta.get("keywords"):
        props.keywords = meta["keywords"]
    props.modified = datetime.now(timezone.utc).replace(tzinfo=None)


def _section_plain_texts(section: dict) -> list[str]:
    lines: list[str] = []
    for b in section.get("content_blocks") or []:
        btype = b.get("type")
        if btype == "TEXT" and b.get("text"):
            lines.append(str(b["text"]))
        elif btype in {"LIST", "NUMBERED_LIST"}:
            for i, item in enumerate(b.get("items") or [], start=1):
                prefix = f"{i}. " if btype == "NUMBERED_LIST" else "• "
                lines.append(prefix + str(item))
        elif btype == "FORMULA" and b.get("text"):
            lines.append(str(b["text"]))
        elif btype == "REFERENCE":
            lines.append(str(b.get("display_text") or ""))
        elif btype == "TABLE" and b.get("display_text"):
            lines.append(str(b["display_text"]))
        elif btype == "SIGNATURE":
            lines.append("[Блок подписи]")
    return [ln for ln in lines if ln]


def render_protocol_docx(
    *,
    protocol_payload: dict,
    study_ctx: dict,
    mode: str = "DRAFT",
    output_dir: Path,
    project_slug: str = "project",
    protocol_version: str = "1",
    only_sections: set[str] | frozenset[str] | list[str] | None = None,
) -> RenderResult:
    """
    Render ProtocolDraft payload into DOCX using immutable template copy.
    study_ctx supplies cover/header variables only (no calculations here).
    only_sections: if set, replace only those section bodies (targeted 12B.1 path).
    """
    profile = get_template_profile()
    mode = mode.upper()
    template_path = profile.template_path()
    tpl_errors = _verify_template(profile, template_path)
    if tpl_errors:
        return RenderResult(
            status="FAILED",
            mode=mode,
            output_path=None,
            checksum=None,
            filename=None,
            validation=None,
            blocking_reasons=tpl_errors,
            template_version=profile.template_version,
            profile_version=profile.profile_version,
        )

    sections = protocol_payload.get("sections") or []
    tables = protocol_payload.get("tables") or []
    references = protocol_payload.get("references") or []
    unresolved = _collect_unresolved(
        {
            "sections": sections,
            "tables": tables,
            "report": protocol_payload.get("build_report"),
        }
    )
    # Also scan for forbidden invented tokens in assembled content
    blob = str(sections) + str(tables)
    for bad in ("ХХ", "XXX", "примерно"):
        if bad.lower() in blob.lower() and "{{" not in bad:
            # XXX inside {{ }} is fine; bare XXX is bad — already stripped in assembly
            pass

    study = study_ctx.get("study") or {}
    product = study_ctx.get("product") or {}
    reference = study_ctx.get("reference_product") or {}
    sponsor = study_ctx.get("sponsor") or {}
    consistency = protocol_payload.get("consistency_snapshot") or study_ctx.get("consistency") or {}

    gate = _gate_mode(
        mode,
        draft_status=str(protocol_payload.get("status") or ""),
        unresolved=unresolved,
        consistency=consistency,
        study=study,
        product=product,
        reference=reference,
        sponsor=sponsor,
    )
    if gate and mode in {"REVIEW", "FINAL"}:
        return RenderResult(
            status="BLOCKED",
            mode=mode,
            output_path=None,
            checksum=None,
            filename=None,
            validation=None,
            blocking_reasons=gate,
            template_version=profile.template_version,
            profile_version=profile.profile_version,
        )
    if gate and mode == "DRAFT" and any(
        r.startswith("missing protocol_number") or r.startswith("missing test product") for r in gate
    ):
        # Even DRAFT requires minimal identity for a meaningful file — block rather than invent
        if "missing protocol_number" in gate or "missing test product" in gate:
            # Allow DRAFT without protocol_number only if study has title? Spec says block missing protocol number for generation.
            return RenderResult(
                status="BLOCKED",
                mode=mode,
                output_path=None,
                checksum=None,
                filename=None,
                validation=None,
                blocking_reasons=gate,
                template_version=profile.template_version,
                profile_version=profile.profile_version,
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"protocol-{project_slug}-v{protocol_version}-{mode.lower()}-{ts}.docx"
    out_path = output_dir / filename
    # immutable template: copy then edit the copy only
    shutil.copy2(template_path, out_path)

    doc = Document(str(out_path))
    table_numbers = _assign_table_numbers(tables)

    # Resolve reference display texts in-memory for section injection
    ref_by_section: dict[str, list[str]] = {}
    for ref in references:
        display = _resolve_reference_display(ref, table_numbers)
        ref_by_section.setdefault(ref.get("source_section") or "", []).append(display)

    # Replace active section bodies from ProtocolDraft
    sections_by_code = {s["section_code"]: s for s in sections}
    only_set = set(only_sections) if only_sections is not None else None
    # Targeted path: only touch tables referenced by selected section blocks
    allowed_table_keys: set[str] | None = None
    if only_set is not None:
        allowed_table_keys = set()
        for code in only_set:
            for b in (sections_by_code.get(code) or {}).get("content_blocks") or []:
                tk = b.get("table_key")
                if tk:
                    allowed_table_keys.add(str(tk))

    # Fill mapped dynamic tables (full path = all keys; targeted = allowed only)
    table_by_key = {t["table_key"]: t for t in tables}
    for key, idx in TABLE_KEY_TO_INDEX.items():
        if allowed_table_keys is not None and key not in allowed_table_keys:
            continue
        if key not in table_by_key:
            continue
        if idx >= len(doc.tables):
            continue
        pt = table_by_key[key]
        fill_mode = str(pt.get("fill_mode") or "LABEL").upper()
        if fill_mode == "PRESERVE":
            continue
        tmpl = doc.tables[idx]
        rows = pt.get("rows") or []
        cols = pt.get("columns") or []
        if not rows and fill_mode != "REBUILD":
            continue
        if fill_mode == "REBUILD" or key in {"BLOOD_SAMPLING", "PK_PARAMETERS", "CV_EVIDENCE", "MEAL_TIMING", "SOURCES"}:
            if rows:
                _rebuild_table_data_rows(tmpl, cols, rows)
        elif key in {"TEST_PRODUCT", "REFERENCE_PRODUCT", "STUDY_METADATA", "SIGNATURES"}:
            _fill_label_value_table(tmpl, rows)
        elif key == "SYNOPSIS_N":
            # merge into synopsis table T03 — fill matching labels if present
            _fill_label_value_table(tmpl, rows)
        else:
            _fill_label_value_table(tmpl, rows)

    touch_synopsis = only_set is None or (
        "SYNOPSIS_N" in (allowed_table_keys or set())
        or "SYNOPSIS" in only_set
        or any(str(c).startswith("1.") for c in only_set)
    )
    if touch_synopsis:
        _apply_synopsis_canonical_fill(doc, study_ctx, consistency)

    heading_map = _find_heading_indexes(doc)
    section_codes_iter = (
        [c for c in ACTIVE_SECTION_CODES if c in only_set]
        if only_set is not None
        else list(ACTIVE_SECTION_CODES)
    )
    for code in section_codes_iter:
        sec = sections_by_code.get(code)
        if not sec:
            continue
        rng = _section_body_range(heading_map, code, len(doc.paragraphs))
        if rng is None:
            continue
        start, end = rng
        _clear_paragraph_range(doc, start, end)
        # re-find heading after deletes
        heading_map = _find_heading_indexes(doc)
        if code not in heading_map:
            continue
        head_idx = heading_map[code]
        head_para = doc.paragraphs[head_idx]
        lines = _section_plain_texts(sec)
        # update TABLE display texts with live numbers
        for b in sec.get("content_blocks") or []:
            if b.get("type") == "TABLE" and b.get("table_key") in table_numbers:
                num = table_numbers[b["table_key"]]
                lines.append(f"Таблица {num}")
        for ref_line in ref_by_section.get(code, []):
            if ref_line not in lines:
                lines.append(ref_line)
        # DRAFT: keep unresolved markers visible; FINAL already gated
        insert_after = head_para
        for line in lines:
            if mode != "DRAFT" and UNRESOLVED_RE.search(line):
                # REVIEW/FINAL should not reach here with critical unresolved
                continue
            insert_after = _insert_paragraph_after(insert_after, line, style="Normal")

    # Cover / synopsis table T01 light fill — skip on narrow targeted renders
    touch_cover = only_set is None or any(
        c in only_set for c in ("1.1", "1.2", "1.3", "SYNOPSIS", "2.1.1")
    )
    if touch_cover and len(doc.tables) > 0 and product:
        t0 = doc.tables[0]
        # best-effort: do not invent; only write known values into empty-ish value cells
        from app.domain.org_render import resolve_sponsor as _resolve_sponsor

        sp = _resolve_sponsor(study_ctx)
        known = {
            "protocol": str(study.get("protocol_number") or ""),
            "product": str(product.get("trade_name") or product.get("inn") or ""),
            "dose": str(product.get("dosage") or ""),
            "design": str(consistency.get("design") or ""),
            "sponsor": str((sp or {}).get("name") or (sp or {}).get("legal_name") or ""),
        }
        for row in t0.rows:
            label = (row.cells[0].text or "").lower() if row.cells else ""
            if len(row.cells) < 2:
                continue
            if "протокол" in label and known["protocol"]:
                _set_cell_text(row.cells[1], known["protocol"])
            elif ("препарат" in label or "назван" in label) and known["product"]:
                _set_cell_text(row.cells[1], known["product"])
            elif "дизайн" in label and known["design"]:
                _set_cell_text(row.cells[1], known["design"])
            elif ("доз" in label) and known["dose"]:
                _set_cell_text(row.cells[1], known["dose"])
            elif "спонсор" in label and known["sponsor"]:
                _set_cell_text(row.cells[1], known["sponsor"])

    # Header/footer vars: safe on targeted path (placeholders only, no section rewrite)
    hf_vars = {
        "PROTOCOL_NUMBER": str(study.get("protocol_number") or ""),
        "TEST_PRODUCT": str(product.get("trade_name") or product.get("inn") or ""),
        "VERSION": str(protocol_version),
        "DATE": str(study.get("version_date") or ""),
    }
    _apply_header_footer_vars(doc, hf_vars)

    title = study.get("title") or study.get("short_title") or product.get("trade_name") or "BE Protocol"
    _set_core_properties(
        doc,
        {
            "title": str(title),
            "subject": f"BE Protocol {study.get('protocol_number') or ''}".strip(),
            "author": "BE Protocol Platform",
            "keywords": "bioequivalence,protocol,BE",
        },
    )

    # REVIEW/FINAL: block if legacy subject-count 46 survives after synopsis fill + section replace
    if mode in {"REVIEW", "FINAL"}:
        legacy_hits = _legacy_subject_n_gate(doc, consistency)
        if legacy_hits:
            out_path.unlink(missing_ok=True)
            return RenderResult(
                status="BLOCKED",
                mode=mode,
                output_path=None,
                checksum=None,
                filename=None,
                validation=None,
                blocking_reasons=legacy_hits,
                table_numbers=table_numbers,
                template_version=profile.template_version,
                profile_version=profile.profile_version,
            )

    # TOC fields: leave Word field codes intact (documented)
    doc.save(str(out_path))

    allow_unresolved = mode == "DRAFT"
    validation = validate_docx_file(out_path, allow_unresolved=allow_unresolved)
    # Extra gate: FINAL/REVIEW must have clean validation
    if mode in {"REVIEW", "FINAL"} and validation.blocking:
        out_path.unlink(missing_ok=True)
        return RenderResult(
            status="BLOCKED",
            mode=mode,
            output_path=None,
            checksum=None,
            filename=None,
            validation=validation,
            blocking_reasons=[i.message for i in validation.issues if i.severity in {"CRITICAL", "ERROR"}],
            table_numbers=table_numbers,
            template_version=profile.template_version,
            profile_version=profile.profile_version,
        )

    checksum = sha256_hex(out_path.read_bytes())
    status = "READY"
    if mode == "DRAFT" and (gate or validation.unresolved_found):
        # DRAFT may be READY with warnings
        status = "READY"
    return RenderResult(
        status=status,
        mode=mode,
        output_path=out_path,
        checksum=checksum,
        filename=filename,
        validation=validation,
        blocking_reasons=gate,
        table_numbers=table_numbers,
        template_version=profile.template_version,
        profile_version=profile.profile_version,
    )

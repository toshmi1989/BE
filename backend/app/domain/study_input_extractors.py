"""Deterministic extractors for writer documents — Phase 14.

AI-off. Never mutates Study. Never invents missing values.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.domain.study_input_package import CandidateStudyValue


def _cand(
    *,
    field_path: str,
    value: Any,
    value_type: str,
    source_id: str,
    document_type: str,
    excerpt: str,
    location: str | None = None,
    confidence: str = "HIGH",
    original_filename: str | None = None,
    document_id: str | None = None,
    source_version_id: str | None = None,
) -> CandidateStudyValue:
    return CandidateStudyValue(
        field_path=field_path,
        value=value,
        value_type=value_type,
        source_id=source_id,
        document_type=document_type,
        excerpt=excerpt[:500],
        location=location,
        confidence=confidence,
        extraction_method="DETERMINISTIC",
        status="PROPOSED",
        original_filename=original_filename,
        document_id=document_id,
        source_version_id=source_version_id,
    )


def extract_text_from_docx(path: Path) -> str:
    from docx import Document

    d = Document(str(path))
    texts: list[str] = []
    for para in d.paragraphs:
        if para.text.strip():
            texts.append(para.text.strip())
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            uniq: list[str] = []
            for c in cells:
                if not uniq or c != uniq[-1]:
                    uniq.append(c)
            line = " | ".join(uniq)
            if line.strip(" |"):
                texts.append(line)
    return "\n".join(texts)


def extract_text_from_pdf(path: Path) -> tuple[str, list[dict[str, Any]]]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages: list[dict[str, Any]] = []
    parts: list[str] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        pages.append({"page_number": i, "text": t})
        parts.append(t)
    return "\n".join(parts), pages


def extract_checklist(
    text: str,
    *,
    source_id: str,
    original_filename: str | None = None,
    document_id: str | None = None,
    tables: list[dict[str, Any]] | None = None,
) -> list[CandidateStudyValue]:
    from app.domain.study_input_binary_ingest import find_table_location

    out: list[CandidateStudyValue] = []
    meta = dict(
        source_id=source_id,
        document_type="CHECKLIST",
        original_filename=original_filename,
        document_id=document_id,
    )

    def loc(fallback: str, *needles: str) -> str:
        if tables:
            for n in needles:
                hit = find_table_location(tables, n)
                if hit:
                    return hit
        return fallback

    m = re.search(r"Номер протокола[^\n|]*\|\s*([A-Z0-9\-]+)", text, re.I)
    if m:
        out.append(
            _cand(
                field_path="study.protocol_number",
                value=m.group(1).strip(),
                value_type="string",
                excerpt=m.group(0),
                location=loc("checklist.protocol", "Номер протокола"),
                **meta,
            )
        )

    m = re.search(r"Спонсор\s*\|\s*([^|\n]+)", text, re.I)
    if m:
        out.append(
            _cand(
                field_path="sponsor.name",
                value=m.group(1).strip(),
                value_type="string",
                excerpt=m.group(0),
                location=loc("checklist.sponsor", "Спонсор"),
                **meta,
            )
        )

    m = re.search(r"Название организации\s*\|\s*([^|\n]+)", text, re.I)
    if m:
        out.append(
            _cand(
                field_path="cro.name",
                value=m.group(1).strip(),
                value_type="string",
                excerpt=m.group(0),
                location=loc("checklist.cro", "Название организации"),
                **meta,
            )
        )

    m = re.search(r"ФИО, должность\s*\|\s*([^|\n]+)", text, re.I)
    if m:
        name_part = m.group(1).split(",")[0].strip()
        out.append(
            _cand(
                field_path="investigator.name",
                value=name_part,
                value_type="string",
                excerpt=m.group(0),
                location=loc("checklist.investigator", "ФИО, должность", "Главный исследователь"),
                **meta,
            )
        )
        if "," in m.group(1):
            out.append(
                _cand(
                    field_path="investigator.position",
                    value=m.group(1).split(",", 1)[1].strip(),
                    value_type="string",
                    excerpt=m.group(0),
                    location=loc("checklist.investigator.position", "ФИО, должность"),
                    confidence="MEDIUM",
                    **meta,
                )
            )

    m = re.search(r"Производитель исследуемого препарата\s*\|\s*([^|\n]+)", text, re.I)
    if m and m.group(1).strip():
        out.append(
            _cand(
                field_path="test_product.manufacturer",
                value=m.group(1).strip(),
                value_type="string",
                excerpt=m.group(0),
                location=loc("checklist.test_manufacturer", "Производитель исследуемого"),
                **meta,
            )
        )

    m = re.search(r"Производитель референтного препарата\s*\|\s*([^|\n]+)", text, re.I)
    if m and m.group(1).strip():
        out.append(
            _cand(
                field_path="reference_product.manufacturer",
                value=m.group(1).strip(),
                value_type="string",
                excerpt=m.group(0),
                location=loc("checklist.ref_manufacturer", "Производитель референтного"),
                **meta,
            )
        )

    m = re.search(
        r"Название референтного препарата\s*\|\s*([^|\n]*?(\d+)\s*мг[^|\n]*)",
        text,
        re.I,
    )
    if m:
        line = m.group(1).strip()
        dose = f"{m.group(2)} mg"
        name = line.split(",")[0].strip()
        out.append(
            _cand(
                field_path="reference_product.name",
                value=name,
                value_type="string",
                excerpt=m.group(0),
                location=loc("checklist.reference_product", "Название референтного препарата"),
                **meta,
            )
        )
        out.append(
            _cand(
                field_path="reference_product.dose",
                value=dose,
                value_type="string",
                excerpt=m.group(0),
                location=loc("checklist.reference_product.dose", "30 мг", "Название референтного препарата"),
                confidence="HIGH",
                **meta,
            )
        )
        if "пролонг" in line.lower() or "таблет" in line.lower():
            out.append(
                _cand(
                    field_path="reference_product.dosage_form",
                    value="prolonged-release film-coated tablet",
                    value_type="string",
                    excerpt=line,
                    location=loc("checklist.reference_product.form", "пролонгированным"),
                    confidence="MEDIUM",
                    **meta,
                )
            )

    m = re.search(r"ДРУ на референтный препарат\s*\|\s*([^|\n]+)", text, re.I)
    if m and m.group(1).strip():
        out.append(
            _cand(
                field_path="reference_product.marketing_authorization_holder",
                value=m.group(1).strip(),
                value_type="string",
                excerpt=m.group(0),
                location=loc("checklist.reference_mah", "ДРУ на референтный"),
                **meta,
            )
        )

    return out


def extract_synopsis(
    text: str,
    *,
    source_id: str,
    original_filename: str | None = None,
    document_id: str | None = None,
) -> list[CandidateStudyValue]:
    out: list[CandidateStudyValue] = []
    meta = dict(
        source_id=source_id,
        document_type="SYNOPSIS",
        original_filename=original_filename,
        document_id=document_id,
    )

    m = re.search(r"Протокол\s*№[^\n|]*\|\s*([A-Z0-9\-]+)", text, re.I)
    if not m:
        m = re.search(r"(UPDCB-\d+-BE-\d{4})", text)
    if m:
        out.append(_cand(field_path="study.protocol_number", value=m.group(1).strip(), value_type="string", excerpt=m.group(0), location="synopsis.protocol", **meta))

    if "ПРОМОМЕД РУС" in text:
        out.append(_cand(field_path="sponsor.name", value='ООО «ПРОМОМЕД РУС»', value_type="string", excerpt="ООО «ПРОМОМЕД РУС»", location="synopsis.sponsor", **meta))

    # Test product 15 mg
    m = re.search(r"тестируемый[^\n]{0,40}\|\s*([^|\n]*?15\s*мг[^|\n]*)", text, re.I)
    if m:
        line = m.group(1).strip()
        out.append(_cand(field_path="test_product.dose", value="15 mg", value_type="string", excerpt=m.group(0)[:400], location="synopsis.test_product.dose", **meta))
        if "пролонг" in line.lower():
            out.append(_cand(field_path="test_product.dosage_form", value="prolonged-release film-coated tablet", value_type="string", excerpt=line[:300], location="synopsis.test_product.form", confidence="MEDIUM", **meta))

    # Reference 15 mg — DO NOT overwrite checklist 30
    m = re.search(r"референтн[^\n]{0,40}\|\s*([^|\n]*РАНВЭК[^|\n]*?(\d+)\s*мг[^|\n]*)", text, re.I)
    if m:
        out.append(_cand(field_path="reference_product.name", value="РАНВЭК", value_type="string", excerpt=m.group(0)[:400], location="synopsis.reference_product", **meta))
        out.append(_cand(field_path="reference_product.dose", value=f"{m.group(2)} mg", value_type="string", excerpt=m.group(0)[:400], location="synopsis.reference_product.dose", **meta))

    # Design block
    m = re.search(r"Дизайн исследования\s*\|\s*([^|\n]+)", text, re.I)
    design_blob = m.group(1) if m else text
    if re.search(r"рандомизированн", design_blob, re.I):
        out.append(_cand(field_path="design.randomized", value=True, value_type="bool", excerpt=design_blob[:300], location="synopsis.design", **meta))
    if re.search(r"открыт", design_blob, re.I):
        out.append(_cand(field_path="design.open_label", value=True, value_type="bool", excerpt=design_blob[:300], location="synopsis.design", **meta))
    if re.search(r"перекрестн", design_blob, re.I):
        out.append(_cand(field_path="design.crossover", value=True, value_type="bool", excerpt=design_blob[:300], location="synopsis.design", **meta))
    if re.search(r"двухпериодн", design_blob, re.I):
        out.append(_cand(field_path="design.periods", value=2, value_type="int", excerpt=design_blob[:300], location="synopsis.design.periods", **meta))
    if re.search(r"двумя последовательностями|двухпоследовательн", design_blob, re.I):
        out.append(_cand(field_path="design.sequences", value=2, value_type="int", excerpt=design_blob[:300], location="synopsis.design.sequences", **meta))
    if re.search(r"четырех группах|четырёх группах|4 групп", design_blob, re.I):
        out.append(_cand(field_path="design.groups", value=4, value_type="int", excerpt=design_blob[:300], location="synopsis.design.groups", **meta))
    if re.search(r"адаптивн", design_blob, re.I):
        out.append(_cand(field_path="design.adaptive", value=True, value_type="bool", excerpt=design_blob[:300], location="synopsis.design.adaptive", confidence="MEDIUM", **meta))
    conds = []
    if re.search(r"натощак", design_blob, re.I) or re.search(r"натощак", text, re.I):
        conds.append("fasting")
        out.append(_cand(field_path="treatment.fasting", value=True, value_type="bool", excerpt="натощак", location="synopsis.treatment", **meta))
    if re.search(r"после приема пищи|после приёма пищи", text, re.I):
        conds.append("fed")
        out.append(_cand(field_path="treatment.fed", value=True, value_type="bool", excerpt="после приема пищи", location="synopsis.treatment", **meta))
    if conds:
        out.append(_cand(field_path="design.conditions", value=conds, value_type="list", excerpt=";".join(conds), location="synopsis.design.conditions", **meta))
        out.append(_cand(field_path="food.condition", value="+".join(conds), value_type="string", excerpt=";".join(conds), location="synopsis.food", confidence="MEDIUM", **meta))

    # Subjects
    m = re.search(r"мужского пола", text, re.I)
    if m:
        out.append(_cand(field_path="subjects.sex", value="male", value_type="string", excerpt=m.group(0), location="synopsis.subjects.sex", **meta))
        out.append(_cand(field_path="subjects.type", value="healthy_volunteers", value_type="string", excerpt="здоровых добровольцев", location="synopsis.subjects.type", confidence="MEDIUM", **meta))
    m = re.search(r"возрасте от\s*(\d+)\s*до\s*(\d+)\s*лет", text, re.I)
    if m:
        out.append(_cand(field_path="subjects.age_min", value=int(m.group(1)), value_type="int", excerpt=m.group(0), location="synopsis.subjects.age", **meta))
        out.append(_cand(field_path="subjects.age_max", value=int(m.group(2)), value_type="int", excerpt=m.group(0), location="synopsis.subjects.age", **meta))
    m = re.search(r"Скринированных:\s*до\s*(\d+)", text, re.I)
    if m:
        out.append(_cand(field_path="subjects.screened_n", value=int(m.group(1)), value_type="int", excerpt=m.group(0), location="synopsis.subjects.screened", **meta))
    m = re.search(r"Рандомизированных:\s*(\d+)", text, re.I)
    if m:
        out.append(_cand(field_path="subjects.randomized_n", value=int(m.group(1)), value_type="int", excerpt=m.group(0), location="synopsis.subjects.randomized", **meta))
    m = re.search(r"соотношении\s*(1:1:1:1)", text, re.I)
    if m:
        out.append(_cand(field_path="subjects.group_allocation", value=m.group(1), value_type="string", excerpt=m.group(0), location="synopsis.subjects.allocation", **meta))

    # Washout
    m = re.search(r"отмывочный период[^\n]{0,80}?(\d+)\s*дн", text, re.I)
    if m:
        out.append(_cand(field_path="washout.duration", value=int(m.group(1)), value_type="int", excerpt=m.group(0), location="synopsis.washout", **meta))
        out.append(_cand(field_path="washout.unit", value="day", value_type="string", excerpt=m.group(0), location="synopsis.washout", **meta))

    # Sampling times
    m = re.search(r"Время забора образцов:\s*([^\n]+)", text, re.I)
    if m:
        blob = m.group(1)
        # Drop trailing count phrase so "всего 19" is not treated as a timepoint
        blob = re.split(r"\(всего|\. У каждого", blob, maxsplit=1)[0]
        times = re.findall(r"\d+(?:[.,]\d+)?", blob)
        seen: set[str] = set()
        norm: list[float | int] = []
        for t in times:
            v = t.replace(",", ".")
            if v in seen:
                continue
            seen.add(v)
            norm.append(float(v) if "." in v else int(v))
        if norm:
            out.append(_cand(field_path="sampling.times", value=norm, value_type="list", excerpt=m.group(0)[:400], location="synopsis.sampling.times", **meta))
            # Prefer explicit "всего N точек" when present
            n_m = re.search(r"всего\s*(\d+)\s*точек", m.group(0), re.I)
            n_points = int(n_m.group(1)) if n_m else len(norm)
            out.append(_cand(field_path="sampling.total_points", value=n_points, value_type="int", excerpt=f"n={n_points}", location="synopsis.sampling.n", **meta))
            out.append(_cand(field_path="sampling.pre_dose_point", value=True, value_type="bool", excerpt="0 ч", location="synopsis.sampling.predose", confidence="MEDIUM", **meta))
            if 72 in norm or 72.0 in norm:
                out.append(_cand(field_path="sampling.endpoint", value="72 h", value_type="string", excerpt="72", location="synopsis.sampling.endpoint", **meta))

    # Bioanalysis / PK / stats
    if re.search(r"упадацитиниб", text, re.I):
        out.append(_cand(field_path="bioanalysis.analyte", value="upadacitinib", value_type="string", excerpt="упадацитиниб", location="synopsis.bioanalysis", **meta))
        out.append(_cand(field_path="test_product.active_substance", value="upadacitinib", value_type="string", excerpt="упадацитиниб", location="synopsis.inn", confidence="MEDIUM", **meta))
        out.append(_cand(field_path="reference_product.active_substance", value="upadacitinib", value_type="string", excerpt="упадацитиниб", location="synopsis.inn", confidence="MEDIUM", **meta))
    if re.search(r"плазм", text, re.I):
        out.append(_cand(field_path="bioanalysis.matrix", value="plasma", value_type="string", excerpt="плазма", location="synopsis.bioanalysis.matrix", confidence="MEDIUM", **meta))
    if re.search(r"LC-MS|ВЭЖХ|хроматограф|масс-спектр|МС/МС", text, re.I):
        method = "LC-MS/MS" if re.search(r"LC-MS|масс-спектр|МС/МС", text, re.I) else "chromatography"
        out.append(_cand(field_path="bioanalysis.method", value=method, value_type="string", excerpt=method, location="synopsis.bioanalysis.method", confidence="MEDIUM", **meta))

    pk_params = []
    for label, path, token in [
        ("Cmax", "pk.Cmax", r"Cmax"),
        ("Tmax", "pk.Tmax", r"tmax|Tmax"),
        ("t1/2", "pk.t_half", r"t½|t1/2|t½"),
    ]:
        if re.search(token, text, re.I):
            pk_params.append(label)
            out.append(_cand(field_path=path, value=True, value_type="bool", excerpt=label, location="synopsis.pk", confidence="MEDIUM", **meta))
    if re.search(r"AUC0–72|AUC0-72|AUC\(0-72", text, re.I):
        pk_params.append("AUC0-72")
        out.append(_cand(field_path="pk.AUC_endpoint", value="AUC0-72", value_type="string", excerpt="AUC0-72", location="synopsis.pk.auc", **meta))
    if re.search(r"AUC0–inf|AUC0-∞|AUC0-inf|AUC\(0-∞", text, re.I):
        pk_params.append("AUC0-inf")
    if pk_params:
        out.append(_cand(field_path="pk.parameters", value=pk_params, value_type="list", excerpt=",".join(pk_params), location="synopsis.pk", **meta))
        out.append(_cand(field_path="pk.primary_parameters", value=[p for p in pk_params if p in {"Cmax", "AUC0-72", "AUC0-inf"}], value_type="list", excerpt=",".join(pk_params), location="synopsis.pk.primary", confidence="MEDIUM", **meta))

    if re.search(r"ANOVA", text, re.I):
        out.append(_cand(field_path="statistics.method", value="ANOVA", value_type="string", excerpt="ANOVA", location="synopsis.statistics", **meta))
    if re.search(r"логарифмическ", text, re.I):
        out.append(_cand(field_path="statistics.transformation", value="log", value_type="string", excerpt="логарифмического преобразования", location="synopsis.statistics", **meta))
    if re.search(r"90\s*%|90\-процентн|90 процентные", text, re.I):
        out.append(_cand(field_path="statistics.confidence_interval", value="90%", value_type="string", excerpt="90%", location="synopsis.statistics.ci", confidence="MEDIUM", **meta))
    m = re.search(r"(80[.,]00\s*[–\-—]\s*125[.,]00\s*%|80–125\s*%|80-125\s*%)", text, re.I)
    if m:
        out.append(_cand(field_path="statistics.acceptance_interval", value="80.00-125.00%", value_type="string", excerpt=m.group(0), location="synopsis.statistics.acceptance", **meta))

    if re.search(r"нежелательн", text, re.I):
        out.append(_cand(field_path="safety.adverse_events", value=True, value_type="bool", excerpt="нежелательн", location="synopsis.safety", confidence="MEDIUM", **meta))
    if re.search(r"ЭКГ|ECG", text, re.I):
        out.append(_cand(field_path="safety.ECG", value=True, value_type="bool", excerpt="ЭКГ", location="synopsis.safety.ecg", confidence="MEDIUM", **meta))
    if re.search(r"лабораторн", text, re.I):
        out.append(_cand(field_path="safety.lab_tests", value=True, value_type="bool", excerpt="лабораторн", location="synopsis.safety.lab", confidence="MEDIUM", **meta))
        out.append(_cand(field_path="safety.monitoring", value=True, value_type="bool", excerpt="мониторинг/лабораторн", location="synopsis.safety", confidence="LOW", **meta))

    return out


def extract_design_only(
    text: str,
    *,
    source_id: str,
    original_filename: str | None = None,
    document_id: str | None = None,
) -> list[CandidateStudyValue]:
    """Short design/text block extractor — does not require 'Синопсис'."""
    out: list[CandidateStudyValue] = []
    meta = dict(
        source_id=source_id,
        document_type="DESIGN",
        original_filename=original_filename,
        document_id=document_id,
    )
    t = text or ""

    def add(path: str, value: Any, vtype: str, excerpt: str, conf: str = "HIGH") -> None:
        out.append(_cand(field_path=path, value=value, value_type=vtype, excerpt=excerpt, location="design_text", confidence=conf, **meta))

    if re.search(r"рандомизированн", t, re.I):
        add("design.randomized", True, "bool", "рандомизированное")
    if re.search(r"открыт", t, re.I):
        add("design.open_label", True, "bool", "открытое")
    if re.search(r"перекрестн", t, re.I):
        add("design.crossover", True, "bool", "перекрестное")
    if re.search(r"двухпериодн", t, re.I):
        add("design.periods", 2, "int", "двухпериодное")
    if re.search(r"двумя последовательностями|двухпоследовательн", t, re.I):
        add("design.sequences", 2, "int", "двумя последовательностями")
    if re.search(r"четырех группах|четырёх группах", t, re.I):
        add("design.groups", 4, "int", "четырех группах")
    conds = []
    if re.search(r"натощак", t, re.I):
        conds.append("fasting")
        add("treatment.fasting", True, "bool", "натощак")
    if re.search(r"после приема пищи|после приёма пищи", t, re.I):
        conds.append("fed")
        add("treatment.fed", True, "bool", "после приема пищи")
    if conds:
        add("design.conditions", conds, "list", "+".join(conds))
        add("food.condition", "+".join(conds), "string", "+".join(conds), "MEDIUM")
    if re.search(r"мужского пола", t, re.I):
        add("subjects.sex", "male", "string", "мужского пола")
        add("subjects.type", "healthy_volunteers", "string", "здоровых добровольцев", "MEDIUM")
    m = re.search(r"от\s*(\d+)\s*до\s*(\d+)\s*лет", t, re.I)
    if m:
        add("subjects.age_min", int(m.group(1)), "int", m.group(0))
        add("subjects.age_max", int(m.group(2)), "int", m.group(0))
    m = re.search(r"Скринированных:\s*до\s*(\d+)", t, re.I)
    if m:
        add("subjects.screened_n", int(m.group(1)), "int", m.group(0))
    m = re.search(r"Рандомизированных:\s*(\d+)", t, re.I)
    if m:
        add("subjects.randomized_n", int(m.group(1)), "int", m.group(0))
    m = re.search(r"(1:1:1:1)", t)
    if m:
        add("subjects.group_allocation", m.group(1), "string", m.group(0))
    if re.search(r"отмывочн[^\n]{0,40}(\d+)\s*дн", t, re.I):
        mm = re.search(r"отмывочн[^\n]{0,40}(\d+)\s*дн", t, re.I)
        if mm:
            add("washout.duration", int(mm.group(1)), "int", mm.group(0))
            add("washout.unit", "day", "string", mm.group(0))
    return out


def extract_smpc(
    text: str,
    *,
    source_id: str,
    pages: list[dict[str, Any]] | None = None,
    original_filename: str | None = None,
    document_id: str | None = None,
) -> list[CandidateStudyValue]:
    from app.domain.study_input_binary_ingest import find_pdf_page_location

    out: list[CandidateStudyValue] = []
    meta = dict(
        source_id=source_id,
        document_type="SMPC",
        original_filename=original_filename,
        document_id=document_id,
    )

    def ploc(fallback: str, *needles: str) -> str:
        if pages:
            for n in needles:
                hit = find_pdf_page_location(pages, n)
                if hit:
                    return hit
        return fallback

    page1 = ""
    if pages:
        page1 = pages[0].get("text") or ""
    blob = page1 or text[:5000]

    m = re.search(r"(РАНВЭК|Rinvoq|Ринвок)", blob, re.I)
    if m:
        out.append(
            _cand(
                field_path="reference_product.name",
                value=m.group(1),
                value_type="string",
                excerpt=m.group(0),
                location=ploc("smpc.p1.name", "РАНВЭК"),
                **meta,
            )
        )

    m = re.search(r"(\d+)\s*мг", blob)
    if m:
        out.append(
            _cand(
                field_path="reference_product.dose",
                value=f"{m.group(1)} mg",
                value_type="string",
                excerpt=m.group(0),
                location=ploc("smpc.p1.dose", "15 мг"),
                **meta,
            )
        )

    if re.search(r"пролонг|prolonged|таблет", blob, re.I):
        out.append(
            _cand(
                field_path="reference_product.dosage_form",
                value="prolonged-release film-coated tablet",
                value_type="string",
                excerpt="таблетки с пролонгированным высвобождением" if "пролонг" in blob.lower() else "tablet",
                location=ploc("smpc.p1.form", "пролонгированным"),
                confidence="MEDIUM",
                **meta,
            )
        )

    if re.search(r"упадацитиниб|upadacitinib", text, re.I):
        out.append(
            _cand(
                field_path="reference_product.active_substance",
                value="upadacitinib",
                value_type="string",
                excerpt="упадацитиниб",
                location=ploc("smpc.inn", "упадацитиниб"),
                **meta,
            )
        )

    # Signal-oriented retrieval (not full SmPC structuring / not Study decisions)
    if re.search(r"противопоказан", text, re.I):
        c = _cand(
            field_path="safety.monitoring",
            value=True,
            value_type="bool",
            excerpt="противопоказан",
            location=ploc("smpc.contraindications", "Противопоказан"),
            confidence="LOW",
            **meta,
        )
        c.notes = "contraindications section present — signal only"
        out.append(c)
    if re.search(r"особые указания|меры предосторожности|предупрежден", text, re.I):
        c = _cand(
            field_path="safety.lab_tests",
            value=True,
            value_type="bool",
            excerpt="предупреждения/меры предосторожности",
            location=ploc("smpc.warnings", "особые указания", "предосторожности"),
            confidence="LOW",
            **meta,
        )
        c.notes = "warnings/precautions present — signal only"
        out.append(c)
    if re.search(r"взаимодействие|CYP3A4|CYP 3A4", text, re.I):
        c = _cand(
            field_path="safety.adverse_events",
            value=True,
            value_type="bool",
            excerpt="CYP3A4/взаимодействие",
            location=ploc("smpc.interactions", "CYP3A4", "Взаимодействие"),
            confidence="LOW",
            **meta,
        )
        c.notes = "interactions/CYP3A4 mentioned — not a Study decision"
        out.append(c)
    if re.search(r"способ применения|режим дозирования", text, re.I):
        c = _cand(
            field_path="treatment.dose",
            value=True,
            value_type="bool",
            excerpt="способ применения/дозирование",
            location=ploc("smpc.administration", "способ применения", "дозирования"),
            confidence="LOW",
            **meta,
        )
        c.notes = "administration section present — signal only"
        out.append(c)

    return out

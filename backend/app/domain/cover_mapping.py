"""Phase 30.3 — Typed cover (T01) mapping by explicit label → field path.

Never maps subject counts into dosage_form. Never uses ordinal/row index fill.
"""

from __future__ import annotations

import re
from typing import Any

from app.domain.semantic_field_types import FieldTypeError, coerce_typed

# Normalized label fragment → (field_key, type_name, ctx_path)
COVER_LABEL_RULES: tuple[tuple[str, str, str, str], ...] = (
    ("название исследования", "study_title", "string", "study.title"),
    ("идентификационный номер", "protocol_number", "string", "study.protocol_number"),
    ("номер протокола", "protocol_number", "string", "study.protocol_number"),
    ("версия протокола", "protocol_version", "string", "study.version"),
    ("дата версии", "protocol_date", "string", "study.version_date"),
    ("исследуемый препарат", "product_name", "string", "product.trade_name"),
    ("лекарственная форма", "dosage_form", "string", "product.dosage_form"),
    ("группировочное наименование", "inn", "string", "product.inn"),
    ("фаза исследования", "study_phase", "string", "study.phase"),
    ("спонсор", "sponsor", "string", "sponsor.name"),
)


def _norm(label: str) -> str:
    return (label or "").strip().lower().replace("ё", "е").replace("\n", " ")


def _dig(ctx: dict[str, Any], path: str) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def resolve_cover_value(label: str, study_ctx: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Return (field_key, display_value, error). value None = leave cell / no write."""
    norm = _norm(label)
    for frag, field_key, _type_name, path in COVER_LABEL_RULES:
        if frag in norm:
            raw = _dig(study_ctx, path)
            if field_key == "product_name" and not raw:
                raw = _dig(study_ctx, "product.inn")
            if field_key == "sponsor" and not raw:
                raw = _dig(study_ctx, "sponsor.legal_name")
            if field_key == "study_phase" and not raw:
                raw = "Биоэквивалентность"
            if field_key == "dosage_form":
                # Compose form + strength as string only — never subject counts
                form = _dig(study_ctx, "product.dosage_form")
                dose = _dig(study_ctx, "product.dosage")
                parts = [str(x).strip() for x in (form, dose) if x not in (None, "")]
                if not parts:
                    return field_key, None, "MISSING_DOSAGE_FORM"
                # Reject if someone stuffed an integer into dosage_form
                if isinstance(form, (int, float)) and not isinstance(form, bool):
                    return field_key, None, "TYPE_INCOMPATIBLE_DOSAGE_FORM"
                if isinstance(dose, (int, float)) and not isinstance(dose, bool):
                    return field_key, None, "TYPE_INCOMPATIBLE_DOSE_AS_NUMBER"
                try:
                    if form is not None:
                        coerce_typed("dosage_form", form, allow_empty=False)
                    if dose is not None:
                        coerce_typed("dose", dose, allow_empty=False)
                except FieldTypeError as exc:
                    return field_key, None, str(exc)
                return field_key, ", ".join(parts), None
            if field_key in {"protocol_number", "protocol_version", "protocol_date", "product_name", "inn", "study_title", "sponsor", "study_phase"}:
                try:
                    typed = coerce_typed(
                        {
                            "protocol_number": "product_name",
                            "study_title": "product_name",
                            "sponsor": "product_name",
                            "study_phase": "product_name",
                            "protocol_version": "protocol_version",
                            "protocol_date": "protocol_date",
                            "product_name": "product_name",
                            "inn": "inn",
                        }[field_key],
                        raw,
                        allow_empty=True,
                    )
                except FieldTypeError as exc:
                    return field_key, None, str(exc)
                if typed is None:
                    if field_key == "protocol_date":
                        return field_key, None, "MISSING_PROTOCOL_DATE"
                    return field_key, None, None
                return field_key, str(typed), None
            return field_key, str(raw) if raw is not None else None, None
    return None, None, None


def build_cover_rows(study_ctx: dict[str, Any]) -> list[list[str]]:
    """Semantic rows for COVER_METADATA (label, value) — Russian labels matching T01."""
    study = study_ctx.get("study") or {}
    product = study_ctx.get("product") or {}
    sponsor = study_ctx.get("sponsor") or {}
    form = product.get("dosage_form")
    dose = product.get("dosage")
    form_parts = [str(x).strip() for x in (form, dose) if x not in (None, "")]
    dosage_form_display = ", ".join(form_parts) if form_parts else ""
    return [
        ["Название исследования", str(study.get("title") or "")],
        ["Идентификационный номер", str(study.get("protocol_number") or "")],
        ["Версия протокола", str(study.get("version") or "")],
        ["Дата версии", str(study.get("version_date") or "")],
        ["Исследуемый препарат", str(product.get("trade_name") or product.get("inn") or "")],
        ["Лекарственная форма", dosage_form_display],
        ["Группировочное наименование", str(product.get("inn") or "")],
        ["Фаза исследования", str(study.get("phase") or "Биоэквивалентность")],
        [
            "Спонсор исследования",
            str(sponsor.get("name") or sponsor.get("legal_name") or ""),
        ],
    ]


_SUBJECT_COUNT_AS_FORM = re.compile(r"^\s*\d{1,4}\s*$")


def detect_wrong_cover_mapping(label: str, value: str) -> str | None:
    """Heuristic: subject count written into dosage_form cell."""
    norm = _norm(label)
    if "лекарственная форма" in norm and value and _SUBJECT_COUNT_AS_FORM.match(value):
        return "WRONG_MAPPING_DOSAGE_FORM_SUBJECT_COUNT"
    if "лекарственная форма" in norm and value and re.fullmatch(r"\d+", value.strip()):
        return "WRONG_MAPPING_DOSAGE_FORM_SUBJECT_COUNT"
    return None

"""Deterministic Product / ReferenceProduct → ProtocolTable row mapping.

Maps by semantic field keys; DOCX filler matches template labels (RU/EN),
never by row index alone.
"""

from __future__ import annotations

from typing import Any


# Template label aliases (normalized) → product field
PRODUCT_LABEL_ALIASES: dict[str, str] = {
    "название": "trade_name",
    "название:": "trade_name",
    "trade name": "trade_name",
    "trade_name": "trade_name",
    "производитель": "manufacturer",
    "производитель:": "manufacturer",
    "manufacturer": "manufacturer",
    "мнн": "inn",
    "мнн:": "inn",
    "inn": "inn",
    "лекарственная форма": "dosage_form",
    "лекарственная форма:": "dosage_form",
    "dosage form": "dosage_form",
    "dosage_form": "dosage_form",
    "дозировка": "dosage",
    "дозировка:": "dosage",
    "доза": "dosage",
    "dosage": "dosage",
    "состав": "composition",
    "состав:": "composition",
    "composition": "composition",
    "путь введения": "route",
    "route": "route",
    "страна": "manufacturer_country",
    "country": "manufacturer_country",
    "manufacturer_country": "manufacturer_country",
    "регистрация": "registration_number",
    "registration": "registration_number",
    "registration_number": "registration_number",
    "хранение": "storage_conditions",
    "storage": "storage_conditions",
    "storage_conditions": "storage_conditions",
    "срок годности": "shelf_life",
    "shelf life": "shelf_life",
    "shelf_life": "shelf_life",
    "серия": "batch",
    "batch": "batch",
    "статус закупки": "purchased_status",
    "purchased status": "purchased_status",
    "purchased_status": "purchased_status",
}


def normalize_label(label: str) -> str:
    return (label or "").strip().lower().replace("ё", "е").rstrip(":")


def field_for_label(label: str) -> str | None:
    return PRODUCT_LABEL_ALIASES.get(normalize_label(label))


def product_field_value(product: dict | None, field: str, *, display: bool = True) -> str:
    from app.domain.display_value_registry import resolve_display

    product = product or {}
    val = product.get(field)
    if val is None or val == "":
        placeholders = {
            "trade_name": "{{TEST_PRODUCT.TRADE_NAME}}",
            "inn": "{{TEST_PRODUCT.INN}}",
            "manufacturer": "{{TEST_PRODUCT.MANUFACTURER}}",
            "dosage": "{{TEST_PRODUCT.DOSAGE}}",
            "dosage_form": "{{TEST_PRODUCT.DOSAGE_FORM}}",
            "composition": "{{TEST_PRODUCT.COMPOSITION}}",
            "route": "{{TEST_PRODUCT.ROUTE}}",
            "manufacturer_country": "{{TEST_PRODUCT.COUNTRY}}",
            "registration_number": "{{TEST_PRODUCT.REGISTRATION}}",
            "storage_conditions": "{{TEST_PRODUCT.STORAGE}}",
            "shelf_life": "{{TEST_PRODUCT.SHELF_LIFE}}",
            "batch": "{{TEST_PRODUCT.BATCH}}",
            "purchased_status": "{{REFERENCE_PRODUCT.PURCHASED_STATUS}}",
        }
        return placeholders.get(field, "{{UNRESOLVED}}")
    if display and field == "purchased_status":
        return resolve_display(str(val), context="purchased_status", fallback=str(val))
    return str(val)


def reference_field_value(reference: dict | None, field: str, *, display: bool = True) -> str:
    from app.domain.display_value_registry import resolve_display

    reference = reference or {}
    val = reference.get(field)
    if val is None or val == "":
        placeholders = {
            "trade_name": "{{REFERENCE_PRODUCT.TRADE_NAME}}",
            "inn": "{{REFERENCE_PRODUCT.INN}}",
            "manufacturer": "{{REFERENCE_PRODUCT.MANUFACTURER}}",
            "dosage": "{{REFERENCE_PRODUCT.DOSAGE}}",
            "dosage_form": "{{REFERENCE_PRODUCT.DOSAGE_FORM}}",
            "composition": "{{REFERENCE_PRODUCT.COMPOSITION}}",
            "route": "{{REFERENCE_PRODUCT.ROUTE}}",
            "manufacturer_country": "{{REFERENCE_PRODUCT.COUNTRY}}",
            "registration_number": "{{REFERENCE_PRODUCT.REGISTRATION}}",
            "storage_conditions": "{{REFERENCE_PRODUCT.STORAGE}}",
            "shelf_life": "{{REFERENCE_PRODUCT.SHELF_LIFE}}",
            "batch": "{{REFERENCE_PRODUCT.BATCH}}",
            "purchased_status": "{{REFERENCE_PRODUCT.PURCHASED_STATUS}}",
        }
        return placeholders.get(field, "{{UNRESOLVED}}")
    if display and field == "purchased_status":
        return resolve_display(str(val), context="purchased_status", fallback=str(val))
    return str(val)


def build_test_product_rows(product: dict | None) -> list[list[Any]]:
    """Ordered semantic rows for ProtocolDraft (label key + value)."""
    p = product or {}
    return [
        ["Название", product_field_value(p, "trade_name")],
        ["Производитель", product_field_value(p, "manufacturer")],
        ["МНН", product_field_value(p, "inn")],
        ["Лекарственная форма", product_field_value(p, "dosage_form")],
        ["Дозировка", product_field_value(p, "dosage")],
        ["Состав", product_field_value(p, "composition")],
        ["Путь введения", product_field_value(p, "route")],
        ["Страна", product_field_value(p, "manufacturer_country")],
        ["Регистрация", product_field_value(p, "registration_number")],
        ["Хранение", product_field_value(p, "storage_conditions")],
        ["Срок годности", product_field_value(p, "shelf_life")],
        ["Серия", product_field_value(p, "batch")],
    ]


def build_reference_product_rows(reference: dict | None) -> list[list[Any]]:
    r = reference or {}
    return [
        ["Название", reference_field_value(r, "trade_name")],
        ["Производитель", reference_field_value(r, "manufacturer")],
        ["МНН", reference_field_value(r, "inn")],
        ["Лекарственная форма", reference_field_value(r, "dosage_form")],
        ["Дозировка", reference_field_value(r, "dosage")],
        ["Состав", reference_field_value(r, "composition")],
        ["Статус закупки", reference_field_value(r, "purchased_status")],
        ["Страна", reference_field_value(r, "manufacturer_country")],
        ["Регистрация", reference_field_value(r, "registration_number")],
        ["Хранение", reference_field_value(r, "storage_conditions")],
        ["Срок годности", reference_field_value(r, "shelf_life")],
        ["Серия", reference_field_value(r, "batch")],
    ]


def product_values_by_field(product: dict | None, *, is_reference: bool = False) -> dict[str, str]:
    rows = build_reference_product_rows(product) if is_reference else build_test_product_rows(product)
    out: dict[str, str] = {}
    for label, value in rows:
        field = field_for_label(str(label))
        if field:
            out[field] = str(value)
    return out

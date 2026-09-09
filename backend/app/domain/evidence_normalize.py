"""Deterministic value normalizers for evidence claims — no LLM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.domain.exceptions import ValidationError
from app.domain.units import normalize_unit, to_hours


@dataclass
class NormalizedValue:
    raw: str
    normalized: dict[str, Any]
    unit: str | None = None


_RANGE_RE = re.compile(
    r"(?P<a>\d+(?:[.,]\d+)?)\s*(?:–|-|—|to|до)\s*(?P<b>\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
_NUM_RE = re.compile(r"(?P<n>\d+(?:[.,]\d+)?)")
_UNIT_RE = re.compile(
    r"\b(?P<u>часов|часа|час|h|hr|hrs|min|мин|минут|minutes?|day|дней|дня|сут)\b",
    re.IGNORECASE,
)


def _to_float(s: str) -> float:
    return float(s.replace(",", "."))


def _detect_time_unit(text: str) -> str:
    m = _UNIT_RE.search(text)
    if not m:
        return "h"
    u = m.group("u").lower()
    if u.startswith("min") or u.startswith("мин"):
        return "min"
    if u.startswith("day") or u.startswith("д") or u.startswith("сут"):
        return "day"
    return "h"


def normalize_range_time(text: str, default_unit: str = "h") -> NormalizedValue:
    raw = text.strip()
    unit = _detect_time_unit(raw) if _UNIT_RE.search(raw) else default_unit
    m = _RANGE_RE.search(raw)
    if m:
        a, b = _to_float(m.group("a")), _to_float(m.group("b"))
        lo, hi = (a, b) if a <= b else (b, a)
        # store in canonical hours when unit known
        try:
            nu = normalize_unit(unit).value
            lo_h = to_hours(lo, nu)
            hi_h = to_hours(hi, nu)
            return NormalizedValue(
                raw=raw,
                normalized={"min": lo_h, "max": hi_h, "unit": "h", "original_unit": nu},
                unit="h",
            )
        except ValidationError:
            return NormalizedValue(raw=raw, normalized={"min": lo, "max": hi, "unit": unit}, unit=unit)
    m2 = _NUM_RE.search(raw)
    if not m2:
        raise ValidationError(f"Cannot normalize range from: {raw}", field="value")
    v = _to_float(m2.group("n"))
    try:
        nu = normalize_unit(unit).value
        vh = to_hours(v, nu)
        return NormalizedValue(
            raw=raw, normalized={"min": vh, "max": vh, "unit": "h", "original_unit": nu}, unit="h"
        )
    except ValidationError:
        return NormalizedValue(raw=raw, normalized={"min": v, "max": v, "unit": unit}, unit=unit)


def normalize_percent(text: str) -> NormalizedValue:
    raw = text.strip()
    m = _NUM_RE.search(raw)
    if not m:
        raise ValidationError(f"Cannot normalize percent from: {raw}", field="value")
    v = _to_float(m.group("n"))
    if "%" in raw or "percent" in raw.lower() or "процент" in raw.lower():
        return NormalizedValue(raw=raw, normalized={"value": v, "unit": "percent"}, unit="percent")
    if v <= 1.0:
        return NormalizedValue(
            raw=raw, normalized={"value": v * 100.0, "unit": "percent", "from": "fraction"}, unit="percent"
        )
    return NormalizedValue(raw=raw, normalized={"value": v, "unit": "percent"}, unit="percent")


def normalize_integer(text: str) -> NormalizedValue:
    raw = text.strip()
    m = _NUM_RE.search(raw)
    if not m:
        raise ValidationError(f"Cannot normalize integer from: {raw}", field="value")
    v = int(round(_to_float(m.group("n"))))
    return NormalizedValue(raw=raw, normalized={"value": v}, unit=None)


def normalize_food_condition(text: str) -> NormalizedValue:
    raw = text.strip()
    low = raw.lower()
    if any(k in low for k in ("fed", "после еды", "с пищей", "food")):
        val = "FED"
    elif any(k in low for k in ("fast", "натощак", "fasting")):
        val = "FASTING"
    else:
        val = raw.upper()
    return NormalizedValue(raw=raw, normalized={"value": val}, unit=None)


def normalize_claim_value(field_code: str, text: str) -> NormalizedValue:
    if field_code in {"tmax", "half_life"}:
        return normalize_range_time(text)
    if field_code in {"cv_cmax", "cv_auc"}:
        return normalize_percent(text)
    if field_code in {"study_n", "study_n_be_analysis"}:
        return normalize_integer(text)
    if field_code == "food_condition":
        return normalize_food_condition(text)
    # string fields
    return NormalizedValue(raw=text.strip(), normalized={"value": text.strip()}, unit=None)

"""Phase 30.3 — Explicit typed field validation for protocol DOCX mapping.

No positional/ordinal mapping. Type-incompatible values BLOCK.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable


class FieldTypeError(ValueError):
    def __init__(self, field: str, expected: str, value: Any, reason: str = ""):
        self.field = field
        self.expected = expected
        self.value = value
        self.reason = reason
        super().__init__(f"{field}: expected {expected}, got {value!r}" + (f" ({reason})" if reason else ""))


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def validate_string(field: str, value: Any, *, allow_empty: bool = False) -> str | None:
    if _is_blank(value):
        if allow_empty:
            return None
        raise FieldTypeError(field, "string", value, "missing")
    if isinstance(value, bool) or isinstance(value, (int, float)):
        # integers/floats must not silently become dosage_form / product strings
        raise FieldTypeError(field, "string", value, "numeric value not allowed for string field")
    text = str(value).strip()
    if not text and not allow_empty:
        raise FieldTypeError(field, "string", value, "empty")
    return text


_DOSE_RE = re.compile(
    r"^\s*\d+([.,]\d+)?\s*(mg|мг|µg|ug|мкг|g|г|ml|мл|%)\b",
    re.IGNORECASE,
)


def validate_dose(field: str, value: Any, *, allow_empty: bool = False) -> str | None:
    if _is_blank(value):
        if allow_empty:
            return None
        raise FieldTypeError(field, "Dose", value, "missing")
    if isinstance(value, bool):
        raise FieldTypeError(field, "Dose", value, "bool not allowed")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # bare number without unit is ambiguous — reject
        raise FieldTypeError(field, "Dose", value, "dose requires unit (e.g. '15 mg')")
    text = str(value).strip()
    if not _DOSE_RE.search(text):
        # allow already-composed phrases that include a dose token
        if not re.search(r"\d+\s*(mg|мг)\b", text, re.IGNORECASE):
            raise FieldTypeError(field, "Dose", value, "unrecognized dose pattern")
    return text


def validate_integer(field: str, value: Any, *, allow_empty: bool = False, min_value: int = 1) -> int | None:
    if _is_blank(value):
        if allow_empty:
            return None
        raise FieldTypeError(field, "integer", value, "missing")
    if isinstance(value, bool):
        raise FieldTypeError(field, "integer", value, "bool not allowed")
    if isinstance(value, float) and not value.is_integer():
        raise FieldTypeError(field, "integer", value, "non-integer float")
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise FieldTypeError(field, "integer", value, "not an integer") from exc
    if n < min_value:
        raise FieldTypeError(field, "integer", value, f"must be >= {min_value}")
    return n


_DURATION_RE = re.compile(
    r"^\s*\d+([.,]\d+)?\s*(day|days|дн|день|дня|дней|h|hr|hrs|час|часа|часов)\b",
    re.IGNORECASE,
)


def validate_duration(field: str, value: Any, *, allow_empty: bool = False) -> str | None:
    if _is_blank(value):
        if allow_empty:
            return None
        raise FieldTypeError(field, "duration", value, "missing")
    if isinstance(value, bool):
        raise FieldTypeError(field, "duration", value, "bool not allowed")
    if isinstance(value, (int, float)):
        # bare number without unit — caller must supply unit separately
        raise FieldTypeError(field, "duration", value, "duration requires unit")
    text = str(value).strip()
    if not _DURATION_RE.search(text) and not re.search(r"\d+", text):
        raise FieldTypeError(field, "duration", value, "unrecognized duration")
    return text


def validate_sampling_plan(field: str, value: Any, *, allow_empty: bool = False) -> list[dict[str, Any]] | None:
    if value is None or value == [] or value == {}:
        if allow_empty:
            return None
        raise FieldTypeError(field, "SamplingPlan", value, "missing")
    points = value
    if isinstance(value, dict):
        points = value.get("points") or []
    if not isinstance(points, list) or not points:
        if allow_empty:
            return None
        raise FieldTypeError(field, "SamplingPlan", value, "empty points")
    out: list[dict[str, Any]] = []
    for i, p in enumerate(points):
        if not isinstance(p, dict):
            raise FieldTypeError(field, "SamplingPlan", p, f"point[{i}] not an object")
        if p.get("time_h") is None and p.get("time") is None:
            raise FieldTypeError(field, "SamplingPlan", p, f"point[{i}] missing time_h")
        out.append(p)
    return out


VALIDATORS: dict[str, Callable[..., Any]] = {
    "string": validate_string,
    "Dose": validate_dose,
    "integer": validate_integer,
    "duration": validate_duration,
    "SamplingPlan": validate_sampling_plan,
}


# Canonical typed fields used by cover / product / subjects / washout / sampling
TYPED_FIELDS: dict[str, str] = {
    "dosage_form": "string",
    "dose": "Dose",
    "subject_count": "integer",
    "evaluable_target": "integer",
    "randomized_target": "integer",
    "screened_target": "integer",
    "washout": "duration",
    "sampling": "SamplingPlan",
    "observation_duration": "duration",
    "protocol_version": "string",
    "protocol_date": "string",
    "product_name": "string",
    "inn": "string",
}


@dataclass(frozen=True)
class TypedValue:
    field: str
    type_name: str
    value: Any


def coerce_typed(field: str, value: Any, *, allow_empty: bool = False) -> Any:
    type_name = TYPED_FIELDS.get(field)
    if not type_name:
        return value
    validator = VALIDATORS[type_name]
    return validator(field, value, allow_empty=allow_empty)


def assert_types_compatible(pairs: list[tuple[str, Any]], *, allow_empty: bool = False) -> list[str]:
    """Return list of type error messages (empty = ok)."""
    errors: list[str] = []
    for field, value in pairs:
        try:
            coerce_typed(field, value, allow_empty=allow_empty)
        except FieldTypeError as exc:
            errors.append(str(exc))
    return errors

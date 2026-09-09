"""Canonical time-unit conversion for PK/Sampling engines.

All calculation functions must use hours (or days when explicitly requested).
Do not mix minutes and hours inside math.
"""

from __future__ import annotations

from enum import StrEnum

from app.domain.exceptions import ValidationError


class TimeUnit(StrEnum):
    MIN = "min"
    H = "h"
    DAY = "day"


# Conversion factors relative to hours (canonical)
_TO_HOURS: dict[TimeUnit, float] = {
    TimeUnit.MIN: 1.0 / 60.0,
    TimeUnit.H: 1.0,
    TimeUnit.DAY: 24.0,
}

_FROM_HOURS: dict[TimeUnit, float] = {
    TimeUnit.MIN: 60.0,
    TimeUnit.H: 1.0,
    TimeUnit.DAY: 1.0 / 24.0,
}


def normalize_unit(unit: str | TimeUnit) -> TimeUnit:
    raw = str(unit).strip().lower()
    aliases = {
        "min": TimeUnit.MIN,
        "mins": TimeUnit.MIN,
        "minute": TimeUnit.MIN,
        "minutes": TimeUnit.MIN,
        "h": TimeUnit.H,
        "hr": TimeUnit.H,
        "hrs": TimeUnit.H,
        "hour": TimeUnit.H,
        "hours": TimeUnit.H,
        "d": TimeUnit.DAY,
        "day": TimeUnit.DAY,
        "days": TimeUnit.DAY,
    }
    if raw not in aliases:
        raise ValidationError(f"Unsupported time unit: {unit}", field="unit")
    return aliases[raw]


def to_hours(value: float, unit: str | TimeUnit) -> float:
    u = normalize_unit(unit)
    return float(value) * _TO_HOURS[u]


def from_hours(value_h: float, unit: str | TimeUnit) -> float:
    u = normalize_unit(unit)
    return float(value_h) * _FROM_HOURS[u]


def convert_time(value: float, from_unit: str | TimeUnit, to_unit: str | TimeUnit) -> float:
    return from_hours(to_hours(value, from_unit), to_unit)


def hours_to_min(value_h: float) -> float:
    return from_hours(value_h, TimeUnit.MIN)


def min_to_hours(value_min: float) -> float:
    return to_hours(value_min, TimeUnit.MIN)

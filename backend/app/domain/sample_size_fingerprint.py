"""Phase 15.4 — Deterministic calculation fingerprint."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def normalize_fingerprint_inputs(
    *,
    design: str,
    parameter: str | None,
    cv_value: float | None,
    expected_ratio: float | None,
    alpha: float | None,
    power: float | None,
    dropout_percent: float | None,
    method: str | None,
    calculation_version: str,
    be_lower: float | None = None,
    be_upper: float | None = None,
    inflation_method: str | None = None,
) -> dict[str, Any]:
    def _num(x: float | None) -> float | None:
        if x is None:
            return None
        return round(float(x), 12)

    return {
        "design": str(design),
        "parameter": parameter,
        "cv_value": _num(cv_value),
        "expected_ratio": _num(expected_ratio),
        "alpha": _num(alpha),
        "power": _num(power),
        "dropout_percent": _num(dropout_percent),
        "method": method,
        "calculation_version": calculation_version,
        "be_lower": _num(be_lower),
        "be_upper": _num(be_upper),
        "inflation_method": inflation_method,
    }


def calculation_fingerprint(payload: dict[str, Any]) -> str:
    """Same normalized inputs → same fingerprint; different → different."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def fingerprint_from_inputs(**kwargs: Any) -> str:
    return calculation_fingerprint(normalize_fingerprint_inputs(**kwargs))

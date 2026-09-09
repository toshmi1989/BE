"""Sample / package class separation — TEST & SYNTHETIC never count as REAL."""

from __future__ import annotations

SAMPLE_CLASSES = ("TEST", "SYNTHETIC", "REAL_BETA", "REAL", "REAL_PARTIAL")

# Origins that may increment real_full / real_partial counters
REAL_COUNTABLE = frozenset({"REAL", "REAL_PARTIAL", "REAL_BETA"})


def is_real_countable(origin: str | None) -> bool:
    return (origin or "") in REAL_COUNTABLE and (origin or "") not in {"TEST", "SYNTHETIC"}


def assert_not_counted_as_real(origin: str | None) -> dict[str, bool]:
    return {
        "origin": origin,
        "counts_as_real_full_or_partial": is_real_countable(origin) and origin != "TEST",
        "test_or_synthetic": (origin or "") in {"TEST", "SYNTHETIC"},
        "policy": "TEST and SYNTHETIC must never increment REAL package counters",
    }

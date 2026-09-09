"""Shared field provenance / verification status.

Domain statuses are defined here — not in React.
"""

from enum import StrEnum


class FieldStatus(StrEnum):
    MISSING = "MISSING"
    PROPOSED = "PROPOSED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    CALCULATED = "CALCULATED"
    DERIVED = "DERIVED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class DecisionStatus(StrEnum):
    PROPOSED = "PROPOSED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class Origin(StrEnum):
    USER = "USER"
    SOURCE_DERIVED = "SOURCE_DERIVED"
    CALCULATED = "CALCULATED"
    RULE_DERIVED = "RULE_DERIVED"
    AI_PROPOSED = "AI_PROPOSED"
    # Phase 1 compatibility alias
    EXPERT_ENTERED = "EXPERT_ENTERED"


TERMINAL_PROTECTED = frozenset({FieldStatus.VERIFIED, DecisionStatus.VERIFIED})
AI_ORIGINS = frozenset({Origin.AI_PROPOSED})


def normalize_origin(origin: Origin | str | None) -> str | None:
    if origin is None:
        return None
    value = Origin(origin)
    if value is Origin.EXPERT_ENTERED:
        return Origin.USER.value
    return value.value


def can_ai_overwrite(status: FieldStatus | DecisionStatus | str) -> bool:
    """AI must not directly overwrite VERIFIED data."""
    return str(status) not in {s.value for s in TERMINAL_PROTECTED} and str(status) != "VERIFIED"


def assert_ai_may_write(status: FieldStatus | DecisionStatus | str, origin: Origin | str | None) -> None:
    if origin is None:
        return
    normalized = normalize_origin(origin)
    if normalized in {o.value for o in AI_ORIGINS} and not can_ai_overwrite(status):
        raise ValueError("AI cannot overwrite VERIFIED data")

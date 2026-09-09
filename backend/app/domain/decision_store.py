"""In-memory Decision Center store — Phase 15.0."""

from __future__ import annotations

from typing import Any

from app.domain.decision_context import DecisionContext
from app.domain.decision_models import AnalogueStudyEvidence, ProtocolDecision

_DECISIONS: dict[str, ProtocolDecision] = {}  # decision_id → decision
_BY_STUDY: dict[str, list[str]] = {}  # study_key → decision ids
_CONTEXT: dict[str, DecisionContext] = {}
_ANALOGUES: dict[str, list[AnalogueStudyEvidence]] = {}


def clear_decision_store() -> None:
    _DECISIONS.clear()
    _BY_STUDY.clear()
    _CONTEXT.clear()
    _ANALOGUES.clear()


def _study_key(study_id: str | None, package_id: str | None = None) -> str:
    return str(study_id or package_id or "default")


def put_decisions(study_id: str | None, decisions: list[ProtocolDecision], *, package_id: str | None = None) -> None:
    key = _study_key(study_id, package_id)
    ids = []
    for d in decisions:
        _DECISIONS[d.id] = d
        ids.append(d.id)
    _BY_STUDY[key] = ids


def list_decisions(study_id: str | None, *, package_id: str | None = None) -> list[ProtocolDecision]:
    key = _study_key(study_id, package_id)
    return [_DECISIONS[i] for i in _BY_STUDY.get(key, []) if i in _DECISIONS]


def get_decision(decision_id: str) -> ProtocolDecision | None:
    return _DECISIONS.get(decision_id)


def put_context(study_id: str | None, ctx: DecisionContext, *, package_id: str | None = None) -> None:
    _CONTEXT[_study_key(study_id, package_id)] = ctx


def get_context(study_id: str | None, *, package_id: str | None = None) -> DecisionContext | None:
    return _CONTEXT.get(_study_key(study_id, package_id))


def add_analogue(study_id: str | None, analogue: AnalogueStudyEvidence) -> AnalogueStudyEvidence:
    key = _study_key(study_id)
    _ANALOGUES.setdefault(key, []).append(analogue)
    return analogue


def list_analogues(study_id: str | None) -> list[AnalogueStudyEvidence]:
    return list(_ANALOGUES.get(_study_key(study_id), []))


def decision_center_summary(study_id: str | None, *, package_id: str | None = None) -> dict[str, Any]:
    decisions = list_decisions(study_id, package_id=package_id)
    ctx = get_context(study_id, package_id=package_id)
    return {
        "study_id": study_id,
        "package_id": package_id,
        "fixture_id": ctx.fixture_id if ctx else None,
        "decisions": [d.to_dict(for_ui=True) for d in decisions],
        "open_conflicts": ctx.open_conflicts if ctx else [],
        "study_mutated": False,
        "recommended_is_not_approved": True,
    }

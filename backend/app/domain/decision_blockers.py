"""Shared blocker application helpers — Phase 15.1."""

from __future__ import annotations

from app.domain.decision_context import DecisionContext
from app.domain.decision_dependency import DecisionBlockerReport, is_decision_blocked
from app.domain.decision_models import ProtocolDecision


def apply_dependency_blockers(decision: ProtocolDecision, ctx: DecisionContext) -> DecisionBlockerReport:
    report = is_decision_blocked(decision.domain, ctx)
    decision.blocking_reasons = [b.to_dict() for b in report.blocking_reasons]
    decision.non_blocking_issues = [b.to_dict() for b in report.non_blocking_issues]
    decision.blocking_conflicts = [
        b.field_path for b in report.blocking_reasons if b.kind == "CONFLICT" and b.field_path
    ]
    return report

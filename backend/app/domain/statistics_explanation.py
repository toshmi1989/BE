"""Phase 15.5 — Explanation from stored StatisticsPlan data only."""

from __future__ import annotations

from app.domain.statistics_engine_classes import MODEL_LABELS, ROLE_LABELS_RU, TRANSFORM_LABELS
from app.domain.statistics_models import StatisticsPlan


def build_statistics_explanation(plan: StatisticsPlan) -> str:
    lines: list[str] = ["Statistical analysis plan", ""]
    if plan.design:
        lines.append(f"Design:\n{plan.design}")
        lines.append("")
    for p in plan.parameters:
        lines.append(f"Parameter:\n{p.parameter}")
        if p.original_wording and p.original_wording != p.parameter:
            lines.append(f"Source wording:\n{p.original_wording}")
        lines.append(f"Role:\n{ROLE_LABELS_RU.get(p.role, p.role)}")
        lines.append(f"Transformation:\n{TRANSFORM_LABELS.get(p.transformation, p.transformation)}")
        if p.model:
            lines.append(f"Model:\n{MODEL_LABELS.get(p.model, p.model)}")
        if p.estimate == "GEOMETRIC_MEAN_RATIO_TEST_REFERENCE":
            lines.append("Estimate:\nTest/Reference geometric mean ratio")
        if p.confidence_interval is not None:
            lines.append(f"Confidence level:\n{int(round(p.confidence_interval * 100))}%")
        if p.acceptance_interval:
            lo = p.acceptance_interval.lower_bound * 100
            hi = p.acceptance_interval.upper_bound * 100
            lines.append(f"Acceptance interval:\n{lo:.2f}–{hi:.2f}%")
            lines.append(f"Source:\n{p.acceptance_interval.source_role}")
        if p.summary_method:
            lines.append("Descriptive summary:\n" + ", ".join(p.summary_method))
        lines.append("")
    if plan.scenarios and len(plan.scenarios) > 1:
        lines.append("Multiple scenarios require expert selection:")
        for s in plan.scenarios:
            lines.append(f"- {s.label}: {', '.join(s.primary_parameters)}")
        lines.append("")
    if plan.blocking_reasons:
        lines.append("Blocking / review reasons:")
        for b in plan.blocking_reasons:
            lines.append(f"- {b}")
        lines.append("")
    lines.append("Note: Recommendation is not an approved StatisticsPlan.")
    lines.append("No observed GMR/CI fabricated (method plan only).")
    return "\n".join(lines)

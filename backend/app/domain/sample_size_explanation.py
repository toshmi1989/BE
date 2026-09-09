"""Phase 15.4 — Human-readable explanation from stored calculation data only."""

from __future__ import annotations

from typing import Any

from app.domain.sample_size_models import SampleSizeCalculationRecord


def build_explanation(rec: SampleSizeCalculationRecord) -> str:
    """Generate explanation from stored fields — never invent independent arithmetic."""
    lines: list[str] = ["Sample size calculation", ""]
    lines.append(f"Design:\n{rec.design}")
    lines.append("")
    if rec.parameter:
        lines.append(f"Parameter:\n{rec.parameter}")
        lines.append("")
    if rec.cv_value is not None:
        lines.append(f"CVintra:\n{rec.cv_value}{rec.cv_unit or '%'}")
        cv_src = next((i for i in rec.inputs if i.name == "cv_value"), None)
        if cv_src:
            label = cv_src.source_label or cv_src.source_kind
            claim = cv_src.source_claim_id or ""
            lines.append(f"Source:\n{label}" + (f" ({claim})" if claim else ""))
        lines.append("")
    if rec.expected_ratio is not None:
        lines.append(f"Expected ratio:\n{rec.expected_ratio}")
        er = next((i for i in rec.inputs if i.name == "expected_ratio"), None)
        if er:
            lines.append(f"Source: {er.source_kind}")
        lines.append("")
    if rec.target_power is not None or rec.power is not None:
        p = rec.target_power if rec.target_power is not None else rec.power
        lines.append(f"Power:\n{int(round(float(p) * 100))}%" if p and p <= 1 else f"Power:\n{p}")
        lines.append("")
    if rec.alpha is not None:
        lines.append(f"Alpha:\n{rec.alpha}")
        lines.append("")
    if rec.required_n is not None:
        lines.append(f"Required evaluable subjects:\n{rec.required_n}")
        lines.append("")
    if rec.dropout_percent is not None:
        lines.append(f"Assumed dropout:\n{rec.dropout_percent}%")
        lines.append(f"Inflation method:\n{rec.inflation_method}")
        lines.append("")
    if rec.randomized_n is not None:
        lines.append(f"Planned randomized subjects:\n{rec.randomized_n}")
        lines.append("")
    if rec.achieved_power is not None:
        lines.append(f"Achieved power (rounded N):\n{rec.achieved_power:.6f}")
        lines.append("")
    method = rec.method or "unknown"
    ver = rec.algorithm_version or rec.calculation_version
    lines.append(f"Calculation method:\n{method} / {ver}")
    if rec.blocking_reasons:
        lines.append("")
        lines.append("Blocking reasons:")
        for b in rec.blocking_reasons:
            lines.append(f"- {b}")
    if rec.discrepancy:
        lines.append("")
        lines.append("Current protocol vs calculated:")
        lines.append(f"Current protocol: {rec.discrepancy.current_protocol_n}")
        lines.append(f"Calculated: {rec.discrepancy.calculated_randomized_n}")
        lines.append(f"Status: {rec.discrepancy.status}")
    lines.append("")
    lines.append("Note: Calculated N is not an approved protocol value.")
    return "\n".join(lines)


def explanation_dict(rec: SampleSizeCalculationRecord) -> dict[str, Any]:
    return {"text": build_explanation(rec), "from_stored_data": True, "ai_generated": False}

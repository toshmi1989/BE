"""Canonical SamplingPlan projection — single source for all protocol consumers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CanonicalSamplingPlan:
    points: list[dict[str, Any]]
    points_per_period: int
    observation_duration: float | None
    observation_unit: str
    analyte_coverage: list[str]
    rationale: str | None
    status: str | None
    plan_id: str | None = None
    reasons_display: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": list(self.points),
            "points_per_period": self.points_per_period,
            "observation_duration": self.observation_duration,
            "observation_unit": self.observation_unit,
            "analyte_coverage": list(self.analyte_coverage),
            "rationale": self.rationale,
            "status": self.status,
            "plan_id": self.plan_id,
            "reasons_display": list(self.reasons_display),
        }


def get_canonical_sampling_plan(ctx: dict) -> CanonicalSamplingPlan:
    """
    SamplingPlan is the only source of sampling points.

    Synopsis / 4.4.2 / tables / blood volume / procedures must read this helper
    (or SamplingPlan.points via ctx['sampling']), never invent parallel lists.
    """
    from app.domain.display_value_registry import resolve_display

    sampling = ctx.get("sampling") or {}
    observation = ctx.get("observation") or {}
    analytes = ctx.get("analytes") or []

    raw_points = list(sampling.get("points") or [])
    points: list[dict[str, Any]] = []
    reasons_display: list[dict[str, Any]] = []
    for p in raw_points:
        reason = p.get("reason")
        display_reason = resolve_display(reason, context="sampling_reason", fallback=str(reason or ""))
        entry = {
            "time_h": p.get("time_h"),
            "reason": reason,
            "reason_display": display_reason,
            "sequence_order": p.get("sequence_order"),
            "mandatory": p.get("mandatory"),
            "analyte_ids": list(p.get("analyte_ids") or []),
        }
        points.append(entry)
        reasons_display.append({"time_h": entry["time_h"], "reason_display": display_reason})

    points_per_period = sampling.get("total_points_per_period")
    if points_per_period is None:
        points_per_period = len(points)

    obs = observation.get("selected_duration") or observation.get("final_sampling_time")
    if obs is None:
        obs = sampling.get("final_observation_h")

    coverage = []
    for a in analytes:
        name = a.get("name")
        if name:
            coverage.append(str(name))
        elif a.get("id"):
            coverage.append(str(a["id"]))

    return CanonicalSamplingPlan(
        points=points,
        points_per_period=int(points_per_period or 0),
        observation_duration=float(obs) if obs is not None else None,
        observation_unit=str(
            observation.get("selected_unit") or observation.get("unit") or "h"
        ),
        analyte_coverage=coverage,
        rationale=sampling.get("rationale"),
        status=sampling.get("status"),
        plan_id=str(sampling["id"]) if sampling.get("id") else None,
        reasons_display=reasons_display,
    )

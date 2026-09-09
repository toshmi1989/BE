"""SafetyPlan + SafetyProcedureView — Phase 12A technical foundation.

Does not define clinical thresholds or invent monitoring batteries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.procedure_definition import ProcedureDefinition
from app.domain.procedure_schedule import ProcedureSchedule, compose_procedure_schedule


@dataclass
class SafetyPlan:
    physical_exam: dict[str, Any] | None = None
    vital_signs: dict[str, Any] | None = None
    ECG: dict[str, Any] | None = None
    laboratory_tests: dict[str, Any] | None = None
    AE: dict[str, Any] | None = None
    SAE: dict[str, Any] | None = None
    pregnancy: dict[str, Any] | None = None
    follow_up: dict[str, Any] | None = None
    safety_periods: list[dict[str, Any]] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    origin: str = "USER"
    status: str = "MISSING"
    notes: str | None = None
    # References to existing STATIC_VERIFIED template scale tables (not rewritten)
    static_verified_refs: list[str] = field(
        default_factory=lambda: ["SAFE.T13", "SAFE.T14", "SAFE.T15", "SAFE.T16"]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def enabled_categories(self) -> list[str]:
        keys = (
            "physical_exam",
            "vital_signs",
            "ECG",
            "laboratory_tests",
            "AE",
            "SAE",
            "pregnancy",
            "follow_up",
        )
        out: list[str] = []
        for k in keys:
            block = getattr(self, k)
            if block is True:
                out.append(k)
            elif isinstance(block, dict) and (
                block.get("enabled") is True or block.get("present") is True or bool(block.get("items"))
            ):
                out.append(k)
        return out


def safety_plan_from_dict(data: dict | None) -> SafetyPlan:
    data = data or {}
    known = {f.name for f in SafetyPlan.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in data.items() if k in known}
    return SafetyPlan(**kwargs)


def empty_safety_plan() -> SafetyPlan:
    return SafetyPlan(
        origin="UNRESOLVED",
        status="MISSING",
        notes="SafetyPlan empty — thresholds and batteries deferred pending expert interview",
    )


@dataclass
class SafetyProcedureView:
    """Assembles SafetyPlan + ProcedureSchedule safety-related rows only."""

    safety_plan: SafetyPlan
    procedures: list[ProcedureDefinition] = field(default_factory=list)
    schedule_status: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "safety_plan": self.safety_plan.to_dict(),
            "procedures": [p.to_dict() for p in self.procedures],
            "schedule_status": self.schedule_status,
            "enabled_categories": self.safety_plan.enabled_categories(),
            "notes": self.notes,
        }


def build_safety_procedure_view(ctx: dict, schedule: ProcedureSchedule | None = None) -> SafetyProcedureView:
    plan = safety_plan_from_dict(ctx.get("safety_plan"))
    sched = schedule or compose_procedure_schedule({**ctx, "safety_plan": plan.to_dict()})
    safety_cats = {
        "VITALS",
        "ECG",
        "LAB",
        "PHYSICAL_EXAM",
        "SAFETY",
        "FOLLOW_UP",
    }
    procs = [p for p in sched.procedures if p.category in safety_cats]
    return SafetyProcedureView(
        safety_plan=plan,
        procedures=procs,
        schedule_status=sched.status,
        notes="View only — no new clinical rules",
    )

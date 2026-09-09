"""ProcedureSchedule — deterministic composition from existing study plans.

Phase 12A: does NOT invent new medical procedures or clinical timings beyond
what Design / Food / Sampling / Observation / Washout / SubjectPlan / SafetyPlan
already provide.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.domain.canonical_sampling import get_canonical_sampling_plan
from app.domain.canonical_subjects import get_canonical_subject_counts
from app.domain.procedure_definition import ProcedureDefinition


@dataclass
class ProcedureSchedule:
    """Ordered schedule of ProcedureDefinition rows for a project."""

    project_id: str | None
    procedures: list[ProcedureDefinition] = field(default_factory=list)
    dependency_trace: list[dict[str, Any]] = field(default_factory=list)
    origin: str = "SOURCE_DERIVED"
    status: str = "PROPOSED"
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "procedures": [p.to_dict() for p in self.procedures],
            "dependency_trace": list(self.dependency_trace),
            "origin": self.origin,
            "status": self.status,
            "notes": self.notes,
            "count": len(self.procedures),
        }


def _trace(dep: str, produces: str, detail: str) -> dict[str, Any]:
    return {"dependency": dep, "produces": produces, "detail": detail}


def compose_procedure_schedule(ctx: dict) -> ProcedureSchedule:
    """Build schedule from canonical study context — structural only."""
    project_id = str(ctx.get("project_id") or "") or None
    procs: list[ProcedureDefinition] = []
    trace: list[dict[str, Any]] = []
    order = 0

    def add(proc: ProcedureDefinition) -> None:
        nonlocal order
        order += 10
        proc.sequence_order = order
        procs.append(proc)

    design = ctx.get("design") or {}
    food = ctx.get("food") or {}
    washout = ctx.get("washout") or {}
    observation = ctx.get("observation") or {}
    safety = ctx.get("safety_plan") or {}
    subjects_c = get_canonical_subject_counts(ctx)
    sampling_c = get_canonical_sampling_plan(ctx)

    design_type = str(design.get("type") or "")
    periods = int(design.get("periods") or 0) or (
        2 if "CROSSOVER" in design_type.upper() else 1 if design_type else 0
    )
    if design_type or periods:
        trace.append(
            _trace(
                "Design",
                "periods/sequences stages",
                f"type={design_type or 'unset'} periods={periods}",
            )
        )

    # Screening structural marker when subject plan exists
    if subjects_c.screened_n is not None or subjects_c.randomized_n is not None:
        add(
            ProcedureDefinition(
                code="SCREENING.VISIT",
                name="Screening visit",
                category="SCREENING",
                stage="SCREENING",
                mandatory=True,
                origin="SOURCE_DERIVED",
                status="PROPOSED",
                source_ids=[],
                notes="Structural marker from SubjectPlan presence — no clinical battery invented",
            )
        )
        trace.append(_trace("SubjectPlan", "SCREENING.VISIT", "subject counts present"))

    # Periods from Design
    period_list = list(range(1, periods + 1)) if periods else []
    for pnum in period_list:
        stage = f"PERIOD_{pnum}" if pnum <= 2 else "PERIOD_2"
        # Map period >2 to PERIOD_2 stage enum (only PERIOD_1/2 in catalog) — keep period field
        stage_code = "PERIOD_1" if pnum == 1 else "PERIOD_2"
        add(
            ProcedureDefinition(
                code=f"HOSP.PERIOD_{pnum}",
                name=f"Hospitalization / period {pnum}",
                category="HOSPITALIZATION",
                stage=stage_code,
                period=pnum,
                mandatory=True,
                origin="SOURCE_DERIVED",
                status="PROPOSED",
                notes="Structural period marker from Design — no procedure battery invented",
            )
        )
        add(
            ProcedureDefinition(
                code=f"DOSING.PERIOD_{pnum}",
                name=f"Dosing period {pnum}",
                category="DOSING",
                stage=stage_code,
                period=pnum,
                relative_time_min=0.0,
                mandatory=True,
                origin="SOURCE_DERIVED",
                status="PROPOSED",
                notes="Dosing time zero from Design period — meal/dose details from Food when present",
            )
        )

    # Food → meal procedure (condition only; no inventing calorie schedule)
    food_cond = food.get("condition") or design.get("food_condition")
    if food_cond and str(food_cond).upper() in {"FED", "FASTING_AND_FED"}:
        from app.domain.display_value_registry import resolve_display

        food_disp = resolve_display(str(food_cond).upper(), context="food")
        for pnum in period_list or [1]:
            stage_code = "PERIOD_1" if pnum == 1 else "PERIOD_2"
            add(
                ProcedureDefinition(
                    code=f"MEAL.PERIOD_{pnum}",
                    name=f"Meal ({food_disp})",
                    category="MEAL",
                    stage=stage_code,
                    period=pnum,
                    condition=str(food_cond),
                    mandatory=True,
                    origin="SOURCE_DERIVED",
                    status="PROPOSED",
                    notes="Meal presence from FoodCondition — timing/composition not invented",
                )
            )
        trace.append(_trace("Food", "MEAL procedures", f"condition={food_cond}"))
    elif food_cond and str(food_cond).upper() == "FASTING":
        trace.append(_trace("Food", "no MEAL procedures", "FASTING — meal procedures omitted"))

    # Sampling → blood collection procedures
    if sampling_c.points:
        from app.domain.display_value_registry import resolve_display

        for pnum in period_list or [1]:
            stage_code = "PERIOD_1" if pnum == 1 else "PERIOD_2"
            for pt in sampling_c.points:
                t_h = float(pt.get("time_h") or 0)
                reason = pt.get("reason") or pt.get("reason_code") or "POINT"
                reason_disp = resolve_display(str(reason), context="sampling_reason", fallback=str(reason))
                # Never leave raw enum tokens in display names
                if reason_disp == reason and str(reason).upper() in {
                    "BASELINE",
                    "TMAX_CAPTURE",
                    "FINAL",
                    "ABSORPTION",
                    "DISTRIBUTION",
                    "TERMINAL_PHASE",
                }:
                    reason_disp = str(reason).replace("_", " ").lower()
                add(
                    ProcedureDefinition(
                        code=f"SAMP.P{pnum}.T{t_h}",
                        name=f"Blood sampling t={t_h} h ({reason_disp})",
                        category="SAMPLING",
                        stage=stage_code,
                        period=pnum,
                        relative_time_min=t_h * 60.0,
                        mandatory=True,
                        origin="SOURCE_DERIVED",
                        status="PROPOSED",
                        source_ids=list(pt.get("source_ids") or [])
                        if isinstance(pt.get("source_ids"), list)
                        else [],
                        notes="From canonical SamplingPlan — no extra points invented",
                    )
                )
        trace.append(
            _trace(
                "Sampling",
                "SAMPLING procedures",
                f"points_per_period={sampling_c.points_per_period}",
            )
        )

    # Observation → end of observation marker
    obs_dur = observation.get("selected_duration") or observation.get("final_sampling_time")
    obs_unit = observation.get("unit") or observation.get("selected_unit") or "h"
    if obs_dur is not None:
        for pnum in period_list or [1]:
            stage_code = "PERIOD_1" if pnum == 1 else "PERIOD_2"
            rel_min = float(obs_dur) * 60.0 if str(obs_unit).lower().startswith("h") else float(obs_dur)
            add(
                ProcedureDefinition(
                    code=f"OBS.END.P{pnum}",
                    name=f"End of observation ({obs_dur} {obs_unit})",
                    category="OTHER",
                    stage=stage_code,
                    period=pnum,
                    relative_time_min=rel_min,
                    mandatory=True,
                    origin="SOURCE_DERIVED",
                    status="PROPOSED",
                    notes="From ObservationPlan — not a clinical exam battery",
                )
            )
        trace.append(_trace("Observation", "OBS.END", f"duration={obs_dur} {obs_unit}"))

    # Washout → period transition
    requires_wo = washout.get("requires_washout")
    wo_val = washout.get("selected_value")
    if requires_wo or (wo_val is not None and periods >= 2):
        add(
            ProcedureDefinition(
                code="WASHOUT.INTERVAL",
                name=f"Washout interval ({wo_val} {washout.get('unit') or 'day'})"
                if wo_val is not None
                else "Washout interval",
                category="WASHOUT",
                stage="WASHOUT",
                mandatory=True,
                origin="SOURCE_DERIVED",
                status="PROPOSED",
                notes="From WashoutPlan — no additional washout procedures invented",
            )
        )
        trace.append(_trace("Washout", "WASHOUT.INTERVAL", f"value={wo_val}"))

    # SafetyPlan → only categories explicitly marked present (no thresholds)
    for key, category, code_suffix, name in (
        ("physical_exam", "PHYSICAL_EXAM", "PHYS", "Physical examination"),
        ("vital_signs", "VITALS", "VITALS", "Vital signs"),
        ("ECG", "ECG", "ECG", "ECG"),
        ("laboratory_tests", "LAB", "LAB", "Safety laboratory tests"),
        ("AE", "SAFETY", "AE", "Adverse event monitoring"),
        ("SAE", "SAFETY", "SAE", "Serious adverse event monitoring"),
        ("pregnancy", "SAFETY", "PREG", "Pregnancy monitoring"),
        ("follow_up", "FOLLOW_UP", "FU", "Safety follow-up"),
    ):
        block = safety.get(key)
        if not block:
            continue
        # Accept truthy flag or non-empty dict with enabled/present
        enabled = block is True or (
            isinstance(block, dict)
            and (block.get("enabled") is True or block.get("present") is True or bool(block.get("items")))
        )
        if not enabled:
            continue
        stage = "FOLLOW_UP" if key == "follow_up" else "PERIOD_1"
        add(
            ProcedureDefinition(
                code=f"SAFETY.{code_suffix}",
                name=name,
                category=category,
                stage=stage,
                mandatory=bool(isinstance(block, dict) and block.get("mandatory", True)),
                origin="SOURCE_DERIVED",
                status="PROPOSED",
                source_ids=list(block.get("source_ids") or [])
                if isinstance(block, dict) and isinstance(block.get("source_ids"), list)
                else [],
                notes="From SafetyPlan flag — no clinical thresholds invented",
            )
        )
    if safety:
        trace.append(_trace("SafetyPlan", "SAFETY procedures", "explicitly enabled categories only"))

    # Final visit structural marker
    if subjects_c.randomized_n is not None or period_list:
        add(
            ProcedureDefinition(
                code="FINAL.VISIT",
                name="Final / end-of-study visit",
                category="FINAL",
                stage="FINAL",
                mandatory=True,
                origin="SOURCE_DERIVED",
                status="PROPOSED",
                notes="Structural final marker — exam battery not invented",
            )
        )

    status = "PROPOSED" if procs else "UNRESOLVED"
    return ProcedureSchedule(
        project_id=project_id,
        procedures=procs,
        dependency_trace=trace,
        origin="SOURCE_DERIVED",
        status=status,
        notes="Deterministic composition — no unverified medical rules applied",
    )


# Dependency graph documentation (for tests / matrix)
PROCEDURE_DEPENDENCY_GRAPH: dict[str, list[str]] = {
    "Design": ["periods", "sequences", "HOSPITALIZATION", "DOSING"],
    "Food": ["MEAL"],
    "Sampling": ["SAMPLING"],
    "Observation": ["OBS.END"],
    "Washout": ["WASHOUT"],
    "SubjectPlan": ["SCREENING.VISIT", "FINAL.VISIT"],
    "SafetyPlan": ["PHYSICAL_EXAM", "VITALS", "ECG", "LAB", "SAFETY", "FOLLOW_UP"],
}

"""ProcedureEvent + ProcedureDependency — Phase 12A.2 technical model.

No invented medical timings. relative_time only from canonical/source/decision.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4

from app.domain.content_foundation_v2 import DEPENDENCY_TYPES, TIME_ANCHORS
from app.domain.procedure_definition import ProcedureDefinition
from app.domain.procedure_schedule import ProcedureSchedule, PROCEDURE_DEPENDENCY_GRAPH


@dataclass
class ProcedureEvent:
    procedure_definition_code: str
    time_anchor: str = "OTHER"
    id: str | None = None
    study_period: int | None = None
    relative_time: float | None = None  # minutes; only if sourced
    absolute_time: str | None = None
    condition: str | None = None
    order: int = 0
    required: bool = True
    source_ids: list[str] = field(default_factory=list)
    evidence_claim_ids: list[str] = field(default_factory=list)
    status: str = "PROPOSED"
    expert_decision_id: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = str(uuid4())
        if self.time_anchor not in TIME_ANCHORS:
            raise ValueError(f"Invalid time_anchor: {self.time_anchor}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProcedureDependency:
    from_procedure: str
    to_procedure: str
    dependency_type: str = "PRECEDES"
    reason: str = ""
    source_ids: list[str] = field(default_factory=list)
    evidence_claim_ids: list[str] = field(default_factory=list)
    status: str = "PROPOSED"
    id: str | None = None

    def __post_init__(self) -> None:
        if self.id is None:
            self.id = str(uuid4())
        if self.dependency_type not in DEPENDENCY_TYPES:
            raise ValueError(f"Invalid dependency_type: {self.dependency_type}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def events_from_schedule(schedule: ProcedureSchedule) -> list[ProcedureEvent]:
    """Project ProcedureDefinition rows into ProcedureEvent (structural)."""
    events: list[ProcedureEvent] = []
    for p in schedule.procedures:
        anchor = _infer_anchor(p)
        events.append(
            ProcedureEvent(
                procedure_definition_code=p.code,
                time_anchor=anchor,
                study_period=p.period,
                relative_time=p.relative_time_min,
                condition=p.condition,
                order=p.sequence_order,
                required=p.mandatory,
                source_ids=list(p.source_ids or []),
                status=p.status,
                notes=p.notes,
            )
        )
    return events


def _infer_anchor(p: ProcedureDefinition) -> str:
    cat = (p.category or "").upper()
    code = (p.code or "").upper()
    if cat == "SCREENING" or "SCREENING" in code:
        return "SCREENING"
    if cat in {"DOSING"} or code.startswith("DOSING"):
        return "DOSE"
    if cat in {"SAMPLING", "BLOOD_SAMPLING"}:
        return "SAMPLING"
    if cat in {"FOLLOW_UP"}:
        return "FOLLOW_UP"
    if cat in {"FINAL", "DISCHARGE"}:
        return "DISCHARGE"
    if cat in {"HOSPITALIZATION", "ADMISSION"}:
        return "ADMISSION"
    if p.relative_time_min is not None and p.relative_time_min < 0:
        return "PRE_DOSE"
    if p.relative_time_min is not None and p.relative_time_min > 0:
        return "POST_DOSE"
    return "OTHER"


def structural_dependencies() -> list[ProcedureDependency]:
    """Technical dependency edges from PROCEDURE_DEPENDENCY_GRAPH (not clinical)."""
    deps: list[ProcedureDependency] = []
    # Core procedural chain (technical, not medical)
    chains = [
        ("ADMISSION", "FASTING", "PRECEDES", "Structural admission before fasting marker"),
        ("FASTING", "DOSING", "PRECEDES", "Structural fasting before dose when fasting study"),
        ("DOSING", "BLOOD_SAMPLING", "PRECEDES", "Sampling follows dosing time-zero"),
        ("DOSING", "SAMPLING", "PRECEDES", "Sampling follows dosing time-zero"),
        ("BLOOD_SAMPLING", "SAMPLE_PROCESSING", "PRECEDES", "Processing after collection"),
        ("SAMPLE_PROCESSING", "BIOANALYSIS", "PRECEDES", "Bioanalysis after processing"),
        ("ADMISSION", "DOSING", "PRECEDES", "Admission precedes dosing"),
    ]
    for a, b, t, reason in chains:
        deps.append(
            ProcedureDependency(
                from_procedure=a,
                to_procedure=b,
                dependency_type=t,
                reason=reason,
                status="PROPOSED",
            )
        )
    for src, targets in PROCEDURE_DEPENDENCY_GRAPH.items():
        for tgt in targets:
            deps.append(
                ProcedureDependency(
                    from_procedure=src,
                    to_procedure=tgt,
                    dependency_type="REQUIRES",
                    reason=f"Schedule composition dependency: {src} → {tgt}",
                    status="PROPOSED",
                )
            )
    return deps


def validate_schedule_events(events: list[ProcedureEvent]) -> list[dict[str, Any]]:
    """Structural validation — inventing times without source is an issue."""
    issues: list[dict[str, Any]] = []
    for e in events:
        if e.relative_time is not None and not e.source_ids and not e.evidence_claim_ids:
            # Canonical-derived times (sampling) may have empty source_ids — warn only if notes missing
            if not (e.notes and ("canonical" in e.notes.lower() or "sampling" in e.notes.lower() or "from" in e.notes.lower())):
                issues.append(
                    {
                        "code": "CONTENT.MISSING_SOURCE",
                        "severity": "WARNING",
                        "message": f"Event {e.procedure_definition_code} has relative_time without source/evidence",
                        "blocking": False,
                    }
                )
    return issues

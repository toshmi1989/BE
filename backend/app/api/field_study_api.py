"""Phase 19/20 — Field study & real-package APIs."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domain.conflict_benchmark import conflict_benchmark_summary
from app.domain.field_study import (
    CRITICAL_EXTRACTION_FIELDS,
    FIELD_EVENTS,
    PROTOCOL_CORRECTION_CATEGORIES,
    PROTOCOL_DOMAINS,
    add_conflict_writer_label,
    add_feedback,
    add_protocol_correction,
    add_research_review,
    aggregate_timing_metrics,
    assert_no_auto_medical,
    bump_ops,
    classify_evidence,
    classify_field,
    classify_provenance,
    complete_case,
    create_paired_study,
    decision_workload_summary,
    evidence_summary,
    extraction_classification_summary,
    get_session,
    list_events,
    list_pairs,
    list_sessions,
    log_event,
    production_readiness,
    protocol_quality_summary,
    record_decision_latency,
    record_pair_timings,
    record_timings,
    research_summary,
    set_complexity,
    set_conflict_labels,
    set_docx_review,
    set_engine_review,
    set_protocol_domain,
    start_case,
)
from app.domain.field_study_intake import (
    INTAKE_STATES,
    assign_writer,
    bootstrap_from_registry,
    create_intake_case,
    get_intake_case,
    list_intake_cases,
    mark_ready_for_session,
    set_document_inventory,
    submit_sanitization_review,
    transition_state,
)
from app.domain.beta_entry_gate import (
    beta_gate_checks,
    evaluate_entry_criteria,
    save_gate_runtime_state,
    select_beta_cases,
)
from app.domain.controlled_beta import (
    beta_readiness_message,
    export_field_study,
    intake_slots_dashboard,
    session_start_gate,
    start_timed_session,
    stop_timed_session,
    writer_session_dashboard,
)
from app.domain.field_study_status import data_quality_check, field_study_status
from app.domain.real_package_registry import REPO_ROOT
from app.domain.population_gap import investigate_population_gap
from app.domain.real_package_registry import (
    diversity_report,
    field_study_intake_manifest,
    list_real_packages,
    population_status,
    validate_intake_filenames,
)

router = APIRouter(prefix="/field-study", tags=["field-study"])


class StartIn(BaseModel):
    case_id: str
    writer_id: str = Field(description="Pseudonymous writer id")
    system_used: bool
    mode: str = "MANUAL"
    session_type: str | None = None
    case_order: int | None = None
    pair_id: str | None = None


class PairIn(BaseModel):
    case_id: str
    writer_id: str = Field(description="Pseudonymous writer id")
    case_order: int | None = None


class TimingIn(BaseModel):
    T_manual_minutes: float | None = None
    T_system_minutes: float | None = None
    T_review_minutes: float | None = None
    observed_directly: bool = True


class PairTimingIn(BaseModel):
    manual_total_minutes: float
    system_total_minutes: float
    review_minutes: float
    observed_directly: bool = True


class EventIn(BaseModel):
    event: str
    stage: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class OpsIn(BaseModel):
    manual_edits: int = 0
    expert_decisions: int = 0
    evidence_opens: int = 0
    research_queries: int = 0
    document_switches: int = 0
    conflicts: int = 0
    gaps: int = 0
    preflight_warnings: int = 0
    preflight_blockers: int = 0
    recommendations: int = 0
    approved_decisions: int = 0
    rejected_decisions: int = 0
    modified_decisions: int = 0
    unresolved_decisions: int = 0


class ClassifyIn(BaseModel):
    field: str
    classification: str


class EvidenceIn(BaseModel):
    field: str
    judgement: str


class ResearchIn(BaseModel):
    question: str
    judgement: str
    why_needed: str | None = None


class ConflictLabelIn(BaseModel):
    expected: list[str]
    detected: list[str] = Field(default_factory=list)


class ComplexityIn(BaseModel):
    level: str
    rationale: str


class EngineReviewIn(BaseModel):
    sample_size: str | None = None
    statistics: str | None = None


class ProtocolDomainIn(BaseModel):
    domain: str
    classification: str


class FeedbackIn(BaseModel):
    answers: dict[str, str]


class IntakeValidateIn(BaseModel):
    filenames: list[str]


class IntakeCreateIn(BaseModel):
    case_id: str
    source_origin: str
    origin: str = "REAL"
    study_pattern: list[str] = Field(default_factory=list)
    filenames: list[str] = Field(default_factory=list)
    document_inventory: dict[str, str] | None = None


class InventoryIn(BaseModel):
    document_inventory: dict[str, str]


class SanitizationIn(BaseModel):
    sanitized: bool
    notes: str | None = None


class AssignWriterIn(BaseModel):
    writer_id: str


class StateIn(BaseModel):
    state: str


class ProvenanceIn(BaseModel):
    field: str
    status: str


class ConflictWriterIn(BaseModel):
    label: str
    conflict_type: str


class ProtocolCorrectionIn(BaseModel):
    category: str
    note: str | None = None


class DocxReviewIn(BaseModel):
    status: str
    corrected: bool = False


class DecisionLatencyIn(BaseModel):
    recommendation_at: str
    decision_at: str
    outcome: str


@router.get("/status")
def status() -> dict[str, Any]:
    return field_study_status()


@router.get("/beta-readiness")
def beta_ready() -> dict[str, Any]:
    msg = beta_readiness_message()
    msg["entry_gate"] = evaluate_entry_criteria()
    return msg


@router.get("/beta-gate")
def beta_gate() -> dict[str, Any]:
    return beta_gate_checks()


@router.get("/activation/phase24")
def phase24_activation() -> dict[str, Any]:
    """Read honest Phase 24 activation artifacts if present."""
    act = REPO_ROOT / "fixtures" / "field_study" / "phase24_activation_result.json"
    pg = REPO_ROOT / "fixtures" / "field_study" / "phase24_postgres_evidence.json"
    out: dict[str, Any] = {"fabricated": False}
    if act.exists():
        out["activation"] = json.loads(act.read_text(encoding="utf-8-sig"))
    if pg.exists():
        out["postgres_evidence"] = json.loads(pg.read_text(encoding="utf-8-sig"))
    out["entry_gate"] = evaluate_entry_criteria()
    return out


@router.get("/beta-cases")
def beta_cases() -> dict[str, Any]:
    return select_beta_cases()


class GateStateIn(BaseModel):
    state: str
    note: str | None = None


@router.post("/beta-gate/state")
def set_beta_gate_state(payload: GateStateIn) -> dict[str, Any]:
    """Advance runtime state only when entry criteria allow (except forcing NOT_READY)."""
    entry = evaluate_entry_criteria()
    if payload.state != "BETA_NOT_READY" and not entry["entry_ready"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "entry_not_ready", "blockers": entry["blockers"]},
        )
    try:
        return save_gate_runtime_state(payload.state, note=payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/dashboard/intake")
def dash_intake() -> dict[str, Any]:
    return intake_slots_dashboard()


@router.get("/dashboard/sessions")
def dash_sessions() -> dict[str, Any]:
    return writer_session_dashboard()


@router.get("/export")
def export_fs(format: str = "json") -> dict[str, Any]:
    return export_field_study(format=format)


@router.post("/session-gate")
def gate_check(payload: dict[str, Any]) -> dict[str, Any]:
    return session_start_gate(str(payload.get("case_id") or ""), payload.get("writer_id"))


class TimedStartIn(BaseModel):
    case_id: str
    writer_id: str
    session_type: str
    pair_id: str | None = None


class TimedStopIn(BaseModel):
    review_minutes: float | None = None


@router.post("/sessions/timed/start")
def timed_start(payload: TimedStartIn) -> dict[str, Any]:
    try:
        out = start_timed_session(
            case_id=payload.case_id,
            writer_id=payload.writer_id,
            session_type=payload.session_type,
            pair_id=payload.pair_id,
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not out.get("ok"):
        raise HTTPException(status_code=400, detail=out.get("gate") or out)
    return out


@router.post("/sessions/{session_id}/timed/stop")
def timed_stop(session_id: str, payload: TimedStopIn | None = None) -> dict[str, Any]:
    try:
        return stop_timed_session(
            session_id,
            review_minutes=(payload.review_minutes if payload else None),
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/data-quality")
def dq() -> dict[str, Any]:
    return data_quality_check()


@router.get("/intake/cases")
def intake_cases() -> dict[str, Any]:
    bootstrap_from_registry()
    return {"states": list(INTAKE_STATES), "cases": list_intake_cases()}


@router.post("/intake/cases")
def intake_create(payload: IntakeCreateIn) -> dict[str, Any]:
    try:
        return create_intake_case(
            case_id=payload.case_id,
            source_origin=payload.source_origin,
            origin=payload.origin,
            study_pattern=payload.study_pattern,
            filenames=payload.filenames,
            document_inventory=payload.document_inventory,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/intake/cases/{case_id}")
def intake_get(case_id: str) -> dict[str, Any]:
    row = get_intake_case(case_id)
    if not row:
        bootstrap_from_registry()
        row = get_intake_case(case_id)
    if not row:
        raise HTTPException(status_code=404, detail="Intake case not found")
    return row


@router.post("/intake/cases/{case_id}/inventory")
def intake_inventory(case_id: str, payload: InventoryIn) -> dict[str, Any]:
    try:
        return set_document_inventory(case_id, payload.document_inventory)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Intake case not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/intake/cases/{case_id}/sanitization")
def intake_sanitize(case_id: str, payload: SanitizationIn) -> dict[str, Any]:
    try:
        return submit_sanitization_review(case_id, sanitized=payload.sanitized, notes=payload.notes)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Intake case not found") from e


@router.post("/intake/cases/{case_id}/assign-writer")
def intake_assign(case_id: str, payload: AssignWriterIn) -> dict[str, Any]:
    try:
        return assign_writer(case_id, payload.writer_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Intake case not found") from e


@router.post("/intake/cases/{case_id}/ready")
def intake_ready(case_id: str) -> dict[str, Any]:
    try:
        return mark_ready_for_session(case_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Intake case not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/intake/cases/{case_id}/state")
def intake_state(case_id: str, payload: StateIn) -> dict[str, Any]:
    try:
        return transition_state(case_id, payload.state)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Intake case not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/real-packages")
def real_packages() -> dict[str, Any]:
    return {
        "packages": list_real_packages(),
        "population": population_status(),
        "diversity": diversity_report(),
        "intake_manifest": field_study_intake_manifest(),
    }


@router.get("/population-status")
def pop_status() -> dict[str, Any]:
    return population_status()


@router.get("/population-gap")
def population_gap() -> dict[str, Any]:
    return investigate_population_gap()


@router.get("/conflict-benchmark")
def conflict_benchmark() -> dict[str, Any]:
    return conflict_benchmark_summary()


@router.get("/production-readiness")
def readiness() -> dict[str, Any]:
    return production_readiness()


@router.post("/intake/validate-filenames")
def intake_validate(payload: IntakeValidateIn) -> dict[str, Any]:
    return validate_intake_filenames(payload.filenames)


@router.get("/events/catalog")
def event_catalog() -> dict[str, Any]:
    return {
        "events": list(FIELD_EVENTS),
        "critical_extraction_fields": list(CRITICAL_EXTRACTION_FIELDS),
        "protocol_domains": list(PROTOCOL_DOMAINS),
    }


@router.post("/pairs")
def create_pair(payload: PairIn) -> dict[str, Any]:
    try:
        return create_paired_study(
            case_id=payload.case_id,
            writer_id=payload.writer_id,
            case_order=payload.case_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/pairs")
def pairs() -> dict[str, Any]:
    return {"pairs": list_pairs()}


@router.post("/pairs/{pair_id}/timings")
def pair_timings(pair_id: str, payload: PairTimingIn) -> dict[str, Any]:
    try:
        return record_pair_timings(
            pair_id,
            manual_total_minutes=payload.manual_total_minutes,
            system_total_minutes=payload.system_total_minutes,
            review_minutes=payload.review_minutes,
            observed_directly=payload.observed_directly,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Pair not found") from e


@router.post("/sessions")
def create_session(payload: StartIn) -> dict[str, Any]:
    try:
        return start_case(
            case_id=payload.case_id,
            writer_id=payload.writer_id,
            system_used=payload.system_used,
            mode=payload.mode,
            session_type=payload.session_type,
            case_order=payload.case_order,
            pair_id=payload.pair_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sessions")
def sessions() -> dict[str, Any]:
    return {"sessions": list_sessions()}


@router.get("/sessions/{session_id}")
def session(session_id: str) -> dict[str, Any]:
    row = get_session(session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    row["auto_medical_guards"] = assert_no_auto_medical(row)
    return row


@router.post("/sessions/{session_id}/events")
def post_event(session_id: str, payload: EventIn) -> dict[str, Any]:
    try:
        return log_event(session_id, payload.event, stage=payload.stage, meta=payload.meta)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="Session not found") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/sessions/{session_id}/events")
def get_events(session_id: str) -> dict[str, Any]:
    return {"events": list_events(session_id)}


@router.post("/sessions/{session_id}/timings")
def post_timings(session_id: str, payload: TimingIn) -> dict[str, Any]:
    if session_id not in {s["session_id"] for s in list_sessions()}:
        raise HTTPException(status_code=404, detail="Session not found")
    return record_timings(
        session_id,
        T_manual_minutes=payload.T_manual_minutes,
        T_system_minutes=payload.T_system_minutes,
        T_review_minutes=payload.T_review_minutes,
        observed_directly=payload.observed_directly,
    )


@router.post("/sessions/{session_id}/ops")
def post_ops(session_id: str, payload: OpsIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return bump_ops(session_id, **payload.model_dump())


@router.post("/sessions/{session_id}/classify-field")
def post_classify(session_id: str, payload: ClassifyIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        classify_field(session_id, payload.field, payload.classification)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return get_session(session_id) or {}


@router.post("/sessions/{session_id}/evidence")
def post_evidence(session_id: str, payload: EvidenceIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        classify_evidence(session_id, payload.field, payload.judgement)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return get_session(session_id) or {}


@router.post("/sessions/{session_id}/provenance")
def post_provenance(session_id: str, payload: ProvenanceIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        classify_provenance(session_id, payload.field, payload.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return get_session(session_id) or {}


@router.post("/sessions/{session_id}/conflict-writer-label")
def post_conflict_writer(session_id: str, payload: ConflictWriterIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        add_conflict_writer_label(session_id, payload.label, payload.conflict_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return get_session(session_id) or {}


@router.post("/sessions/{session_id}/protocol-correction")
def post_protocol_correction(session_id: str, payload: ProtocolCorrectionIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        add_protocol_correction(session_id, payload.category, payload.note)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return get_session(session_id) or {}


@router.post("/sessions/{session_id}/docx-review")
def post_docx_review(session_id: str, payload: DocxReviewIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        set_docx_review(session_id, payload.status, corrected=payload.corrected)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return get_session(session_id) or {}


@router.post("/sessions/{session_id}/decision-latency")
def post_decision_latency(session_id: str, payload: DecisionLatencyIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        return record_decision_latency(
            session_id,
            recommendation_at=payload.recommendation_at,
            decision_at=payload.decision_at,
            outcome=payload.outcome,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sessions/{session_id}/research")
def post_research(session_id: str, payload: ResearchIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        return add_research_review(
            session_id,
            question=payload.question,
            judgement=payload.judgement,
            why_needed=payload.why_needed,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/sessions/{session_id}/conflict-labels")
def post_conflict_labels(session_id: str, payload: ConflictLabelIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return set_conflict_labels(session_id, expected=payload.expected, detected=payload.detected)


@router.post("/sessions/{session_id}/complexity")
def post_complexity(session_id: str, payload: ComplexityIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        set_complexity(session_id, payload.level, payload.rationale)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return get_session(session_id) or {}


@router.post("/sessions/{session_id}/engine-review")
def post_engine_review(session_id: str, payload: EngineReviewIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        set_engine_review(
            session_id,
            sample_size=payload.sample_size,
            statistics=payload.statistics,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return get_session(session_id) or {}


@router.post("/sessions/{session_id}/protocol-domain")
def post_protocol_domain(session_id: str, payload: ProtocolDomainIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        set_protocol_domain(session_id, payload.domain, payload.classification)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return get_session(session_id) or {}


@router.post("/sessions/{session_id}/feedback")
def post_feedback(session_id: str, payload: FeedbackIn) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return add_feedback(session_id, answers=payload.answers)


@router.post("/sessions/{session_id}/complete")
def post_complete(session_id: str) -> dict[str, Any]:
    if get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return complete_case(session_id)


@router.get("/metrics/timing")
def timing_metrics() -> dict[str, Any]:
    return aggregate_timing_metrics()


@router.get("/metrics/extraction")
def extraction_metrics(session_id: str | None = None) -> dict[str, Any]:
    return extraction_classification_summary(session_id)


@router.get("/metrics/evidence")
def evidence_metrics(session_id: str | None = None) -> dict[str, Any]:
    return evidence_summary(session_id)


@router.get("/metrics/research")
def research_metrics(session_id: str | None = None) -> dict[str, Any]:
    return research_summary(session_id)


@router.get("/metrics/decisions")
def decision_metrics(session_id: str | None = None) -> dict[str, Any]:
    return decision_workload_summary(session_id)


@router.get("/metrics/protocol")
def protocol_metrics(session_id: str | None = None) -> dict[str, Any]:
    return protocol_quality_summary(session_id)

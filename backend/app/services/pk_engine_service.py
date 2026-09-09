from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.blood_volume import BloodVolumeInput, calculate_blood_volume, calculate_sample_count
from app.domain.blood_volume import SampleCountInput
from app.domain.constants import ANALYTE_TYPES, PK_PARAMETER_CODES
from app.domain.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.observation import ObservationCalcInput, calculate_observation
from app.domain.sampling import (
    AnalyteTmaxWindow,
    SamplingRecommendInput,
    generate_sampling_recommendation,
    point_time_min,
    validate_sampling_plan,
)
from app.domain.units import normalize_unit, to_hours
from app.domain.washout import WashoutCalcInput, calculate_washout
from app.models import (
    Analyte,
    BloodVolumeCalculation,
    Design,
    ObservationPlan,
    PKParameter,
    Project,
    SamplingPlan,
    SamplingPoint,
    SubjectPlan,
    WashoutPlan,
)
from app.schemas.common import ProvenanceIn
from app.schemas.phase3 import (
    AnalyteCreate,
    AnalyteOut,
    AnalyteUpdate,
    BloodVolumeCalculateRequest,
    BloodVolumeOut,
    ObservationCalculateRequest,
    ObservationOut,
    PKParameterCreate,
    PKParameterOut,
    SamplingPatchRequest,
    SamplingPlanOut,
    SamplingPointOut,
    SamplingRecommendRequest,
    WashoutCalculateRequest,
    WashoutOut,
)
from app.services.provenance import apply_provenance, bump_entity_version, with_provenance


def _get_project(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", field="project_id")
    return project


def serialize_analyte(row: Analyte) -> AnalyteOut:
    return with_provenance(AnalyteOut, row)


def serialize_pk(row: PKParameter) -> PKParameterOut:
    return with_provenance(PKParameterOut, row)


def serialize_washout(row: WashoutPlan) -> WashoutOut:
    return with_provenance(WashoutOut, row)


def serialize_observation(row: ObservationPlan) -> ObservationOut:
    return with_provenance(ObservationOut, row)


def serialize_sampling_point(row: SamplingPoint) -> SamplingPointOut:
    return with_provenance(SamplingPointOut, row)


def serialize_sampling(plan: SamplingPlan) -> SamplingPlanOut:
    data = with_provenance(SamplingPlanOut, plan, points=[serialize_sampling_point(p) for p in plan.points])
    return data


def serialize_blood(row: BloodVolumeCalculation) -> BloodVolumeOut:
    return with_provenance(BloodVolumeOut, row)


def _validate_analyte_payload(
    *,
    analyte_type: str,
    tmax_min: float | None,
    tmax_max: float | None,
    tmax_unit: str,
    half_life_min: float | None,
    half_life_max: float | None,
    half_life_unit: str,
) -> None:
    if analyte_type not in ANALYTE_TYPES:
        raise ValidationError(f"Invalid analyte type: {analyte_type}", field="type")
    normalize_unit(tmax_unit)
    normalize_unit(half_life_unit)
    if tmax_min is not None and tmax_max is not None and tmax_min > tmax_max:
        raise ValidationError("tmax_min must be <= tmax_max", field="tmax_min")
    if half_life_min is not None and half_life_max is not None and half_life_min > half_life_max:
        raise ValidationError("half_life_min must be <= half_life_max", field="half_life_min")


def create_analyte(db: Session, project_id: UUID, payload: AnalyteCreate) -> AnalyteOut:
    _get_project(db, project_id)
    _validate_analyte_payload(
        analyte_type=payload.type,
        tmax_min=payload.tmax_min,
        tmax_max=payload.tmax_max,
        tmax_unit=payload.tmax_unit,
        half_life_min=payload.half_life_min,
        half_life_max=payload.half_life_max,
        half_life_unit=payload.half_life_unit,
    )
    row = Analyte(
        project_id=project_id,
        name=payload.name,
        type=payload.type,
        active=payload.active,
        matrix=payload.matrix,
        assay_method=payload.assay_method,
        lloq=payload.lloq,
        uloq=payload.uloq,
        tmax_min=payload.tmax_min,
        tmax_max=payload.tmax_max,
        tmax_unit=normalize_unit(payload.tmax_unit).value,
        half_life_min=payload.half_life_min,
        half_life_max=payload.half_life_max,
        half_life_unit=normalize_unit(payload.half_life_unit).value,
        pk_parameter_codes=payload.pk_parameter_codes or [],
    )
    apply_provenance(row, payload.provenance, creating=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_analyte(row)


def list_analytes(db: Session, project_id: UUID) -> list[AnalyteOut]:
    _get_project(db, project_id)
    rows = db.execute(select(Analyte).where(Analyte.project_id == project_id)).scalars().all()
    return [serialize_analyte(r) for r in rows]


def update_analyte(db: Session, project_id: UUID, analyte_id: UUID, payload: AnalyteUpdate) -> AnalyteOut:
    row = db.get(Analyte, analyte_id)
    if row is None or row.project_id != project_id:
        raise NotFoundError("Analyte not found", field="analyte_id")
    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    for key, value in data.items():
        if key in {"tmax_unit", "half_life_unit"} and value is not None:
            setattr(row, key, normalize_unit(value).value)
        else:
            setattr(row, key, value)
    _validate_analyte_payload(
        analyte_type=row.type,
        tmax_min=row.tmax_min,
        tmax_max=row.tmax_max,
        tmax_unit=row.tmax_unit,
        half_life_min=row.half_life_min,
        half_life_max=row.half_life_max,
        half_life_unit=row.half_life_unit,
    )
    apply_provenance(row, payload.provenance)
    bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return serialize_analyte(row)


def delete_analyte(db: Session, project_id: UUID, analyte_id: UUID) -> None:
    row = db.get(Analyte, analyte_id)
    if row is None or row.project_id != project_id:
        raise NotFoundError("Analyte not found", field="analyte_id")
    db.delete(row)
    db.commit()


def create_pk_parameter(db: Session, project_id: UUID, payload: PKParameterCreate) -> PKParameterOut:
    _get_project(db, project_id)
    analyte = db.get(Analyte, payload.analyte_id)
    if analyte is None or analyte.project_id != project_id:
        raise ConflictError("analyte_id must belong to project", field="analyte_id")
    if payload.parameter_code not in PK_PARAMETER_CODES:
        raise ValidationError(
            f"Unsupported parameter_code: {payload.parameter_code}",
            field="parameter_code",
            details={"allowed": list(PK_PARAMETER_CODES)},
        )
    if payload.unit:
        # Allow concentration units as free text; time-like codes must normalize
        if payload.parameter_code in {"Tmax", "T1_2"}:
            payload_unit = normalize_unit(payload.unit).value
        else:
            payload_unit = payload.unit
    else:
        payload_unit = None
    if (
        payload.range_min is not None
        and payload.range_max is not None
        and payload.range_min > payload.range_max
    ):
        raise ValidationError("range_min must be <= range_max", field="range_min")

    evidence = [e.model_dump() for e in (payload.evidence or [])]
    row = PKParameter(
        project_id=project_id,
        analyte_id=payload.analyte_id,
        parameter_code=payload.parameter_code,
        unit=payload_unit,
        value_numeric=payload.value_numeric,
        range_min=payload.range_min,
        range_max=payload.range_max,
        calculated_value=payload.calculated_value,
        reference_text=payload.reference_text,
        evidence=evidence,
    )
    apply_provenance(row, payload.provenance, creating=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_pk(row)


def list_pk_parameters(db: Session, project_id: UUID) -> list[PKParameterOut]:
    _get_project(db, project_id)
    rows = db.execute(select(PKParameter).where(PKParameter.project_id == project_id)).scalars().all()
    return [serialize_pk(r) for r in rows]


def _primary_analyte_half_life(analytes: list[Analyte]) -> tuple[float | None, float | None, str]:
    parents = [a for a in analytes if a.active and a.type == "PARENT"]
    pool = parents or [a for a in analytes if a.active] or analytes
    if not pool:
        return None, None, "h"
    a = pool[0]
    return a.half_life_min, a.half_life_max, a.half_life_unit


def _analyte_windows(analytes: list[Analyte]) -> list[AnalyteTmaxWindow]:
    windows: list[AnalyteTmaxWindow] = []
    for a in analytes:
        if not a.active:
            continue
        if a.tmax_min is None or a.tmax_max is None:
            continue
        windows.append(
            AnalyteTmaxWindow(
                analyte_id=str(a.id),
                name=a.name,
                tmax_min=a.tmax_min,
                tmax_max=a.tmax_max,
                tmax_unit=a.tmax_unit,
            )
        )
    return windows


def recommend_pk(db: Session, project_id: UUID, persist: bool = True) -> dict:
    """Create structured Tmax/T1_2 PK parameters from analytes (no LLM)."""
    _get_project(db, project_id)
    analytes = db.execute(select(Analyte).where(Analyte.project_id == project_id)).scalars().all()
    created: list[PKParameterOut] = []
    for a in analytes:
        if a.tmax_min is not None and a.tmax_max is not None:
            created.append(
                create_pk_parameter(
                    db,
                    project_id,
                    PKParameterCreate(
                        analyte_id=a.id,
                        parameter_code="Tmax",
                        unit=a.tmax_unit,
                        range_min=a.tmax_min,
                        range_max=a.tmax_max,
                        provenance=ProvenanceIn(origin="SOURCE_DERIVED", status="PROPOSED"),  # type: ignore[arg-type]
                    ),
                )
            )
        if a.half_life_min is not None and a.half_life_max is not None:
            created.append(
                create_pk_parameter(
                    db,
                    project_id,
                    PKParameterCreate(
                        analyte_id=a.id,
                        parameter_code="T1_2",
                        unit=a.half_life_unit,
                        range_min=a.half_life_min,
                        range_max=a.half_life_max,
                        provenance=ProvenanceIn(origin="SOURCE_DERIVED", status="PROPOSED"),  # type: ignore[arg-type]
                    ),
                )
            )
    return {"parameters": [c.model_dump(mode="json") for c in created], "count": len(created)}


def calculate_and_store_washout(
    db: Session, project_id: UUID, payload: WashoutCalculateRequest
) -> WashoutOut:
    project = _get_project(db, project_id)
    design = db.execute(select(Design).where(Design.project_id == project_id)).scalar_one_or_none()
    analytes = db.execute(select(Analyte).where(Analyte.project_id == project_id)).scalars().all()
    hl_min, hl_max, hl_unit = _primary_analyte_half_life(list(analytes))

    result = calculate_washout(
        WashoutCalcInput(
            half_life_min=hl_min,
            half_life_max=hl_max,
            half_life_unit=hl_unit,
            design_type=design.type if design else None,
            selected_value=payload.selected_value,
            selected_unit=payload.selected_unit,
            manual_override=payload.manual_override,
        )
    )
    if not payload.persist:
        # Still persist in Phase 3 API contract for reproducibility of aggregate
        pass

    row = db.execute(select(WashoutPlan).where(WashoutPlan.project_id == project_id)).scalar_one_or_none()
    creating = row is None
    if creating:
        row = WashoutPlan(project_id=project_id)
        apply_provenance(row, None, creating=True)
        db.add(row)
    row.calculated_minimum = result.calculated_minimum
    row.selected_value = result.selected_value
    row.unit = result.selected_unit if result.selected_value is not None else result.calculated_unit
    row.rule_id = result.rule_ids[0] if result.rule_ids else None
    row.rule_ids = result.rule_ids
    row.rationale = result.rationale
    row.manual_override = payload.manual_override
    row.requires_washout = result.requires_washout
    row.issues = result.critical_issues
    row.status = result.status
    row.origin = "CALCULATED"
    if not creating:
        bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return serialize_washout(row)


def get_washout(db: Session, project_id: UUID) -> WashoutOut:
    _get_project(db, project_id)
    row = db.execute(select(WashoutPlan).where(WashoutPlan.project_id == project_id)).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Washout plan not found", field="washout")
    return serialize_washout(row)


def calculate_and_store_observation(
    db: Session, project_id: UUID, payload: ObservationCalculateRequest
) -> ObservationOut:
    _get_project(db, project_id)
    analytes = db.execute(select(Analyte).where(Analyte.project_id == project_id)).scalars().all()
    hl_min, hl_max, hl_unit = _primary_analyte_half_life(list(analytes))
    result = calculate_observation(
        ObservationCalcInput(
            half_life_min=hl_min,
            half_life_max=hl_max,
            half_life_unit=hl_unit,
            selected_duration=payload.selected_duration,
            selected_unit=payload.selected_unit,
            manual_override=payload.manual_override,
        )
    )
    row = db.execute(
        select(ObservationPlan).where(ObservationPlan.project_id == project_id)
    ).scalar_one_or_none()
    creating = row is None
    if creating:
        row = ObservationPlan(project_id=project_id)
        apply_provenance(row, None, creating=True)
        db.add(row)
    row.calculated_minimum = result.calculated_minimum_h
    row.selected_duration = result.selected_duration_h
    row.unit = result.unit
    row.final_sampling_time = result.final_sampling_time_h
    row.rule_id = result.rule_ids[0] if result.rule_ids else None
    row.rule_ids = result.rule_ids
    row.rationale = result.rationale
    row.manual_override = payload.manual_override
    row.issues = result.issues
    row.status = result.status
    row.origin = "CALCULATED"
    if not creating:
        bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return serialize_observation(row)


def get_observation(db: Session, project_id: UUID) -> ObservationOut:
    _get_project(db, project_id)
    row = db.execute(
        select(ObservationPlan).where(ObservationPlan.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Observation plan not found", field="observation")
    return serialize_observation(row)


def _load_sampling(db: Session, project_id: UUID) -> SamplingPlan | None:
    return db.execute(
        select(SamplingPlan)
        .where(SamplingPlan.project_id == project_id)
        .options(selectinload(SamplingPlan.points))
    ).scalar_one_or_none()


def recommend_sampling(
    db: Session, project_id: UUID, payload: SamplingRecommendRequest
) -> SamplingPlanOut:
    _get_project(db, project_id)
    design = db.execute(select(Design).where(Design.project_id == project_id)).scalar_one_or_none()
    analytes = list(db.execute(select(Analyte).where(Analyte.project_id == project_id)).scalars().all())
    windows = _analyte_windows(analytes)
    if not windows:
        raise ValidationError("Active analytes with Tmax ranges required", field="analytes")

    obs = db.execute(
        select(ObservationPlan).where(ObservationPlan.project_id == project_id)
    ).scalar_one_or_none()
    obs_h = payload.observation_duration_h
    if obs_h is None and obs is not None:
        obs_h = obs.selected_duration or obs.final_sampling_time or obs.calculated_minimum
    if obs_h is None:
        raise ValidationError("observation duration required", field="observation_duration_h")

    hl_min, hl_max, hl_unit = _primary_analyte_half_life(analytes)
    hl_max_h = to_hours(hl_max, hl_unit) if hl_max is not None else None

    result = generate_sampling_recommendation(
        SamplingRecommendInput(
            analyte_windows=windows,
            observation_duration_h=float(obs_h),
            half_life_max_h=hl_max_h,
            design_type=design.type if design else None,
            target_point_count=payload.target_point_count,
        )
    )

    plan = _load_sampling(db, project_id)
    creating = plan is None
    if creating:
        plan = SamplingPlan(project_id=project_id)
        apply_provenance(plan, None, creating=True)
        db.add(plan)
        db.flush()
    else:
        for p in list(plan.points):
            db.delete(p)
        db.flush()

    plan.design_id = design.id if design else None
    plan.final_observation_h = float(obs_h)
    plan.manual_override = False
    plan.rationale = result.rationale
    plan.rule_ids = result.rule_ids
    plan.warnings = result.warnings
    plan.status = result.status
    plan.origin = "RULE_DERIVED"
    plan.source_ids = []

    points_orm: list[SamplingPoint] = []
    for idx, draft in enumerate(result.points):
        pt = SamplingPoint(
            sampling_plan_id=plan.id,
            time_h=draft.time_h,
            time_min=point_time_min(draft.time_h),
            window_before_min=draft.window_before_min,
            window_after_min=draft.window_after_min,
            reason=draft.reason,
            sequence_order=idx,
            mandatory=draft.mandatory,
            analyte_ids=draft.analyte_ids,
        )
        apply_provenance(
            pt,
            ProvenanceIn(origin="RULE_DERIVED", status="PROPOSED"),  # type: ignore[arg-type]
            creating=True,
        )
        db.add(pt)
        points_orm.append(pt)

    plan.total_points_per_period = len(points_orm)
    issues = validate_sampling_plan(
        [{"time_h": p.time_h, "reason": p.reason} for p in points_orm],
        observation_duration_h=float(obs_h),
        analyte_windows=windows,
        design_type=design.type if design else None,
        manual_override=False,
    )
    plan.validation_issues = [
        {"severity": i.severity, "code": i.code, "message": i.message, "field": i.field} for i in issues
    ]
    if not creating:
        bump_entity_version(plan)
    db.commit()
    plan = _load_sampling(db, project_id)
    assert plan is not None
    return serialize_sampling(plan)


def get_sampling(db: Session, project_id: UUID) -> SamplingPlanOut:
    _get_project(db, project_id)
    plan = _load_sampling(db, project_id)
    if plan is None:
        raise NotFoundError("Sampling plan not found", field="sampling")
    return serialize_sampling(plan)


def patch_sampling(db: Session, project_id: UUID, payload: SamplingPatchRequest) -> SamplingPlanOut:
    _get_project(db, project_id)
    plan = _load_sampling(db, project_id)
    if plan is None:
        raise NotFoundError("Sampling plan not found", field="sampling")
    design = db.execute(select(Design).where(Design.project_id == project_id)).scalar_one_or_none()
    analytes = list(db.execute(select(Analyte).where(Analyte.project_id == project_id)).scalars().all())
    windows = _analyte_windows(analytes)

    for p in list(plan.points):
        db.delete(p)
    db.flush()

    points_orm: list[SamplingPoint] = []
    for idx, item in enumerate(sorted(payload.points, key=lambda x: x.time_h)):
        pt = SamplingPoint(
            sampling_plan_id=plan.id,
            time_h=item.time_h,
            time_min=point_time_min(item.time_h),
            window_before_min=item.window_before_min,
            window_after_min=item.window_after_min,
            reason=item.reason,
            sequence_order=idx,
            mandatory=item.mandatory,
            analyte_ids=item.analyte_ids or [],
        )
        apply_provenance(pt, item.provenance, creating=True)
        db.add(pt)
        points_orm.append(pt)

    obs_h = payload.final_observation_h
    if obs_h is None:
        obs_h = plan.final_observation_h
    plan.final_observation_h = obs_h
    plan.total_points_per_period = len(points_orm)
    plan.manual_override = True
    plan.design_id = design.id if design else plan.design_id
    apply_provenance(plan, payload.provenance)
    issues = validate_sampling_plan(
        [{"time_h": p.time_h, "reason": p.reason} for p in points_orm],
        observation_duration_h=obs_h,
        analyte_windows=windows or None,
        design_type=design.type if design else None,
        manual_override=True,
    )
    plan.validation_issues = [
        {"severity": i.severity, "code": i.code, "message": i.message, "field": i.field} for i in issues
    ]
    bump_entity_version(plan)
    db.commit()
    plan = _load_sampling(db, project_id)
    assert plan is not None
    return serialize_sampling(plan)


def validate_sampling(db: Session, project_id: UUID) -> dict:
    plan = get_sampling(db, project_id)
    design = db.execute(select(Design).where(Design.project_id == project_id)).scalar_one_or_none()
    analytes = list(db.execute(select(Analyte).where(Analyte.project_id == project_id)).scalars().all())
    windows = _analyte_windows(analytes)
    issues = validate_sampling_plan(
        [{"time_h": p.time_h, "reason": p.reason} for p in plan.points],
        observation_duration_h=plan.final_observation_h,
        analyte_windows=windows or None,
        design_type=design.type if design else None,
        manual_override=plan.manual_override,
    )
    return {
        "issues": [
            {"severity": i.severity, "code": i.code, "message": i.message, "field": i.field} for i in issues
        ],
        "blocking": any(i.severity == "CRITICAL" for i in issues),
    }


def calculate_and_store_blood(
    db: Session, project_id: UUID, payload: BloodVolumeCalculateRequest
) -> BloodVolumeOut:
    _get_project(db, project_id)
    design = db.execute(select(Design).where(Design.project_id == project_id)).scalar_one_or_none()
    subjects = db.execute(select(SubjectPlan).where(SubjectPlan.project_id == project_id)).scalar_one_or_none()
    sampling = _load_sampling(db, project_id)

    periods = payload.periods
    if periods is None:
        periods = design.periods if design and design.periods else None
    if periods is None:
        raise ValidationError("periods required (from Design or request)", field="periods")

    n_subjects = payload.subjects
    if n_subjects is None:
        n_subjects = (
            subjects.planned_randomized_n
            if subjects and subjects.planned_randomized_n is not None
            else None
        )
    if n_subjects is None:
        raise ValidationError("subjects required (from SubjectPlan or request)", field="subjects")

    points = sampling.total_points_per_period if sampling else None
    if not points:
        raise ValidationError("sampling points_per_period required", field="sampling")

    sample_count = calculate_sample_count(
        SampleCountInput(
            points_per_period=points,
            periods=periods,
            planned_subjects=n_subjects,
        )
    )
    result = calculate_blood_volume(
        BloodVolumeInput(
            subjects=n_subjects,
            periods=periods,
            sampling_points_per_period=points,
            blood_volume_per_pk_sample_ml=payload.blood_volume_per_pk_sample_ml,
            screening_volume_ml=payload.screening_volume_ml,
            safety_laboratory_volume_ml=payload.safety_laboratory_volume_ml,
            other_blood_volume_ml=payload.other_blood_volume_ml,
            reserve_duplicate_factor=payload.reserve_duplicate_factor,
        )
    )

    row = db.execute(
        select(BloodVolumeCalculation).where(BloodVolumeCalculation.project_id == project_id)
    ).scalar_one_or_none()
    creating = row is None
    if creating:
        row = BloodVolumeCalculation(project_id=project_id, subjects=n_subjects, periods=periods,
                                     sampling_points_per_period=points,
                                     blood_volume_per_pk_sample_ml=payload.blood_volume_per_pk_sample_ml,
                                     pk_volume_ml=0, screening_total_ml=0, safety_total_ml=0,
                                     other_total_ml=0, total_volume_ml=0, volume_per_subject_ml=0,
                                     volume_per_period_ml=0)
        apply_provenance(row, None, creating=True)
        db.add(row)

    row.subjects = n_subjects
    row.periods = periods
    row.sampling_points_per_period = points
    row.blood_volume_per_pk_sample_ml = payload.blood_volume_per_pk_sample_ml
    row.screening_volume_ml = payload.screening_volume_ml
    row.safety_laboratory_volume_ml = payload.safety_laboratory_volume_ml
    row.other_blood_volume_ml = payload.other_blood_volume_ml
    row.reserve_duplicate_factor = payload.reserve_duplicate_factor
    row.pk_volume_ml = result.pk_volume_ml
    row.screening_total_ml = result.screening_volume_ml
    row.safety_total_ml = result.safety_volume_ml
    row.other_total_ml = result.other_volume_ml
    row.total_volume_ml = result.total_volume_ml
    row.volume_per_subject_ml = result.volume_per_subject_ml
    row.volume_per_period_ml = result.volume_per_period_ml
    row.rationale = result.rationale
    row.breakdown = result.breakdown
    row.sample_count = {
        "points_per_period": sample_count.points_per_period,
        "periods": sample_count.periods,
        "planned_subjects": sample_count.planned_subjects,
        "total_subject_periods": sample_count.total_subject_periods,
        "total_pk_samples": sample_count.total_pk_samples,
        "rationale": sample_count.rationale,
    }
    row.status = "CALCULATED"
    row.origin = "CALCULATED"
    if not creating:
        bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return serialize_blood(row)


def get_blood_volume(db: Session, project_id: UUID) -> BloodVolumeOut:
    _get_project(db, project_id)
    row = db.execute(
        select(BloodVolumeCalculation).where(BloodVolumeCalculation.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Blood volume calculation not found", field="blood_volume")
    return serialize_blood(row)

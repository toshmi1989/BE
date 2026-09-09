from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.cv_pooling import pool_cv
from app.domain.cv_selection import select_cv_for_sample_size
from app.domain.cv_validation import CVStudyData, validate_cv_study
from app.domain.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.sample_size import SampleSizeInput, calculate_sample_size
from app.domain.stats_rules import ROUNDING_2X2, RULE_STAT_DEFAULTS
from app.domain.subject_reserve import ReserveInput, apply_subject_reserve
from app.models import Analyte, Design, Source, SubjectPlan
from app.models.cv_study import CVStudy
from app.models.statistics import (
    CVPool,
    CVSelection,
    SampleSizeCalculation,
    StatisticalConfig,
    SubjectReserveCalculation,
)
from app.schemas.common import ProvenanceIn
from app.schemas.phase4 import (
    CVPoolOut,
    CVPoolRequest,
    CVSelectRequest,
    CVSelectionOut,
    CVStudyCreate,
    CVStudyOut,
    SampleSizeOut,
    SampleSizeRequest,
    StatisticalConfigOut,
)
from app.services.provenance import apply_provenance, bump_entity_version, with_provenance


def _sync_subject_plan_from_sample_size(
    db: Session,
    project_id: UUID,
    *,
    evaluable_n: int | None,
    randomized_n: int | None,
    screened_n: int | None,
) -> None:
    """
    Accept calculated sample size into SubjectPlan (canonical N owner).

    SampleSizeCalculation remains the CALCULATED RESULT record; SubjectPlan
    holds the protocol-facing accepted counts.
    """
    if evaluable_n is None or randomized_n is None:
        return
    plan = db.execute(
        select(SubjectPlan).where(SubjectPlan.project_id == project_id)
    ).scalar_one_or_none()
    creating = plan is None
    if creating:
        plan = SubjectPlan(project_id=project_id)
        apply_provenance(plan, ProvenanceIn(origin="CALCULATED", status="PROPOSED"), creating=True)
        db.add(plan)
    plan.target_evaluable_n = int(evaluable_n)
    plan.planned_randomized_n = int(randomized_n)
    if screened_n is not None:
        plan.planned_screened_n = int(screened_n)
    if plan.reserve_n is None and screened_n is not None and randomized_n is not None:
        plan.reserve_n = max(0, int(screened_n) - int(randomized_n))
    if not creating:
        apply_provenance(plan, ProvenanceIn(origin="CALCULATED", status="PROPOSED"))
        bump_entity_version(plan)


def _get_project_id(db: Session, project_id: UUID) -> UUID:
    from app.models import Project

    if db.get(Project, project_id) is None:
        raise NotFoundError("Project not found", field="project_id")
    return project_id


def serialize_cv(row: CVStudy) -> CVStudyOut:
    return with_provenance(CVStudyOut, row)


def serialize_pool(row: CVPool) -> CVPoolOut:
    return with_provenance(CVPoolOut, row)


def serialize_selection(row: CVSelection) -> CVSelectionOut:
    return with_provenance(CVSelectionOut, row)


def serialize_config(row: StatisticalConfig) -> StatisticalConfigOut:
    return with_provenance(StatisticalConfigOut, row)


def serialize_sample_size(row: SampleSizeCalculation) -> SampleSizeOut:
    return with_provenance(SampleSizeOut, row)


def _to_cv_data(row: CVStudy) -> CVStudyData:
    return CVStudyData(
        analyte_id=str(row.analyte_id),
        parameter=row.parameter,
        design=row.design,
        condition=row.condition,
        dose=row.dose,
        n_total=row.n_total,
        n_be_analysis=row.n_be_analysis,
        cv_value=row.cv_value,
        cv_unit=row.cv_unit,
        source_id=row.source_id,
        cv_type=row.cv_type,
    )


def ensure_statistical_config(db: Session, project_id: UUID) -> StatisticalConfig:
    row = db.execute(
        select(StatisticalConfig).where(StatisticalConfig.project_id == project_id)
    ).scalar_one_or_none()
    if row is not None:
        return row
    p = RULE_STAT_DEFAULTS.parameters
    row = StatisticalConfig(
        project_id=project_id,
        alpha=float(p["alpha"]),
        power=float(p["power"]),
        be_lower=float(p["be_lower"]),
        be_upper=float(p["be_upper"]),
        expected_ratio=float(p["expected_ratio"]),
        analysis_method=str(p["analysis_method"]),
        transformation=str(p["transformation"]),
        software=None,
        algorithm_version=None,
        rule_id=RULE_STAT_DEFAULTS.rule_id,
        defaults_source=RULE_STAT_DEFAULTS.source,
    )
    apply_provenance(
        row,
        ProvenanceIn(origin="RULE_DERIVED", status="PROPOSED"),  # type: ignore[arg-type]
        creating=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_cv_study(db: Session, project_id: UUID, payload: CVStudyCreate) -> CVStudyOut:
    _get_project_id(db, project_id)
    analyte = db.get(Analyte, payload.analyte_id)
    if analyte is None or analyte.project_id != project_id:
        raise ConflictError("analyte_id must belong to project", field="analyte_id")

    # source must exist in project sources if UUID-like, else allow opaque research id string
    sources = db.execute(select(Source).where(Source.project_id == project_id)).scalars().all()
    source_ids = {str(s.id) for s in sources}
    if payload.source_id not in source_ids and len(source_ids) > 0:
        # allow external opaque ids for future Research Engine, but warn via provenance notes
        pass
    if not sources and not payload.source_id:
        raise ValidationError("source_id required", field="source_id")

    data = CVStudyData(
        analyte_id=str(payload.analyte_id),
        parameter=payload.parameter,
        design=payload.design,
        condition=payload.condition,
        dose=payload.dose,
        n_total=payload.n_total,
        n_be_analysis=payload.n_be_analysis,
        cv_value=payload.cv_value,
        cv_unit=payload.cv_unit,
        source_id=payload.source_id,
        cv_type=payload.cv_type,
    )
    validate_cv_study(data)

    # AI provenance cannot create VERIFIED
    if payload.provenance and str(payload.provenance.origin) == "AI_PROPOSED":
        if payload.provenance.status and str(payload.provenance.status) == "VERIFIED":
            raise ValidationError(
                "AI-extracted CV cannot be VERIFIED automatically",
                field="provenance.status",
            )

    row = CVStudy(
        project_id=project_id,
        source_id=payload.source_id,
        study_name=payload.study_name,
        publication_title=payload.publication_title,
        analyte_id=payload.analyte_id,
        parameter=payload.parameter,
        design=payload.design,
        condition=payload.condition,
        dose=payload.dose,
        n_total=payload.n_total,
        n_be_analysis=payload.n_be_analysis,
        cv_value=payload.cv_value,
        cv_unit=payload.cv_unit,
        cv_type=payload.cv_type,
        evidence=[e.model_dump() for e in (payload.evidence or [])],
    )
    apply_provenance(row, payload.provenance, creating=True)
    if payload.extraction_method and not (payload.provenance and payload.provenance.extraction_method):
        row.extraction_method = payload.extraction_method
    if payload.notes and not (payload.provenance and payload.provenance.notes):
        row.notes = payload.notes
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_cv(row)


def list_cv_studies(db: Session, project_id: UUID) -> list[CVStudyOut]:
    _get_project_id(db, project_id)
    rows = db.execute(select(CVStudy).where(CVStudy.project_id == project_id)).scalars().all()
    return [serialize_cv(r) for r in rows]


def pool_cv_studies(db: Session, project_id: UUID, payload: CVPoolRequest) -> CVPoolOut:
    _get_project_id(db, project_id)
    rows = []
    for sid in payload.cv_study_ids:
        row = db.get(CVStudy, sid)
        if row is None or row.project_id != project_id:
            raise NotFoundError("CV study not found", field="cv_study_ids")
        rows.append(row)
    result = pool_cv([_to_cv_data(r) for r in rows], method_id=payload.method)
    pool = CVPool(
        project_id=project_id,
        method=result.method,
        algorithm_version=result.algorithm_version,
        pooled_cv=result.pooled_cv,
        confidence_interval=list(result.confidence_interval)
        if result.confidence_interval
        else None,
        inputs=result.inputs,
        cv_study_ids=[str(r.id) for r in rows],
        warnings=result.warnings,
        mismatches=result.mismatches,
        parameter=rows[0].parameter if rows else None,
    )
    apply_provenance(
        pool,
        ProvenanceIn(origin="CALCULATED", status=result.status),  # type: ignore[arg-type]
        creating=True,
    )
    pool.status = result.status
    db.add(pool)
    db.commit()
    db.refresh(pool)
    return serialize_pool(pool)


def select_cv(db: Session, project_id: UUID, payload: CVSelectRequest) -> CVSelectionOut:
    _get_project_id(db, project_id)
    studies: list[CVStudy] = []
    if payload.cv_study_ids:
        for sid in payload.cv_study_ids:
            row = db.get(CVStudy, sid)
            if row is None or row.project_id != project_id:
                raise NotFoundError("CV study not found", field="cv_study_ids")
            studies.append(row)

    pooled_cv = None
    if payload.pool_id:
        pool = db.get(CVPool, payload.pool_id)
        if pool is None or pool.project_id != project_id:
            raise NotFoundError("CV pool not found", field="pool_id")
        pooled_cv = pool.pooled_cv

    selected_index = None
    if payload.selection_method == "SINGLE_STUDY":
        if payload.selected_study_id is None:
            raise ValidationError("selected_study_id required", field="selected_study_id")
        ids = [r.id for r in studies] if studies else []
        if payload.selected_study_id not in ids:
            row = db.get(CVStudy, payload.selected_study_id)
            if row is None or row.project_id != project_id:
                raise NotFoundError("selected study not found", field="selected_study_id")
            studies = [row]
            selected_index = 0
        else:
            selected_index = ids.index(payload.selected_study_id)

    result = select_cv_for_sample_size(
        method=payload.selection_method,
        studies=[_to_cv_data(s) for s in studies] or None,
        pooled_cv=pooled_cv,
        expert_cv=payload.expert_cv,
        guideline_cv=payload.guideline_cv,
        selected_study_index=selected_index,
        cv_unit=payload.cv_unit,
    )

    row = db.execute(select(CVSelection).where(CVSelection.project_id == project_id)).scalar_one_or_none()
    creating = row is None
    if creating:
        row = CVSelection(project_id=project_id, selection_method=payload.selection_method)
        apply_provenance(row, None, creating=True)
        db.add(row)
    row.selected_cv = result.selected_cv
    row.cv_unit = result.cv_unit
    row.selection_method = result.selection_method
    row.rationale = result.rationale
    row.source_study_ids = result.source_study_ids
    row.warnings = result.warnings
    row.parameter = result.parameter
    row.analyte_id = result.analyte_id
    row.status = result.status
    row.origin = "CALCULATED" if payload.selection_method == "POOLED" else "USER"
    if not creating:
        bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return serialize_selection(row)


def get_cv_selection(db: Session, project_id: UUID) -> CVSelectionOut:
    _get_project_id(db, project_id)
    row = db.execute(select(CVSelection).where(CVSelection.project_id == project_id)).scalar_one_or_none()
    if row is None:
        raise NotFoundError("CV selection not found", field="cv_selection")
    return serialize_selection(row)


def get_statistical_config(db: Session, project_id: UUID) -> StatisticalConfigOut:
    _get_project_id(db, project_id)
    row = ensure_statistical_config(db, project_id)
    return serialize_config(row)


def calculate_and_store_sample_size(
    db: Session, project_id: UUID, payload: SampleSizeRequest
) -> SampleSizeOut:
    _get_project_id(db, project_id)
    cfg = ensure_statistical_config(db, project_id)
    design = db.execute(select(Design).where(Design.project_id == project_id)).scalar_one_or_none()
    selection = db.execute(
        select(CVSelection).where(CVSelection.project_id == project_id)
    ).scalar_one_or_none()

    design_type = payload.design_type or (design.type if design else None)
    if not design_type:
        raise ValidationError("design_type required", field="design_type")

    selected_cv = payload.selected_cv
    if selected_cv is None:
        selected_cv = selection.selected_cv if selection else None
    if selected_cv is None:
        raise ValidationError("selected_cv required (or create CV selection first)", field="selected_cv")

    result = calculate_sample_size(
        SampleSizeInput(
            design_type=design_type,
            selected_cv_percent=float(selected_cv),
            expected_ratio=payload.expected_ratio
            if payload.expected_ratio is not None
            else cfg.expected_ratio,
            alpha=payload.alpha if payload.alpha is not None else cfg.alpha,
            power=payload.power if payload.power is not None else cfg.power,
            be_lower=payload.be_lower if payload.be_lower is not None else cfg.be_lower,
            be_upper=payload.be_upper if payload.be_upper is not None else cfg.be_upper,
            parameter=payload.parameter or (selection.parameter if selection else None),
            analyte_id=selection.analyte_id if selection else None,
            dropout_pct=payload.dropout_pct,
            reserve_pct=payload.reserve_pct,
            screen_failure_pct=payload.screen_failure_pct,
        )
    )

    row = SampleSizeCalculation(
        project_id=project_id,
        design_type=design_type,
        selected_cv=float(selected_cv),
        parameter=result.inputs_snapshot.get("parameter"),
        evaluable_n=result.evaluable_n,
        randomized_n=result.randomized_n,
        screened_n=result.screened_n,
        method=result.method,
        formula=result.formula,
        software_version=result.software_version,
        algorithm_version=result.algorithm_version,
        achieved_power=result.achieved_power,
        inputs_snapshot=result.inputs_snapshot,
        warnings=result.warnings,
        reserve_formula=result.formula,
        created_by=payload.created_by,
    )
    apply_provenance(
        row,
        ProvenanceIn(origin="CALCULATED", status=result.status),  # type: ignore[arg-type]
        creating=True,
    )
    row.status = result.status
    db.add(row)
    db.flush()

    if result.evaluable_n is not None and result.randomized_n is not None:
        reserve = apply_subject_reserve(
            ReserveInput(
                evaluable_n=result.evaluable_n,
                dropout_pct=payload.dropout_pct,
                reserve_pct=payload.reserve_pct,
                screen_failure_pct=payload.screen_failure_pct,
                rounding=ROUNDING_2X2,
            )
        )
        reserve_row = SubjectReserveCalculation(
            project_id=project_id,
            sample_size_calculation_id=row.id,
            evaluable_n=reserve.evaluable_n,
            dropout_pct=payload.dropout_pct,
            reserve_pct=payload.reserve_pct,
            screen_failure_pct=payload.screen_failure_pct,
            randomized_n=reserve.randomized_n,
            screened_n=reserve.screened_n,
            formula=reserve.formula,
            rationale=reserve.rationale,
            rounding_rule_id=reserve.rule_id,
        )
        apply_provenance(
            reserve_row,
            ProvenanceIn(origin="CALCULATED", status="PROPOSED"),
            creating=True,
        )
        db.add(reserve_row)

    # Canonicalize: accept calculated N into SubjectPlan (single protocol source)
    _sync_subject_plan_from_sample_size(
        db,
        project_id,
        evaluable_n=result.evaluable_n,
        randomized_n=result.randomized_n,
        screened_n=result.screened_n,
    )

    db.commit()
    db.refresh(row)
    return serialize_sample_size(row)


def list_sample_sizes(db: Session, project_id: UUID) -> list[SampleSizeOut]:
    _get_project_id(db, project_id)
    rows = (
        db.execute(
            select(SampleSizeCalculation)
            .where(SampleSizeCalculation.project_id == project_id)
            .order_by(SampleSizeCalculation.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [serialize_sample_size(r) for r in rows]


def get_latest_sample_size(db: Session, project_id: UUID) -> SampleSizeOut:
    rows = list_sample_sizes(db, project_id)
    if not rows:
        raise NotFoundError("Sample size calculation not found", field="sample_size")
    return rows[0]


def validate_statistics(db: Session, project_id: UUID) -> dict:
    _get_project_id(db, project_id)
    issues: list[dict] = []
    cvs = list_cv_studies(db, project_id)
    if not cvs:
        issues.append(
            {
                "severity": "ERROR",
                "code": "NO_CV",
                "message": "No CV studies registered",
                "field": "cv_studies",
            }
        )
    selection = db.execute(
        select(CVSelection).where(CVSelection.project_id == project_id)
    ).scalar_one_or_none()
    if selection is None or selection.selected_cv is None:
        issues.append(
            {
                "severity": "ERROR",
                "code": "NO_SELECTED_CV",
                "message": "CV not selected for sample size",
                "field": "cv_selection",
            }
        )
    elif selection.status == "NEEDS_REVIEW":
        issues.append(
            {
                "severity": "WARNING",
                "code": "CV_NEEDS_REVIEW",
                "message": "Selected CV requires review",
                "field": "cv_selection",
            }
        )

    ss = (
        db.execute(
            select(SampleSizeCalculation)
            .where(SampleSizeCalculation.project_id == project_id)
            .order_by(SampleSizeCalculation.created_at.desc())
        )
        .scalars()
        .first()
    )
    if ss is None:
        issues.append(
            {
                "severity": "WARNING",
                "code": "NO_SAMPLE_SIZE",
                "message": "No sample size calculation stored",
                "field": "sample_size",
            }
        )
    elif ss.status in {"NEEDS_REVIEW", "NOT_IMPLEMENTED"}:
        issues.append(
            {
                "severity": "WARNING",
                "code": "SAMPLE_SIZE_STATUS",
                "message": f"Sample size status={ss.status}",
                "field": "sample_size",
            }
        )
    elif ss.status == "PROPOSED":
        issues.append(
            {
                "severity": "INFO",
                "code": "SAMPLE_SIZE_PROPOSED",
                "message": "Sample size is PROPOSED, not VERIFIED",
                "field": "sample_size",
            }
        )

    blocking = any(i["severity"] in {"CRITICAL", "ERROR"} for i in issues)
    return {"issues": issues, "blocking": blocking}

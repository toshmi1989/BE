from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.constants import DEFAULT_DECISION_STATUS, ELIGIBILITY_CATEGORIES
from app.domain.design_recommend import DesignRecommendInput, recommend_design
from app.domain.design_validation import validate_design_payload
from app.domain.exceptions import ConflictError, NotFoundError, ValidationError
from app.domain.food_validation import validate_food_payload
from app.domain.provenance import DecisionStatus, can_ai_overwrite
from app.domain.subject_plan import SubjectPlanValues, calculate_subject_plan
from app.models import (
    ClientInput,
    Design,
    EligibilityCriterion,
    FoodCondition,
    Project,
    SubjectPlan,
)
from app.schemas.common import ProvenanceIn
from app.schemas.phase2 import (
    ClientInputOut,
    ClientInputUpsert,
    CriterionCreate,
    CriterionOut,
    CriterionUpdate,
    DesignCreate,
    DesignOut,
    DesignRecommendRequest,
    DesignRecommendResponse,
    DesignUpdate,
    EligibilityOut,
    EligibilityReplace,
    FoodOut,
    FoodUpdate,
    FoodUpsert,
    SubjectPlanOut,
    SubjectPlanUpdate,
    SubjectPlanUpsert,
)
from app.services.provenance import apply_provenance, bump_entity_version, with_provenance


def _get_project(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", field="project_id")
    return project


def serialize_design(design: Design) -> DesignOut:
    return with_provenance(DesignOut, design)


def serialize_food(food: FoodCondition) -> FoodOut:
    return with_provenance(FoodOut, food)


def serialize_criterion(row: EligibilityCriterion) -> CriterionOut:
    return with_provenance(CriterionOut, row)


def serialize_subjects(plan: SubjectPlan) -> SubjectPlanOut:
    return with_provenance(SubjectPlanOut, plan)


def serialize_client_input(row: ClientInput) -> ClientInputOut:
    return with_provenance(ClientInputOut, row)


def _sync_decision_status(entity, decision_status: DecisionStatus | str | None) -> None:
    if decision_status is None:
        return
    value = DecisionStatus(decision_status).value
    entity.decision_status = value
    entity.status = value


def create_design(db: Session, project_id: UUID, payload: DesignCreate) -> DesignOut:
    _get_project(db, project_id)
    existing = db.execute(select(Design).where(Design.project_id == project_id)).scalar_one_or_none()
    if existing is not None:
        raise ConflictError("Design already exists; use PATCH", field="design")

    validate_design_payload(
        design_type=payload.type,
        periods=payload.periods,
        sequences=payload.sequences,
        treatments=payload.treatments,
        stage_configuration=payload.stage_configuration,
    )

    design = Design(
        project_id=project_id,
        type=payload.type,
        periods=payload.periods,
        sequences=payload.sequences or [],
        treatments=payload.treatments or [],
        randomization=payload.randomization,
        blinding=payload.blinding,
        food_condition=payload.food_condition,
        stage_configuration=payload.stage_configuration,
        rationale=payload.rationale,
        decision_status=(
            payload.decision_status.value if payload.decision_status else DEFAULT_DECISION_STATUS
        ),
    )
    apply_provenance(design, payload.provenance, creating=True)
    if payload.decision_status:
        _sync_decision_status(design, payload.decision_status)
    elif design.status == "MISSING":
        design.status = design.decision_status
    # Recommended designs must never be stored as VERIFIED implicitly
    if design.decision_status == DecisionStatus.VERIFIED.value and (
        payload.provenance is None
        or payload.provenance.origin is None
        or str(payload.provenance.origin) in {"RULE_DERIVED", "AI_PROPOSED"}
    ):
        raise ValidationError(
            "Recommended/rule-derived design cannot be created as VERIFIED",
            field="decision_status",
        )
    db.add(design)
    db.commit()
    db.refresh(design)
    return serialize_design(design)


def get_design(db: Session, project_id: UUID) -> DesignOut:
    _get_project(db, project_id)
    design = db.execute(select(Design).where(Design.project_id == project_id)).scalar_one_or_none()
    if design is None:
        raise NotFoundError("Design not found", field="design")
    return serialize_design(design)


def update_design(db: Session, project_id: UUID, payload: DesignUpdate) -> DesignOut:
    _get_project(db, project_id)
    design = db.execute(select(Design).where(Design.project_id == project_id)).scalar_one_or_none()
    if design is None:
        raise NotFoundError("Design not found", field="design")

    data = payload.model_dump(exclude_unset=True, exclude={"provenance", "decision_status"})
    for key, value in data.items():
        if key in {"sequences", "treatments"} and value is None:
            setattr(design, key, [])
        else:
            setattr(design, key, value)

    if "decision_status" in payload.model_fields_set:
        _sync_decision_status(design, payload.decision_status)

    validate_design_payload(
        design_type=design.type,
        periods=design.periods,
        sequences=design.sequences,
        treatments=design.treatments,
        stage_configuration=design.stage_configuration,
    )
    apply_provenance(design, payload.provenance)
    bump_entity_version(design)
    db.commit()
    db.refresh(design)
    return serialize_design(design)


def recommend_and_optionally_persist(
    db: Session, project_id: UUID, payload: DesignRecommendRequest
) -> DesignRecommendResponse:
    _get_project(db, project_id)
    result = recommend_design(
        DesignRecommendInput(
            available_guideline_recommendation=payload.available_guideline_recommendation,
            reference_product_known=payload.reference_product_known,
            half_life=payload.half_life,
            variability_known=payload.variability_known,
            variability_level=payload.variability_level,
            dosage_form=payload.dosage_form,
            route=payload.route,
            food_condition=payload.food_condition,
            expert_override=payload.expert_override,
            evidence_source_ids=list(payload.evidence_source_ids),
        )
    )

    persisted: DesignOut | None = None
    if payload.persist and result.recommended_design is not None:
        existing = db.execute(select(Design).where(Design.project_id == project_id)).scalar_one_or_none()
        if existing is not None and not can_ai_overwrite(existing.decision_status):
            # Never overwrite VERIFIED design from recommendation persist
            persisted = None
        else:
            body = result.recommended_design
            prov = ProvenanceIn(
                status=result.status,  # type: ignore[arg-type]
                origin=result.origin,  # type: ignore[arg-type]
                confidence=result.confidence,
                source_ids=result.evidence_source_ids,
            )
            if existing is None:
                persisted = create_design(
                    db,
                    project_id,
                    DesignCreate(
                        type=body["type"],
                        periods=body.get("periods"),
                        sequences=body.get("sequences"),
                        treatments=body.get("treatments"),
                        randomization=body.get("randomization"),
                        blinding=body.get("blinding"),
                        food_condition=body.get("food_condition"),
                        stage_configuration=body.get("stage_configuration"),
                        rationale=result.rationale,
                        decision_status=DecisionStatus(result.status),
                        provenance=prov,
                    ),
                )
            else:
                existing.type = body["type"]
                existing.periods = body.get("periods")
                existing.sequences = body.get("sequences") or []
                existing.treatments = body.get("treatments") or []
                existing.randomization = body.get("randomization")
                existing.blinding = body.get("blinding")
                existing.food_condition = body.get("food_condition")
                existing.stage_configuration = body.get("stage_configuration")
                existing.rationale = result.rationale
                existing.recommendation_confidence = result.confidence
                apply_provenance(existing, prov)
                _sync_decision_status(existing, result.status)
                bump_entity_version(existing)
                db.commit()
                db.refresh(existing)
                persisted = serialize_design(existing)

    return DesignRecommendResponse(
        recommended_design=result.recommended_design,
        rationale=result.rationale,
        confidence=result.confidence,
        evidence_source_ids=result.evidence_source_ids,
        status=result.status,
        origin=result.origin,
        persisted_design=persisted,
    )


def upsert_food(db: Session, project_id: UUID, payload: FoodUpsert) -> FoodOut:
    _get_project(db, project_id)
    validate_food_payload(
        condition=payload.condition,
        meal_type=payload.meal_type,
        calories=payload.calories,
        fat_percent=payload.fat_percent,
        meal_start_offset_min=payload.meal_start_offset_min,
        dose_after_meal_min=payload.dose_after_meal_min,
        water_volume_ml=payload.water_volume_ml,
    )
    food = db.execute(
        select(FoodCondition).where(FoodCondition.project_id == project_id)
    ).scalar_one_or_none()
    creating = food is None
    if creating:
        food = FoodCondition(project_id=project_id, condition=payload.condition, composition=[])
        apply_provenance(food, None, creating=True)
        db.add(food)

    food.condition = payload.condition
    food.meal_type = payload.meal_type
    food.calories = payload.calories
    food.fat_percent = payload.fat_percent
    food.composition = payload.composition if payload.composition is not None else []
    food.meal_start_offset_min = payload.meal_start_offset_min
    food.dose_after_meal_min = payload.dose_after_meal_min
    food.water_volume_ml = payload.water_volume_ml
    apply_provenance(food, payload.provenance, creating=creating)
    if payload.decision_status:
        _sync_decision_status(food, payload.decision_status)
    elif creating and food.status == "MISSING":
        food.decision_status = DEFAULT_DECISION_STATUS
        food.status = DEFAULT_DECISION_STATUS
    if not creating:
        bump_entity_version(food)
    db.commit()
    db.refresh(food)
    return serialize_food(food)


def get_food(db: Session, project_id: UUID) -> FoodOut:
    _get_project(db, project_id)
    food = db.execute(
        select(FoodCondition).where(FoodCondition.project_id == project_id)
    ).scalar_one_or_none()
    if food is None:
        raise NotFoundError("Food condition not found", field="food")
    return serialize_food(food)


def update_food(db: Session, project_id: UUID, payload: FoodUpdate) -> FoodOut:
    food = db.execute(
        select(FoodCondition).where(FoodCondition.project_id == project_id)
    ).scalar_one_or_none()
    if food is None:
        raise NotFoundError("Food condition not found", field="food")
    data = payload.model_dump(exclude_unset=True, exclude={"provenance", "decision_status"})
    for key, value in data.items():
        if key == "composition" and value is None:
            food.composition = []
        else:
            setattr(food, key, value)
    if "decision_status" in payload.model_fields_set:
        _sync_decision_status(food, payload.decision_status)
    validate_food_payload(
        condition=food.condition,
        meal_type=food.meal_type,
        calories=food.calories,
        fat_percent=food.fat_percent,
        meal_start_offset_min=food.meal_start_offset_min,
        dose_after_meal_min=food.dose_after_meal_min,
        water_volume_ml=food.water_volume_ml,
    )
    apply_provenance(food, payload.provenance)
    bump_entity_version(food)
    db.commit()
    db.refresh(food)
    return serialize_food(food)


def get_eligibility(db: Session, project_id: UUID) -> EligibilityOut:
    _get_project(db, project_id)
    rows = (
        db.execute(
            select(EligibilityCriterion)
            .where(EligibilityCriterion.project_id == project_id)
            .order_by(EligibilityCriterion.category, EligibilityCriterion.number)
        )
        .scalars()
        .all()
    )
    out = EligibilityOut()
    for row in rows:
        item = serialize_criterion(row)
        getattr(out, row.category).append(item)
    return out


def replace_eligibility(db: Session, project_id: UUID, payload: EligibilityReplace) -> EligibilityOut:
    _get_project(db, project_id)
    existing = (
        db.execute(select(EligibilityCriterion).where(EligibilityCriterion.project_id == project_id))
        .scalars()
        .all()
    )
    for row in existing:
        db.delete(row)
    db.flush()

    for category in ELIGIBILITY_CATEGORIES:
        items: list[CriterionCreate] = getattr(payload, category)
        seen_numbers: set[int] = set()
        for idx, item in enumerate(items, start=1):
            if item.category and item.category != category:
                raise ValidationError(
                    "Criterion category must match collection",
                    field=f"{category}[{idx - 1}].category",
                )
            number = item.number if item.number is not None else idx
            if number in seen_numbers:
                raise ValidationError(
                    "Duplicate criterion number within category",
                    field=f"{category}.number",
                    details={"number": number},
                )
            seen_numbers.add(number)
            row = EligibilityCriterion(
                project_id=project_id,
                category=category,
                number=number,
                text=item.text,
            )
            apply_provenance(row, item.provenance, creating=True)
            db.add(row)
    db.commit()
    return get_eligibility(db, project_id)


def create_criterion(db: Session, project_id: UUID, payload: CriterionCreate) -> CriterionOut:
    _get_project(db, project_id)
    if not payload.category or payload.category not in ELIGIBILITY_CATEGORIES:
        raise ValidationError(
            f"Invalid category: {payload.category}",
            field="category",
            details={"allowed": list(ELIGIBILITY_CATEGORIES)},
        )
    category = payload.category
    number = payload.number
    if number is None:
        max_n = db.execute(
            select(func.max(EligibilityCriterion.number)).where(
                EligibilityCriterion.project_id == project_id,
                EligibilityCriterion.category == category,
            )
        ).scalar_one()
        number = int(max_n or 0) + 1

    conflict = db.execute(
        select(EligibilityCriterion).where(
            EligibilityCriterion.project_id == project_id,
            EligibilityCriterion.category == category,
            EligibilityCriterion.number == number,
        )
    ).scalar_one_or_none()
    if conflict is not None:
        raise ConflictError("Criterion number already exists in category", field="number")

    row = EligibilityCriterion(
        project_id=project_id,
        category=category,
        number=number,
        text=payload.text,
    )
    apply_provenance(row, payload.provenance, creating=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize_criterion(row)


def update_criterion(
    db: Session, project_id: UUID, criterion_id: UUID, payload: CriterionUpdate
) -> CriterionOut:
    row = db.get(EligibilityCriterion, criterion_id)
    if row is None or row.project_id != project_id:
        raise NotFoundError("Criterion not found", field="criterion_id")
    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    if "number" in data and data["number"] is not None:
        conflict = db.execute(
            select(EligibilityCriterion).where(
                EligibilityCriterion.project_id == project_id,
                EligibilityCriterion.category == row.category,
                EligibilityCriterion.number == data["number"],
                EligibilityCriterion.id != criterion_id,
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise ConflictError("Criterion number already exists in category", field="number")
    for key, value in data.items():
        setattr(row, key, value)
    apply_provenance(row, payload.provenance)
    bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return serialize_criterion(row)


def delete_criterion(db: Session, project_id: UUID, criterion_id: UUID) -> None:
    row = db.get(EligibilityCriterion, criterion_id)
    if row is None or row.project_id != project_id:
        raise NotFoundError("Criterion not found", field="criterion_id")
    db.delete(row)
    db.commit()


def upsert_subjects(db: Session, project_id: UUID, payload: SubjectPlanUpsert) -> SubjectPlanOut:
    _get_project(db, project_id)
    calculated = calculate_subject_plan(
        SubjectPlanValues(
            target_evaluable_n=payload.target_evaluable_n,
            planned_randomized_n=payload.planned_randomized_n,
            reserve_n=payload.reserve_n,
            planned_screened_n=payload.planned_screened_n,
        )
    )
    plan = db.execute(
        select(SubjectPlan).where(SubjectPlan.project_id == project_id)
    ).scalar_one_or_none()
    creating = plan is None
    if creating:
        plan = SubjectPlan(project_id=project_id)
        apply_provenance(plan, None, creating=True)
        db.add(plan)
    plan.target_evaluable_n = calculated.target_evaluable_n
    plan.planned_randomized_n = calculated.planned_randomized_n
    plan.reserve_n = calculated.reserve_n
    plan.planned_screened_n = calculated.planned_screened_n
    apply_provenance(plan, payload.provenance, creating=creating)
    if not creating:
        bump_entity_version(plan)
    db.commit()
    db.refresh(plan)
    return serialize_subjects(plan)


def get_subjects(db: Session, project_id: UUID) -> SubjectPlanOut:
    _get_project(db, project_id)
    plan = db.execute(
        select(SubjectPlan).where(SubjectPlan.project_id == project_id)
    ).scalar_one_or_none()
    if plan is None:
        raise NotFoundError("Subject plan not found", field="subjects")
    return serialize_subjects(plan)


def update_subjects(db: Session, project_id: UUID, payload: SubjectPlanUpdate) -> SubjectPlanOut:
    plan = db.execute(
        select(SubjectPlan).where(SubjectPlan.project_id == project_id)
    ).scalar_one_or_none()
    if plan is None:
        raise NotFoundError("Subject plan not found", field="subjects")
    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    for key, value in data.items():
        setattr(plan, key, value)
    calculate_subject_plan(
        SubjectPlanValues(
            target_evaluable_n=plan.target_evaluable_n,
            planned_randomized_n=plan.planned_randomized_n,
            reserve_n=plan.reserve_n,
            planned_screened_n=plan.planned_screened_n,
        )
    )
    apply_provenance(plan, payload.provenance)
    bump_entity_version(plan)
    db.commit()
    db.refresh(plan)
    return serialize_subjects(plan)


def upsert_client_input(db: Session, project_id: UUID, payload: ClientInputUpsert) -> ClientInputOut:
    _get_project(db, project_id)
    if payload.requested_subject_count is not None and payload.requested_subject_count <= 0:
        raise ValidationError(
            "requested_subject_count must be > 0 when supplied",
            field="requested_subject_count",
        )
    row = db.execute(
        select(ClientInput).where(ClientInput.project_id == project_id)
    ).scalar_one_or_none()
    creating = row is None
    if creating:
        row = ClientInput(project_id=project_id)
        apply_provenance(row, None, creating=True)
        db.add(row)
    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    for key, value in data.items():
        setattr(row, key, value)
    apply_provenance(row, payload.provenance, creating=creating)
    if not creating:
        bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return serialize_client_input(row)


def get_client_input(db: Session, project_id: UUID) -> ClientInputOut:
    _get_project(db, project_id)
    row = db.execute(
        select(ClientInput).where(ClientInput.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Client input not found", field="client_input")
    return serialize_client_input(row)


def update_client_input(
    db: Session, project_id: UUID, payload: ClientInputUpsert
) -> ClientInputOut:
    row = db.execute(
        select(ClientInput).where(ClientInput.project_id == project_id)
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Client input not found", field="client_input")
    if payload.requested_subject_count is not None and payload.requested_subject_count <= 0:
        raise ValidationError(
            "requested_subject_count must be > 0 when supplied",
            field="requested_subject_count",
        )
    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    for key, value in data.items():
        setattr(row, key, value)
    apply_provenance(row, payload.provenance)
    bump_entity_version(row)
    db.commit()
    db.refresh(row)
    return serialize_client_input(row)

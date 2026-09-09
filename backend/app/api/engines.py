from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
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
from app.services import study_engine_service as eng

router = APIRouter(tags=["study-engines"])


@router.post("/projects/{project_id}/design", response_model=DesignOut, status_code=201)
def create_design(project_id: UUID, payload: DesignCreate, db: Session = Depends(get_db)) -> DesignOut:
    return eng.create_design(db, project_id, payload)


@router.get("/projects/{project_id}/design", response_model=DesignOut)
def get_design(project_id: UUID, db: Session = Depends(get_db)) -> DesignOut:
    return eng.get_design(db, project_id)


@router.patch("/projects/{project_id}/design", response_model=DesignOut)
def update_design(project_id: UUID, payload: DesignUpdate, db: Session = Depends(get_db)) -> DesignOut:
    return eng.update_design(db, project_id, payload)


@router.post("/projects/{project_id}/design/recommend", response_model=DesignRecommendResponse)
def recommend_design(
    project_id: UUID, payload: DesignRecommendRequest, db: Session = Depends(get_db)
) -> DesignRecommendResponse:
    return eng.recommend_and_optionally_persist(db, project_id, payload)


@router.post("/projects/{project_id}/food", response_model=FoodOut, status_code=201)
def create_food(project_id: UUID, payload: FoodUpsert, db: Session = Depends(get_db)) -> FoodOut:
    return eng.upsert_food(db, project_id, payload)


@router.get("/projects/{project_id}/food", response_model=FoodOut)
def get_food(project_id: UUID, db: Session = Depends(get_db)) -> FoodOut:
    return eng.get_food(db, project_id)


@router.patch("/projects/{project_id}/food", response_model=FoodOut)
def update_food(project_id: UUID, payload: FoodUpdate, db: Session = Depends(get_db)) -> FoodOut:
    return eng.update_food(db, project_id, payload)


@router.get("/projects/{project_id}/eligibility", response_model=EligibilityOut)
def get_eligibility(project_id: UUID, db: Session = Depends(get_db)) -> EligibilityOut:
    return eng.get_eligibility(db, project_id)


@router.put("/projects/{project_id}/eligibility", response_model=EligibilityOut)
def replace_eligibility(
    project_id: UUID, payload: EligibilityReplace, db: Session = Depends(get_db)
) -> EligibilityOut:
    return eng.replace_eligibility(db, project_id, payload)


@router.post(
    "/projects/{project_id}/eligibility/criteria",
    response_model=CriterionOut,
    status_code=201,
)
def create_criterion(
    project_id: UUID, payload: CriterionCreate, db: Session = Depends(get_db)
) -> CriterionOut:
    return eng.create_criterion(db, project_id, payload)


@router.patch(
    "/projects/{project_id}/eligibility/criteria/{criterion_id}",
    response_model=CriterionOut,
)
def update_criterion(
    project_id: UUID,
    criterion_id: UUID,
    payload: CriterionUpdate,
    db: Session = Depends(get_db),
) -> CriterionOut:
    return eng.update_criterion(db, project_id, criterion_id, payload)


@router.delete(
    "/projects/{project_id}/eligibility/criteria/{criterion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_criterion(
    project_id: UUID, criterion_id: UUID, db: Session = Depends(get_db)
) -> Response:
    eng.delete_criterion(db, project_id, criterion_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/projects/{project_id}/subjects", response_model=SubjectPlanOut, status_code=201)
def create_subjects(
    project_id: UUID, payload: SubjectPlanUpsert, db: Session = Depends(get_db)
) -> SubjectPlanOut:
    return eng.upsert_subjects(db, project_id, payload)


@router.get("/projects/{project_id}/subjects", response_model=SubjectPlanOut)
def get_subjects(project_id: UUID, db: Session = Depends(get_db)) -> SubjectPlanOut:
    return eng.get_subjects(db, project_id)


@router.patch("/projects/{project_id}/subjects", response_model=SubjectPlanOut)
def update_subjects(
    project_id: UUID, payload: SubjectPlanUpdate, db: Session = Depends(get_db)
) -> SubjectPlanOut:
    return eng.update_subjects(db, project_id, payload)


@router.post("/projects/{project_id}/client-input", response_model=ClientInputOut, status_code=201)
def create_client_input(
    project_id: UUID, payload: ClientInputUpsert, db: Session = Depends(get_db)
) -> ClientInputOut:
    return eng.upsert_client_input(db, project_id, payload)


@router.get("/projects/{project_id}/client-input", response_model=ClientInputOut)
def get_client_input(project_id: UUID, db: Session = Depends(get_db)) -> ClientInputOut:
    return eng.get_client_input(db, project_id)


@router.patch("/projects/{project_id}/client-input", response_model=ClientInputOut)
def update_client_input(
    project_id: UUID, payload: ClientInputUpsert, db: Session = Depends(get_db)
) -> ClientInputOut:
    return eng.update_client_input(db, project_id, payload)

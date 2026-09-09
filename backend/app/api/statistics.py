from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
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
    StatisticsValidateOut,
)
from app.services import statistics_service as stats

router = APIRouter(tags=["statistics"])


@router.post("/projects/{project_id}/statistics/cv", response_model=CVStudyOut, status_code=201)
def create_cv(project_id: UUID, payload: CVStudyCreate, db: Session = Depends(get_db)) -> CVStudyOut:
    return stats.create_cv_study(db, project_id, payload)


@router.get("/projects/{project_id}/statistics/cv", response_model=list[CVStudyOut])
def list_cv(project_id: UUID, db: Session = Depends(get_db)) -> list[CVStudyOut]:
    return stats.list_cv_studies(db, project_id)


@router.post("/projects/{project_id}/statistics/cv/pool", response_model=CVPoolOut)
def pool_cv(project_id: UUID, payload: CVPoolRequest, db: Session = Depends(get_db)) -> CVPoolOut:
    return stats.pool_cv_studies(db, project_id, payload)


@router.post("/projects/{project_id}/statistics/cv/select", response_model=CVSelectionOut)
def select_cv(
    project_id: UUID, payload: CVSelectRequest, db: Session = Depends(get_db)
) -> CVSelectionOut:
    return stats.select_cv(db, project_id, payload)


@router.get("/projects/{project_id}/statistics/cv/selection", response_model=CVSelectionOut)
def get_cv_selection(project_id: UUID, db: Session = Depends(get_db)) -> CVSelectionOut:
    return stats.get_cv_selection(db, project_id)


@router.post("/projects/{project_id}/statistics/sample-size", response_model=SampleSizeOut)
def calculate_sample_size(
    project_id: UUID, payload: SampleSizeRequest, db: Session = Depends(get_db)
) -> SampleSizeOut:
    return stats.calculate_and_store_sample_size(db, project_id, payload)


@router.get("/projects/{project_id}/statistics/sample-size", response_model=list[SampleSizeOut])
def list_sample_size(project_id: UUID, db: Session = Depends(get_db)) -> list[SampleSizeOut]:
    return stats.list_sample_sizes(db, project_id)


@router.post("/projects/{project_id}/statistics/validate", response_model=StatisticsValidateOut)
def validate_statistics(project_id: UUID, db: Session = Depends(get_db)) -> StatisticsValidateOut:
    return StatisticsValidateOut(**stats.validate_statistics(db, project_id))


@router.get("/projects/{project_id}/statistics/config", response_model=StatisticalConfigOut)
def get_statistics_config(
    project_id: UUID, db: Session = Depends(get_db)
) -> StatisticalConfigOut:
    return stats.get_statistical_config(db, project_id)

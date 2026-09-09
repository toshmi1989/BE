from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
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
    PKRecommendRequest,
    SamplingPatchRequest,
    SamplingPlanOut,
    SamplingRecommendRequest,
    WashoutCalculateRequest,
    WashoutOut,
)
from app.services import pk_engine_service as pk

router = APIRouter(tags=["pk-sampling"])


@router.post("/projects/{project_id}/analytes", response_model=AnalyteOut, status_code=201)
def create_analyte(project_id: UUID, payload: AnalyteCreate, db: Session = Depends(get_db)) -> AnalyteOut:
    return pk.create_analyte(db, project_id, payload)


@router.get("/projects/{project_id}/analytes", response_model=list[AnalyteOut])
def list_analytes(project_id: UUID, db: Session = Depends(get_db)) -> list[AnalyteOut]:
    return pk.list_analytes(db, project_id)


@router.patch("/projects/{project_id}/analytes/{analyte_id}", response_model=AnalyteOut)
def update_analyte(
    project_id: UUID, analyte_id: UUID, payload: AnalyteUpdate, db: Session = Depends(get_db)
) -> AnalyteOut:
    return pk.update_analyte(db, project_id, analyte_id, payload)


@router.delete("/projects/{project_id}/analytes/{analyte_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analyte(project_id: UUID, analyte_id: UUID, db: Session = Depends(get_db)) -> Response:
    pk.delete_analyte(db, project_id, analyte_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/projects/{project_id}/pk/parameters", response_model=PKParameterOut, status_code=201)
def create_pk_parameter(
    project_id: UUID, payload: PKParameterCreate, db: Session = Depends(get_db)
) -> PKParameterOut:
    return pk.create_pk_parameter(db, project_id, payload)


@router.get("/projects/{project_id}/pk/parameters", response_model=list[PKParameterOut])
def list_pk_parameters(project_id: UUID, db: Session = Depends(get_db)) -> list[PKParameterOut]:
    return pk.list_pk_parameters(db, project_id)


@router.post("/projects/{project_id}/pk/recommend")
def recommend_pk(
    project_id: UUID, payload: PKRecommendRequest, db: Session = Depends(get_db)
) -> dict:
    return pk.recommend_pk(db, project_id, persist=payload.persist)


@router.post("/projects/{project_id}/washout/calculate", response_model=WashoutOut)
def calculate_washout(
    project_id: UUID, payload: WashoutCalculateRequest, db: Session = Depends(get_db)
) -> WashoutOut:
    return pk.calculate_and_store_washout(db, project_id, payload)


@router.get("/projects/{project_id}/washout", response_model=WashoutOut)
def get_washout(project_id: UUID, db: Session = Depends(get_db)) -> WashoutOut:
    return pk.get_washout(db, project_id)


@router.post("/projects/{project_id}/observation/calculate", response_model=ObservationOut)
def calculate_observation(
    project_id: UUID, payload: ObservationCalculateRequest, db: Session = Depends(get_db)
) -> ObservationOut:
    return pk.calculate_and_store_observation(db, project_id, payload)


@router.get("/projects/{project_id}/observation", response_model=ObservationOut)
def get_observation(project_id: UUID, db: Session = Depends(get_db)) -> ObservationOut:
    return pk.get_observation(db, project_id)


@router.post("/projects/{project_id}/sampling/recommend", response_model=SamplingPlanOut)
def recommend_sampling(
    project_id: UUID, payload: SamplingRecommendRequest, db: Session = Depends(get_db)
) -> SamplingPlanOut:
    return pk.recommend_sampling(db, project_id, payload)


@router.get("/projects/{project_id}/sampling", response_model=SamplingPlanOut)
def get_sampling(project_id: UUID, db: Session = Depends(get_db)) -> SamplingPlanOut:
    return pk.get_sampling(db, project_id)


@router.patch("/projects/{project_id}/sampling", response_model=SamplingPlanOut)
def patch_sampling(
    project_id: UUID, payload: SamplingPatchRequest, db: Session = Depends(get_db)
) -> SamplingPlanOut:
    return pk.patch_sampling(db, project_id, payload)


@router.post("/projects/{project_id}/sampling/validate")
def validate_sampling(project_id: UUID, db: Session = Depends(get_db)) -> dict:
    return pk.validate_sampling(db, project_id)


@router.post("/projects/{project_id}/blood-volume/calculate", response_model=BloodVolumeOut)
def calculate_blood(
    project_id: UUID, payload: BloodVolumeCalculateRequest, db: Session = Depends(get_db)
) -> BloodVolumeOut:
    return pk.calculate_and_store_blood(db, project_id, payload)


@router.get("/projects/{project_id}/blood-volume", response_model=BloodVolumeOut)
def get_blood(project_id: UUID, db: Session = Depends(get_db)) -> BloodVolumeOut:
    return pk.get_blood_volume(db, project_id)

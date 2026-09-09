from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.project import (
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
    PersonCreate,
    PersonOut,
    PersonUpdate,
    ProductOut,
    ProductUpsert,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdate,
    ProjectVersionCreate,
    ProjectVersionOut,
    ReferenceProductOut,
    ReferenceProductUpsert,
    SourceCreate,
    SourceOut,
    SourceUpdate,
    SponsorOut,
    SponsorUpsert,
    StudyOut,
    StudyUpsert,
    StudyAdministrationOut,
    StudyAdministrationUpsert,
)
from app.services import project_service as svc

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectDetail:
    return svc.create_project(db, payload)


@router.get("/projects", response_model=list[ProjectSummary])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectSummary]:
    return svc.list_projects(db)


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: UUID, db: Session = Depends(get_db)) -> ProjectDetail:
    return svc.get_project(db, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectDetail)
def update_project(
    project_id: UUID, payload: ProjectUpdate, db: Session = Depends(get_db)
) -> ProjectDetail:
    return svc.update_project(db, project_id, payload)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: UUID, db: Session = Depends(get_db)) -> Response:
    svc.delete_project(db, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/projects/{project_id}/study", response_model=StudyOut)
def upsert_study(project_id: UUID, payload: StudyUpsert, db: Session = Depends(get_db)) -> StudyOut:
    return svc.upsert_study(db, project_id, payload)


@router.put("/projects/{project_id}/sponsor", response_model=SponsorOut)
def upsert_sponsor(
    project_id: UUID, payload: SponsorUpsert, db: Session = Depends(get_db)
) -> SponsorOut:
    return svc.upsert_sponsor(db, project_id, payload)


@router.get("/projects/{project_id}/organizations", response_model=list[OrganizationOut])
def list_organizations(project_id: UUID, db: Session = Depends(get_db)) -> list[OrganizationOut]:
    return svc.list_organizations(db, project_id)


@router.post(
    "/projects/{project_id}/organizations",
    response_model=OrganizationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    project_id: UUID, payload: OrganizationCreate, db: Session = Depends(get_db)
) -> OrganizationOut:
    return svc.create_organization(db, project_id, payload)


@router.patch("/projects/{project_id}/organizations/{org_id}", response_model=OrganizationOut)
def update_organization(
    project_id: UUID,
    org_id: UUID,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
) -> OrganizationOut:
    return svc.update_organization(db, project_id, org_id, payload)


@router.delete(
    "/projects/{project_id}/organizations/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_organization(project_id: UUID, org_id: UUID, db: Session = Depends(get_db)) -> Response:
    svc.delete_organization(db, project_id, org_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/persons", response_model=list[PersonOut])
def list_persons(project_id: UUID, db: Session = Depends(get_db)) -> list[PersonOut]:
    return svc.list_persons(db, project_id)


@router.post(
    "/projects/{project_id}/persons",
    response_model=PersonOut,
    status_code=status.HTTP_201_CREATED,
)
def create_person(
    project_id: UUID, payload: PersonCreate, db: Session = Depends(get_db)
) -> PersonOut:
    return svc.create_person(db, project_id, payload)


@router.patch("/projects/{project_id}/persons/{person_id}", response_model=PersonOut)
def update_person(
    project_id: UUID,
    person_id: UUID,
    payload: PersonUpdate,
    db: Session = Depends(get_db),
) -> PersonOut:
    return svc.update_person(db, project_id, person_id, payload)


@router.delete(
    "/projects/{project_id}/persons/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_person(project_id: UUID, person_id: UUID, db: Session = Depends(get_db)) -> Response:
    svc.delete_person(db, project_id, person_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/projects/{project_id}/study-administration", response_model=StudyAdministrationOut)
def upsert_study_administration(
    project_id: UUID, payload: StudyAdministrationUpsert, db: Session = Depends(get_db)
) -> StudyAdministrationOut:
    return svc.upsert_study_administration(db, project_id, payload)


@router.put("/projects/{project_id}/product", response_model=ProductOut)
def upsert_product(
    project_id: UUID, payload: ProductUpsert, db: Session = Depends(get_db)
) -> ProductOut:
    return svc.upsert_product(db, project_id, payload)


@router.put("/projects/{project_id}/reference-product", response_model=ReferenceProductOut)
def upsert_reference_product(
    project_id: UUID, payload: ReferenceProductUpsert, db: Session = Depends(get_db)
) -> ReferenceProductOut:
    return svc.upsert_reference_product(db, project_id, payload)


@router.get("/projects/{project_id}/sources", response_model=list[SourceOut])
def list_sources(project_id: UUID, db: Session = Depends(get_db)) -> list[SourceOut]:
    return svc.list_sources(db, project_id)


@router.post(
    "/projects/{project_id}/sources",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    project_id: UUID, payload: SourceCreate, db: Session = Depends(get_db)
) -> SourceOut:
    return svc.create_source(db, project_id, payload)


@router.patch("/projects/{project_id}/sources/{source_id}", response_model=SourceOut)
def update_source(
    project_id: UUID,
    source_id: UUID,
    payload: SourceUpdate,
    db: Session = Depends(get_db),
) -> SourceOut:
    return svc.update_source(db, project_id, source_id, payload)


@router.delete(
    "/projects/{project_id}/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_source(project_id: UUID, source_id: UUID, db: Session = Depends(get_db)) -> Response:
    svc.delete_source(db, project_id, source_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/versions", response_model=list[ProjectVersionOut])
def list_versions(project_id: UUID, db: Session = Depends(get_db)) -> list[ProjectVersionOut]:
    return svc.list_project_versions(db, project_id)


@router.post(
    "/projects/{project_id}/versions",
    response_model=ProjectVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_version(
    project_id: UUID, payload: ProjectVersionCreate, db: Session = Depends(get_db)
) -> ProjectVersionOut:
    return svc.create_project_version(db, project_id, payload)

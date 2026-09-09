from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.domain.constants import RULES_CATALOG_VERSION, SCHEMA_VERSION
from app.domain.exceptions import ConflictError, NotFoundError, ProvenanceGuardError
from app.models import (
    Organization,
    Person,
    Product,
    Project,
    ProjectVersion,
    ReferenceProduct,
    SamplingPlan,
    Source,
    Sponsor,
    Study,
    StudyAdministration,
)
from app.schemas.common import provenance_from_orm
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
from app.services.provenance import apply_provenance, bump_entity_version, with_provenance
from app.services.study_engine_service import (
    serialize_client_input,
    serialize_design,
    serialize_food,
    serialize_subjects,
)
from app.services.pk_engine_service import (
    serialize_analyte,
    serialize_blood,
    serialize_observation,
    serialize_pk,
    serialize_sampling,
    serialize_washout,
)


def _get_project(db: Session, project_id: UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise NotFoundError("Project not found", field="project_id")
    return project


def _load_project(db: Session, project_id: UUID) -> Project:
    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.study),
            selectinload(Project.sponsor),
            selectinload(Project.organizations),
            selectinload(Project.persons),
            selectinload(Project.study_administration),
            selectinload(Project.product),
            selectinload(Project.reference_product),
            selectinload(Project.sources),
            selectinload(Project.versions),
            selectinload(Project.client_input),
            selectinload(Project.design),
            selectinload(Project.food),
            selectinload(Project.eligibility_criteria),
            selectinload(Project.subjects),
            selectinload(Project.analytes),
            selectinload(Project.pk_parameters),
            selectinload(Project.washout),
            selectinload(Project.observation),
            selectinload(Project.sampling).selectinload(SamplingPlan.points),
            selectinload(Project.blood_volume),
            selectinload(Project.cv_studies),
            selectinload(Project.cv_pools),
            selectinload(Project.cv_selection),
            selectinload(Project.statistical_config),
            selectinload(Project.sample_size_calculations),
        )
    )
    project = db.execute(stmt).scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project not found", field="project_id")
    return project


def serialize_study(study: Study) -> StudyOut:
    return with_provenance(StudyOut, study)


def serialize_sponsor(sponsor: Sponsor) -> SponsorOut:
    return with_provenance(SponsorOut, sponsor)


def serialize_organization(org: Organization) -> OrganizationOut:
    return with_provenance(OrganizationOut, org)


def serialize_person(person: Person) -> PersonOut:
    return with_provenance(PersonOut, person)


def serialize_study_administration(row: StudyAdministration) -> StudyAdministrationOut:
    return with_provenance(StudyAdministrationOut, row)


def serialize_product(product: Product) -> ProductOut:
    return with_provenance(ProductOut, product)


def serialize_reference(ref: ReferenceProduct) -> ReferenceProductOut:
    return with_provenance(ReferenceProductOut, ref)


def serialize_source(source: Source) -> SourceOut:
    return with_provenance(SourceOut, source)


def serialize_project_detail(project: Project) -> ProjectDetail:
    from app.schemas.phase2 import EligibilityOut
    from app.services.statistics_service import (
        serialize_config,
        serialize_cv,
        serialize_pool,
        serialize_sample_size,
        serialize_selection,
    )
    from app.services.study_engine_service import serialize_criterion

    eligibility = EligibilityOut()
    for row in project.eligibility_criteria or []:
        getattr(eligibility, row.category).append(serialize_criterion(row))

    sample_sizes = sorted(
        project.sample_size_calculations or [],
        key=lambda r: r.created_at,
        reverse=True,
    )
    latest_ss = serialize_sample_size(sample_sizes[0]) if sample_sizes else None

    return ProjectDetail(
        id=project.id,
        name=project.name,
        status=project.status,
        schema_version=project.schema_version,
        description=project.description,
        entity_version=project.entity_version,
        created_at=project.created_at,
        updated_at=project.updated_at,
        study=serialize_study(project.study) if project.study else None,
        sponsor=serialize_sponsor(project.sponsor) if project.sponsor else None,
        organizations=[serialize_organization(o) for o in project.organizations],
        persons=[serialize_person(p) for p in (project.persons or [])],
        study_administration=(
            serialize_study_administration(project.study_administration)
            if project.study_administration
            else None
        ),
        product=serialize_product(project.product) if project.product else None,
        reference_product=(
            serialize_reference(project.reference_product) if project.reference_product else None
        ),
        sources=[serialize_source(s) for s in project.sources],
        versions=[ProjectVersionOut.model_validate(v) for v in project.versions],
        client_input=serialize_client_input(project.client_input) if project.client_input else None,
        design=serialize_design(project.design) if project.design else None,
        food=serialize_food(project.food) if project.food else None,
        eligibility=eligibility,
        subjects=serialize_subjects(project.subjects) if project.subjects else None,
        analytes=[serialize_analyte(a) for a in (project.analytes or [])],
        pk_parameters=[serialize_pk(p) for p in (project.pk_parameters or [])],
        washout=serialize_washout(project.washout) if project.washout else None,
        observation=serialize_observation(project.observation) if project.observation else None,
        sampling=serialize_sampling(project.sampling) if project.sampling else None,
        blood_volume=serialize_blood(project.blood_volume) if project.blood_volume else None,
        cv_studies=[serialize_cv(c) for c in (project.cv_studies or [])],
        cv_pools=[serialize_pool(p) for p in (project.cv_pools or [])],
        cv_selection=serialize_selection(project.cv_selection) if project.cv_selection else None,
        statistical_config=(
            serialize_config(project.statistical_config) if project.statistical_config else None
        ),
        sample_size=latest_ss,
        sample_size_calculations=[serialize_sample_size(s) for s in sample_sizes],
    )


def create_project(db: Session, payload: ProjectCreate) -> ProjectDetail:
    project = Project(name=payload.name, description=payload.description)
    db.add(project)
    db.flush()

    study = Study(project_id=project.id)
    apply_provenance(study, None, creating=True)
    db.add(study)
    db.commit()
    return serialize_project_detail(_load_project(db, project.id))


def list_projects(db: Session) -> list[ProjectSummary]:
    rows = db.execute(select(Project).order_by(Project.created_at.desc())).scalars().all()
    return [ProjectSummary.model_validate(p) for p in rows]


def get_project(db: Session, project_id: UUID) -> ProjectDetail:
    return serialize_project_detail(_load_project(db, project_id))


def update_project(db: Session, project_id: UUID, payload: ProjectUpdate) -> ProjectDetail:
    project = _get_project(db, project_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(project, key, value)
    bump_entity_version(project)
    db.commit()
    return serialize_project_detail(_load_project(db, project_id))


def delete_project(db: Session, project_id: UUID) -> None:
    project = _get_project(db, project_id)
    db.delete(project)
    db.commit()


def upsert_study(db: Session, project_id: UUID, payload: StudyUpsert) -> StudyOut:
    _get_project(db, project_id)
    study = db.execute(select(Study).where(Study.project_id == project_id)).scalar_one_or_none()
    creating = study is None
    if creating:
        study = Study(project_id=project_id)
        apply_provenance(study, None, creating=True)
        db.add(study)

    if payload.sponsor_id is not None:
        sponsor = db.get(Sponsor, payload.sponsor_id)
        if sponsor is None or sponsor.project_id != project_id:
            raise ConflictError("sponsor_id must belong to the same project", field="sponsor_id")

    data = payload.model_dump(exclude_unset=True, exclude={"provenance", "sponsor_id"})
    for key, value in data.items():
        setattr(study, key, value)
    if "sponsor_id" in payload.model_fields_set:
        study.sponsor_id = payload.sponsor_id

    apply_provenance(study, payload.provenance, creating=creating)
    if not creating:
        bump_entity_version(study)
    db.commit()
    db.refresh(study)
    return serialize_study(study)


def upsert_sponsor(db: Session, project_id: UUID, payload: SponsorUpsert) -> SponsorOut:
    _get_project(db, project_id)
    sponsor = db.execute(select(Sponsor).where(Sponsor.project_id == project_id)).scalar_one_or_none()
    creating = sponsor is None
    if creating:
        sponsor = Sponsor(project_id=project_id, name=payload.name)
        apply_provenance(sponsor, None, creating=True)
        db.add(sponsor)

    if payload.organization_id is not None:
        org = db.get(Organization, payload.organization_id)
        if org is None or org.project_id != project_id:
            raise ConflictError(
                "organization_id must belong to the same project", field="organization_id"
            )

    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    for key, value in data.items():
        setattr(sponsor, key, value)

    apply_provenance(sponsor, payload.provenance, creating=creating)
    if not creating:
        bump_entity_version(sponsor)

    # Keep Study.sponsor_id linked when study exists
    study = db.execute(select(Study).where(Study.project_id == project_id)).scalar_one_or_none()
    if study is not None and study.sponsor_id is None:
        study.sponsor_id = sponsor.id

    db.commit()
    db.refresh(sponsor)
    return serialize_sponsor(sponsor)


def create_organization(db: Session, project_id: UUID, payload: OrganizationCreate) -> OrganizationOut:
    _get_project(db, project_id)
    org = Organization(
        project_id=project_id,
        name=payload.name,
        role=payload.role,
        country=payload.country,
        address=payload.address,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
    )
    apply_provenance(org, payload.provenance, creating=True)
    db.add(org)
    db.commit()
    db.refresh(org)
    return serialize_organization(org)


def list_organizations(db: Session, project_id: UUID) -> list[OrganizationOut]:
    _get_project(db, project_id)
    rows = (
        db.execute(select(Organization).where(Organization.project_id == project_id))
        .scalars()
        .all()
    )
    return [serialize_organization(o) for o in rows]


def update_organization(
    db: Session, project_id: UUID, org_id: UUID, payload: OrganizationUpdate
) -> OrganizationOut:
    org = db.get(Organization, org_id)
    if org is None or org.project_id != project_id:
        raise NotFoundError("Organization not found", field="organization_id")
    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    for key, value in data.items():
        setattr(org, key, value)
    apply_provenance(org, payload.provenance)
    bump_entity_version(org)
    db.commit()
    db.refresh(org)
    return serialize_organization(org)


def delete_organization(db: Session, project_id: UUID, org_id: UUID) -> None:
    org = db.get(Organization, org_id)
    if org is None or org.project_id != project_id:
        raise NotFoundError("Organization not found", field="organization_id")
    db.delete(org)
    db.commit()


def create_person(db: Session, project_id: UUID, payload: PersonCreate) -> PersonOut:
    _get_project(db, project_id)
    if payload.organization_id is not None:
        org = db.get(Organization, payload.organization_id)
        if org is None or org.project_id != project_id:
            raise ConflictError("organization_id must belong to the same project", field="organization_id")
    person = Person(
        project_id=project_id,
        role=payload.role,
        full_name=payload.full_name,
        title=payload.title,
        phone=payload.phone,
        email=payload.email,
        organization_id=payload.organization_id,
        notes=payload.notes,
    )
    apply_provenance(person, payload.provenance, creating=True)
    db.add(person)
    db.commit()
    db.refresh(person)
    return serialize_person(person)


def list_persons(db: Session, project_id: UUID) -> list[PersonOut]:
    _get_project(db, project_id)
    rows = db.execute(select(Person).where(Person.project_id == project_id)).scalars().all()
    return [serialize_person(p) for p in rows]


def update_person(db: Session, project_id: UUID, person_id: UUID, payload: PersonUpdate) -> PersonOut:
    person = db.get(Person, person_id)
    if person is None or person.project_id != project_id:
        raise NotFoundError("Person not found", field="person_id")
    if payload.organization_id is not None:
        org = db.get(Organization, payload.organization_id)
        if org is None or org.project_id != project_id:
            raise ConflictError("organization_id must belong to the same project", field="organization_id")
    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    for key, value in data.items():
        setattr(person, key, value)
    apply_provenance(person, payload.provenance)
    bump_entity_version(person)
    db.commit()
    db.refresh(person)
    return serialize_person(person)


def delete_person(db: Session, project_id: UUID, person_id: UUID) -> None:
    person = db.get(Person, person_id)
    if person is None or person.project_id != project_id:
        raise NotFoundError("Person not found", field="person_id")
    db.delete(person)
    db.commit()


def upsert_study_administration(
    db: Session, project_id: UUID, payload: StudyAdministrationUpsert
) -> StudyAdministrationOut:
    _get_project(db, project_id)
    row = db.execute(
        select(StudyAdministration).where(StudyAdministration.project_id == project_id)
    ).scalar_one_or_none()
    creating = row is None
    if creating:
        row = StudyAdministration(project_id=project_id)
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
    return serialize_study_administration(row)


def upsert_product(db: Session, project_id: UUID, payload: ProductUpsert) -> ProductOut:
    _get_project(db, project_id)
    product = db.execute(select(Product).where(Product.project_id == project_id)).scalar_one_or_none()
    creating = product is None
    if creating:
        product = Product(project_id=project_id, composition=[])
        apply_provenance(product, None, creating=True)
        db.add(product)

    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    for key, value in data.items():
        setattr(product, key, value if value is not None or key != "composition" else [])
    if "composition" in data and data["composition"] is None:
        product.composition = []

    apply_provenance(product, payload.provenance, creating=creating)
    if not creating:
        bump_entity_version(product)
    db.commit()
    db.refresh(product)
    return serialize_product(product)


def upsert_reference_product(
    db: Session, project_id: UUID, payload: ReferenceProductUpsert
) -> ReferenceProductOut:
    _get_project(db, project_id)
    ref = db.execute(
        select(ReferenceProduct).where(ReferenceProduct.project_id == project_id)
    ).scalar_one_or_none()
    creating = ref is None
    if creating:
        ref = ReferenceProduct(project_id=project_id, composition=[], purchased_status="UNKNOWN")
        apply_provenance(ref, None, creating=True)
        db.add(ref)

    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    for key, value in data.items():
        setattr(ref, key, value)
    if "composition" in data and data["composition"] is None:
        ref.composition = []

    apply_provenance(ref, payload.provenance, creating=creating)
    if not creating:
        bump_entity_version(ref)
    db.commit()
    db.refresh(ref)
    return serialize_reference(ref)


def create_source(db: Session, project_id: UUID, payload: SourceCreate) -> SourceOut:
    _get_project(db, project_id)
    source = Source(
        project_id=project_id,
        type=payload.type,
        title=payload.title,
        authors=payload.authors or [],
        year=payload.year,
        url=payload.url,
        file_id=payload.file_id,
        page=payload.page,
        section=payload.section,
        checksum=payload.checksum,
        verified=payload.verified,
    )
    apply_provenance(source, payload.provenance, creating=True)
    db.add(source)
    db.commit()
    db.refresh(source)
    return serialize_source(source)


def list_sources(db: Session, project_id: UUID) -> list[SourceOut]:
    _get_project(db, project_id)
    rows = db.execute(select(Source).where(Source.project_id == project_id)).scalars().all()
    return [serialize_source(s) for s in rows]


def update_source(db: Session, project_id: UUID, source_id: UUID, payload: SourceUpdate) -> SourceOut:
    source = db.get(Source, source_id)
    if source is None or source.project_id != project_id:
        raise NotFoundError("Source not found", field="source_id")
    data = payload.model_dump(exclude_unset=True, exclude={"provenance"})
    for key, value in data.items():
        setattr(source, key, value)
    if "authors" in data and data["authors"] is None:
        source.authors = []
    apply_provenance(source, payload.provenance)
    bump_entity_version(source)
    db.commit()
    db.refresh(source)
    return serialize_source(source)


def delete_source(db: Session, project_id: UUID, source_id: UUID) -> None:
    source = db.get(Source, source_id)
    if source is None or source.project_id != project_id:
        raise NotFoundError("Source not found", field="source_id")
    db.delete(source)
    db.commit()


def _build_snapshot(project: Project) -> dict:
    detail = serialize_project_detail(project)
    return detail.model_dump(mode="json")


def create_project_version(
    db: Session, project_id: UUID, payload: ProjectVersionCreate
) -> ProjectVersionOut:
    project = _load_project(db, project_id)
    next_number = (max((v.version_number for v in project.versions), default=0) + 1)
    version = ProjectVersion(
        project_id=project.id,
        version_number=next_number,
        label=payload.label,
        schema_version=project.schema_version or SCHEMA_VERSION,
        ruleset_version=RULES_CATALOG_VERSION,
        snapshot=_build_snapshot(project),
    )
    db.add(version)
    bump_entity_version(project)
    db.commit()
    db.refresh(version)
    return ProjectVersionOut.model_validate(version)


def list_project_versions(db: Session, project_id: UUID) -> list[ProjectVersionOut]:
    _get_project(db, project_id)
    rows = (
        db.execute(
            select(ProjectVersion)
            .where(ProjectVersion.project_id == project_id)
            .order_by(ProjectVersion.version_number)
        )
        .scalars()
        .all()
    )
    return [ProjectVersionOut.model_validate(v) for v in rows]


# re-export for tests
__all__ = [
    "ConflictError",
    "NotFoundError",
    "ProvenanceGuardError",
    "create_person",
    "create_organization",
    "create_project",
    "create_project_version",
    "create_source",
    "delete_person",
    "delete_organization",
    "delete_project",
    "delete_source",
    "get_project",
    "list_persons",
    "list_organizations",
    "list_project_versions",
    "list_projects",
    "list_sources",
    "provenance_from_orm",
    "serialize_project_detail",
    "update_person",
    "update_organization",
    "update_project",
    "update_source",
    "upsert_product",
    "upsert_reference_product",
    "upsert_study_administration",
    "upsert_sponsor",
    "upsert_study",
]

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ProvenanceIn, ProvenanceOut


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = None


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    schema_version: str
    description: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime


class StudyUpsert(BaseModel):
    protocol_number: str | None = None
    version: str | None = None
    version_date: str | None = None
    title: str | None = None
    short_title: str | None = None
    country: str | None = None
    phase: str | None = None
    study_status: str | None = None
    sponsor_id: UUID | None = None
    provenance: ProvenanceIn | None = None


class StudyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    sponsor_id: UUID | None
    protocol_number: str | None
    version: str
    version_date: str | None
    title: str | None
    short_title: str | None
    country: str | None
    phase: str
    study_status: str
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class SponsorUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    country: str | None = None
    address: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    organization_id: UUID | None = None
    provenance: ProvenanceIn | None = None


class SponsorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    organization_id: UUID | None
    name: str
    country: str | None
    address: str | None
    contact_email: str | None
    contact_phone: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: str = "OTHER"
    country: str | None = None
    address: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    provenance: ProvenanceIn | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = None
    country: str | None = None
    address: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    provenance: ProvenanceIn | None = None


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    role: str
    country: str | None
    address: str | None
    contact_email: str | None
    contact_phone: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class PersonCreate(BaseModel):
    role: str = Field(min_length=1, max_length=64)
    full_name: str = Field(min_length=1, max_length=255)
    title: str | None = None
    phone: str | None = None
    email: str | None = None
    organization_id: UUID | None = None
    notes: str | None = None
    provenance: ProvenanceIn | None = None


class PersonUpdate(BaseModel):
    role: str | None = Field(default=None, min_length=1, max_length=64)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = None
    phone: str | None = None
    email: str | None = None
    organization_id: UUID | None = None
    notes: str | None = None
    provenance: ProvenanceIn | None = None


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    organization_id: UUID | None
    role: str
    full_name: str
    title: str | None
    phone: str | None
    email: str | None
    notes: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class StudyAdministrationUpsert(BaseModel):
    insurance_provider: str | None = None
    insurance_policy: str | None = None
    insurance_details: str | None = None
    financing_source: str | None = None
    financing_details: str | None = None
    publication_policy: str | None = None
    publication_contacts: str | None = None
    provenance: ProvenanceIn | None = None


class StudyAdministrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    insurance_provider: str | None
    insurance_policy: str | None
    insurance_details: str | None
    financing_source: str | None
    financing_details: str | None
    publication_policy: str | None
    publication_contacts: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class ProductUpsert(BaseModel):
    trade_name: str | None = None
    inn: str | None = None
    manufacturer: str | None = None
    manufacturer_country: str | None = None
    registration_holder: str | None = None
    registration_number: str | None = None
    dosage: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    pharmacological_group: str | None = None
    composition: list | None = None
    storage_conditions: str | None = None
    shelf_life: str | None = None
    batch_number: str | None = None
    packaging: str | None = None
    provenance: ProvenanceIn | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    trade_name: str | None
    inn: str | None
    manufacturer: str | None
    manufacturer_country: str | None
    registration_holder: str | None
    registration_number: str | None
    dosage: str | None
    dosage_form: str | None
    route: str | None
    pharmacological_group: str | None
    composition: list
    storage_conditions: str | None
    shelf_life: str | None
    batch_number: str | None
    packaging: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class ReferenceProductUpsert(BaseModel):
    trade_name: str | None = None
    inn: str | None = None
    manufacturer: str | None = None
    country: str | None = None
    registration_holder: str | None = None
    registration_number: str | None = None
    dosage: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    composition: list | None = None
    storage_conditions: str | None = None
    shelf_life: str | None = None
    registration_status: str | None = None
    purchased_status: str | None = None
    batch_number: str | None = None
    packaging: str | None = None
    provenance: ProvenanceIn | None = None


class ReferenceProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    trade_name: str | None
    inn: str | None
    manufacturer: str | None
    country: str | None
    registration_holder: str | None
    registration_number: str | None
    dosage: str | None
    dosage_form: str | None
    route: str | None
    composition: list
    storage_conditions: str | None
    shelf_life: str | None
    registration_status: str | None
    purchased_status: str
    batch_number: str | None
    packaging: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class SourceCreate(BaseModel):
    type: str = "OTHER"
    title: str = Field(min_length=1, max_length=512)
    authors: list | None = None
    year: int | None = None
    url: str | None = None
    file_id: str | None = None
    page: int | None = None
    section: str | None = None
    checksum: str | None = None
    verified: bool = False
    provenance: ProvenanceIn | None = None


class SourceUpdate(BaseModel):
    type: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=512)
    authors: list | None = None
    year: int | None = None
    url: str | None = None
    file_id: str | None = None
    page: int | None = None
    section: str | None = None
    checksum: str | None = None
    verified: bool | None = None
    provenance: ProvenanceIn | None = None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    type: str
    title: str
    authors: list
    year: int | None
    url: str | None
    file_id: str | None
    page: int | None
    section: str | None
    checksum: str | None
    verified: bool
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class ProjectVersionCreate(BaseModel):
    label: str | None = None


class ProjectVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    version_number: int
    label: str | None
    schema_version: str
    ruleset_version: str
    snapshot: dict
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectSummary):
    study: StudyOut | None = None
    sponsor: SponsorOut | None = None
    organizations: list[OrganizationOut] = Field(default_factory=list)
    persons: list[PersonOut] = Field(default_factory=list)
    study_administration: StudyAdministrationOut | None = None
    product: ProductOut | None = None
    reference_product: ReferenceProductOut | None = None
    sources: list[SourceOut] = Field(default_factory=list)
    versions: list[ProjectVersionOut] = Field(default_factory=list)
    client_input: Any | None = None
    design: Any | None = None
    food: Any | None = None
    eligibility: Any | None = None
    subjects: Any | None = None
    analytes: list[Any] = Field(default_factory=list)
    pk_parameters: list[Any] = Field(default_factory=list)
    washout: Any | None = None
    observation: Any | None = None
    sampling: Any | None = None
    blood_volume: Any | None = None
    cv_studies: list[Any] = Field(default_factory=list)
    cv_pools: list[Any] = Field(default_factory=list)
    cv_selection: Any | None = None
    statistical_config: Any | None = None
    sample_size: Any | None = None
    sample_size_calculations: list[Any] = Field(default_factory=list)

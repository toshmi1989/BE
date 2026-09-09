from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ProvenanceIn, ProvenanceOut


class AnalyteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: str = "PARENT"
    active: bool = True
    matrix: str | None = None
    assay_method: str | None = None
    lloq: float | None = None
    uloq: float | None = None
    tmax_min: float | None = None
    tmax_max: float | None = None
    tmax_unit: str = "h"
    half_life_min: float | None = None
    half_life_max: float | None = None
    half_life_unit: str = "h"
    pk_parameter_codes: list[str] | None = None
    provenance: ProvenanceIn | None = None


class AnalyteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    type: str | None = None
    active: bool | None = None
    matrix: str | None = None
    assay_method: str | None = None
    lloq: float | None = None
    uloq: float | None = None
    tmax_min: float | None = None
    tmax_max: float | None = None
    tmax_unit: str | None = None
    half_life_min: float | None = None
    half_life_max: float | None = None
    half_life_unit: str | None = None
    pk_parameter_codes: list[str] | None = None
    provenance: ProvenanceIn | None = None


class AnalyteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    type: str
    active: bool
    matrix: str | None
    assay_method: str | None
    lloq: float | None
    uloq: float | None
    tmax_min: float | None
    tmax_max: float | None
    tmax_unit: str
    half_life_min: float | None
    half_life_max: float | None
    half_life_unit: str
    pk_parameter_codes: list
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class PKEvidenceIn(BaseModel):
    source_id: str
    page: int | str | None = None
    section: str | None = None
    extracted_text: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: str = "PROPOSED"


class PKParameterCreate(BaseModel):
    analyte_id: UUID
    parameter_code: str
    unit: str | None = None
    value_numeric: float | None = None
    range_min: float | None = None
    range_max: float | None = None
    calculated_value: float | None = None
    reference_text: str | None = None
    evidence: list[PKEvidenceIn] | None = None
    provenance: ProvenanceIn | None = None


class PKParameterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    analyte_id: UUID
    parameter_code: str
    unit: str | None
    value_numeric: float | None
    range_min: float | None
    range_max: float | None
    calculated_value: float | None
    reference_text: str | None
    evidence: list
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class PKRecommendRequest(BaseModel):
    persist: bool = True


class WashoutCalculateRequest(BaseModel):
    selected_value: float | None = None
    selected_unit: str = "day"
    manual_override: bool = False
    persist: bool = True


class WashoutOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    calculated_minimum: float | None
    selected_value: float | None
    unit: str
    rule_id: str | None
    rule_ids: list
    rationale: str | None
    manual_override: bool
    requires_washout: bool
    issues: list
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class ObservationCalculateRequest(BaseModel):
    selected_duration: float | None = None
    selected_unit: str = "h"
    manual_override: bool = False
    persist: bool = True


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    calculated_minimum: float | None
    selected_duration: float | None
    unit: str
    final_sampling_time: float | None
    rule_id: str | None
    rule_ids: list
    rationale: str | None
    manual_override: bool
    issues: list
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class SamplingPointIn(BaseModel):
    time_h: float
    reason: str
    window_before_min: float | None = None
    window_after_min: float | None = None
    mandatory: bool = False
    analyte_ids: list[str] | None = None
    provenance: ProvenanceIn | None = None


class SamplingPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    time_h: float
    time_min: float
    window_before_min: float | None
    window_after_min: float | None
    reason: str
    sequence_order: int
    mandatory: bool
    analyte_ids: list
    provenance: ProvenanceOut


class SamplingRecommendRequest(BaseModel):
    target_point_count: int | None = None
    observation_duration_h: float | None = None
    persist: bool = True


class SamplingPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    design_id: UUID | None
    total_points_per_period: int | None
    final_observation_h: float | None
    manual_override: bool
    rationale: str | None
    rule_ids: list
    warnings: list
    validation_issues: list
    points: list[SamplingPointOut]
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class SamplingPatchRequest(BaseModel):
    points: list[SamplingPointIn]
    final_observation_h: float | None = None
    manual_override: bool = True
    provenance: ProvenanceIn | None = None


class BloodVolumeCalculateRequest(BaseModel):
    blood_volume_per_pk_sample_ml: float
    screening_volume_ml: float = 0.0
    safety_laboratory_volume_ml: float = 0.0
    other_blood_volume_ml: float = 0.0
    reserve_duplicate_factor: float = 1.0
    subjects: int | None = None
    periods: int | None = None
    persist: bool = True


class BloodVolumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    subjects: int
    periods: int
    sampling_points_per_period: int
    blood_volume_per_pk_sample_ml: float
    screening_volume_ml: float
    safety_laboratory_volume_ml: float
    other_blood_volume_ml: float
    reserve_duplicate_factor: float
    pk_volume_ml: float
    screening_total_ml: float
    safety_total_ml: float
    other_total_ml: float
    total_volume_ml: float
    volume_per_subject_ml: float
    volume_per_period_ml: float
    rationale: str | None
    breakdown: dict
    sample_count: dict
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class ValidationIssueOut(BaseModel):
    severity: str
    code: str
    message: str
    field: str | None = None

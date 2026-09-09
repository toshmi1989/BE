from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import ProvenanceIn, ProvenanceOut


class CVEvidenceIn(BaseModel):
    source_id: str
    page: int | str | None = None
    section: str | None = None
    extracted_text: str | None = None
    quote: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: str = "PROPOSED"


class CVStudyCreate(BaseModel):
    source_id: str
    study_name: str | None = None
    publication_title: str | None = None
    analyte_id: UUID
    parameter: str
    design: str | None = None
    condition: str | None = None
    dose: str | None = None
    n_total: int | None = None
    n_be_analysis: int | None = None
    cv_value: float
    cv_unit: str = "percent"
    cv_type: str = "WITHIN_SUBJECT"
    extraction_method: str | None = None
    notes: str | None = None
    evidence: list[CVEvidenceIn] | None = None
    provenance: ProvenanceIn | None = None


class CVStudyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    source_id: str
    study_name: str | None
    publication_title: str | None
    analyte_id: UUID
    parameter: str
    design: str | None
    condition: str | None
    dose: str | None
    n_total: int | None
    n_be_analysis: int | None
    cv_value: float
    cv_unit: str
    cv_type: str
    extraction_method: str | None
    notes: str | None
    evidence: list
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class CVPoolRequest(BaseModel):
    cv_study_ids: list[UUID]
    method: str = "INVERSE_VARIANCE_WEIGHTED_LOG_CV"
    persist: bool = True


class CVPoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    method: str
    algorithm_version: str
    pooled_cv: float | None
    confidence_interval: list | None
    inputs: list
    cv_study_ids: list
    warnings: list
    mismatches: list
    parameter: str | None
    status: str
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class CVSelectRequest(BaseModel):
    selection_method: str
    cv_study_ids: list[UUID] | None = None
    selected_study_id: UUID | None = None
    pool_id: UUID | None = None
    expert_cv: float | None = None
    guideline_cv: float | None = None
    cv_unit: str = "percent"
    persist: bool = True


class CVSelectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    selected_cv: float | None
    cv_unit: str
    selection_method: str
    rationale: str | None
    source_study_ids: list
    warnings: list
    parameter: str | None
    analyte_id: str | None
    status: str
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class StatisticalConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    alpha: float
    power: float
    be_lower: float
    be_upper: float
    expected_ratio: float
    analysis_method: str
    transformation: str
    software: str | None
    algorithm_version: str | None
    rule_id: str | None
    defaults_source: str | None
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class SampleSizeRequest(BaseModel):
    design_type: str | None = None
    selected_cv: float | None = None
    parameter: str | None = None
    expected_ratio: float | None = None
    alpha: float | None = None
    power: float | None = None
    be_lower: float | None = None
    be_upper: float | None = None
    dropout_pct: float = 0.0
    reserve_pct: float = 0.0
    screen_failure_pct: float = 0.0
    created_by: str | None = None
    persist: bool = True


class SampleSizeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    design_type: str
    selected_cv: float | None
    parameter: str | None
    evaluable_n: int | None
    randomized_n: int | None
    screened_n: int | None
    method: str
    formula: str | None
    software_version: str | None
    algorithm_version: str
    achieved_power: float | None
    inputs_snapshot: dict
    warnings: list
    reserve_formula: str | None
    created_by: str | None
    status: str
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class StatisticsValidateOut(BaseModel):
    issues: list[dict[str, Any]]
    blocking: bool

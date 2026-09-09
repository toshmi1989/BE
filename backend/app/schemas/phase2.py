from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.provenance import DecisionStatus, Origin
from app.schemas.common import ProvenanceIn, ProvenanceOut


class DesignCreate(BaseModel):
    type: str
    periods: int | None = None
    sequences: list | None = None
    treatments: list | None = None
    randomization: bool | None = None
    blinding: bool | None = None
    food_condition: str | None = None
    stage_configuration: dict | None = None
    rationale: str | None = None
    decision_status: DecisionStatus | None = None
    provenance: ProvenanceIn | None = None


class DesignUpdate(BaseModel):
    type: str | None = None
    periods: int | None = None
    sequences: list | None = None
    treatments: list | None = None
    randomization: bool | None = None
    blinding: bool | None = None
    food_condition: str | None = None
    stage_configuration: dict | None = None
    rationale: str | None = None
    decision_status: DecisionStatus | None = None
    provenance: ProvenanceIn | None = None


class DesignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    type: str
    periods: int | None
    sequences: list
    treatments: list
    randomization: bool | None
    blinding: bool | None
    food_condition: str | None
    stage_configuration: dict | None
    rationale: str | None
    decision_status: str
    recommendation_confidence: float | None
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class DesignRecommendRequest(BaseModel):
    available_guideline_recommendation: str | None = None
    reference_product_known: bool | None = None
    half_life: float | None = None
    variability_known: bool | None = None
    variability_level: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    food_condition: str | None = None
    expert_override: str | None = None
    evidence_source_ids: list[str] = Field(default_factory=list)
    persist: bool = False


class DesignRecommendResponse(BaseModel):
    recommended_design: dict[str, Any] | None
    rationale: str
    confidence: float | None
    evidence_source_ids: list[str]
    status: str
    origin: str
    persisted_design: DesignOut | None = None


class FoodUpsert(BaseModel):
    condition: str
    meal_type: str | None = None
    calories: float | None = None
    fat_percent: float | None = None
    composition: list | None = None
    meal_start_offset_min: int | None = None
    dose_after_meal_min: int | None = None
    water_volume_ml: int | None = None
    decision_status: DecisionStatus | None = None
    provenance: ProvenanceIn | None = None


class FoodUpdate(BaseModel):
    condition: str | None = None
    meal_type: str | None = None
    calories: float | None = None
    fat_percent: float | None = None
    composition: list | None = None
    meal_start_offset_min: int | None = None
    dose_after_meal_min: int | None = None
    water_volume_ml: int | None = None
    decision_status: DecisionStatus | None = None
    provenance: ProvenanceIn | None = None


class FoodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    condition: str
    meal_type: str | None
    calories: float | None
    fat_percent: float | None
    composition: list
    meal_start_offset_min: int | None
    dose_after_meal_min: int | None
    water_volume_ml: int | None
    decision_status: str
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class CriterionCreate(BaseModel):
    category: str | None = None
    number: int | None = None
    text: str = Field(min_length=1)
    provenance: ProvenanceIn | None = None


class CriterionUpdate(BaseModel):
    number: int | None = None
    text: str | None = Field(default=None, min_length=1)
    provenance: ProvenanceIn | None = None


class CriterionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    category: str
    number: int
    text: str
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class EligibilityReplace(BaseModel):
    inclusion: list[CriterionCreate] = Field(default_factory=list)
    non_inclusion: list[CriterionCreate] = Field(default_factory=list)
    exclusion: list[CriterionCreate] = Field(default_factory=list)


class EligibilityOut(BaseModel):
    inclusion: list[CriterionOut] = Field(default_factory=list)
    non_inclusion: list[CriterionOut] = Field(default_factory=list)
    exclusion: list[CriterionOut] = Field(default_factory=list)


class SubjectPlanUpsert(BaseModel):
    target_evaluable_n: int | None = None
    planned_randomized_n: int | None = None
    reserve_n: int | None = None
    planned_screened_n: int | None = None
    provenance: ProvenanceIn | None = None


class SubjectPlanUpdate(BaseModel):
    target_evaluable_n: int | None = None
    planned_randomized_n: int | None = None
    reserve_n: int | None = None
    planned_screened_n: int | None = None
    provenance: ProvenanceIn | None = None


class SubjectPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    target_evaluable_n: int | None
    planned_randomized_n: int | None
    reserve_n: int | None
    planned_screened_n: int | None
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut


class ClientInputUpsert(BaseModel):
    requested_product_name: str | None = None
    inn: str | None = None
    dosage: str | None = None
    dosage_form: str | None = None
    route: str | None = None
    requested_subject_count: int | None = None
    provenance: ProvenanceIn | None = None


class ClientInputOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    requested_product_name: str | None
    inn: str | None
    dosage: str | None
    dosage_form: str | None
    route: str | None
    requested_subject_count: int | None
    entity_version: int
    created_at: datetime
    updated_at: datetime
    provenance: ProvenanceOut

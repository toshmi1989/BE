from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.domain.constants import DEFAULT_PROJECT_STATUS, SCHEMA_VERSION
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin, VersionedMixin

if TYPE_CHECKING:
    from app.models.analyte import Analyte
    from app.models.blood_volume import BloodVolumeCalculation
    from app.models.client_input import ClientInput
    from app.models.cv_study import CVStudy
    from app.models.design import Design
    from app.models.eligibility import EligibilityCriterion
    from app.models.food import FoodCondition
    from app.models.observation_plan import ObservationPlan
    from app.models.person import Person
    from app.models.study_administration import StudyAdministration
    from app.models.organization import StudyParty
    from app.models.pk_parameter import PKParameter
    from app.models.product import Product
    from app.models.project_version import ProjectVersion
    from app.models.reference_product import ReferenceProduct
    from app.models.sampling_plan import SamplingPlan
    from app.models.source import Source
    from app.models.sponsor import Sponsor
    from app.models.statistics import (
        CVPool,
        CVSelection,
        SampleSizeCalculation,
        StatisticalConfig,
        SubjectReserveCalculation,
    )
    from app.models.study import Study
    from app.models.subject_plan import SubjectPlan
    from app.models.validation_issue import ValidationIssue
    from app.models.washout_plan import WashoutPlan
    from app.models.research import ResearchCase
    from app.models.documents import Document, ResearchProfile
    from app.models.ai_run import AIRun
    from app.models.protocol import ProtocolDraft
    from app.models.generated_document import GeneratedDocument
    from app.models.procedure_definition import ProcedureDefinitionRecord
    from app.models.procedure_schedule import ProcedureScheduleRecord
    from app.models.bioanalysis_plan import BioanalysisPlanRecord
    from app.models.safety_plan import SafetyPlanRecord
    from app.models.expert_rule import ExpertRuleRecord
    from app.models.regulatory_basis import RegulatoryBasisRecord
    from app.models.knowledge_rule import KnowledgeRuleRecord
    from app.models.expert_decision import ExpertDecisionRecord
    from app.models.knowledge_gap import KnowledgeGapRecord
    from app.models.protocol_comparison import PreviousProtocolComparisonRecord
    from app.models.protocol_qa import ProtocolQARunRecord


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin, VersionedMixin):
    """Workspace / aggregate root for a BE protocol study."""

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=DEFAULT_PROJECT_STATUS)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False, default=SCHEMA_VERSION)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    study: Mapped[Study | None] = relationship(
        "Study", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    sponsor: Mapped[Sponsor | None] = relationship(
        "Sponsor", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    organizations: Mapped[list[StudyParty]] = relationship(
        "StudyParty", back_populates="project", cascade="all, delete-orphan"
    )
    persons: Mapped[list["Person"]] = relationship(
        "Person", back_populates="project", cascade="all, delete-orphan"
    )
    study_administration: Mapped["StudyAdministration | None"] = relationship(
        "StudyAdministration", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    product: Mapped[Product | None] = relationship(
        "Product", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    reference_product: Mapped[ReferenceProduct | None] = relationship(
        "ReferenceProduct",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sources: Mapped[list[Source]] = relationship(
        "Source", back_populates="project", cascade="all, delete-orphan"
    )
    versions: Mapped[list[ProjectVersion]] = relationship(
        "ProjectVersion",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectVersion.version_number",
    )
    client_input: Mapped[ClientInput | None] = relationship(
        "ClientInput", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    design: Mapped[Design | None] = relationship(
        "Design", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    food: Mapped[FoodCondition | None] = relationship(
        "FoodCondition", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    eligibility_criteria: Mapped[list[EligibilityCriterion]] = relationship(
        "EligibilityCriterion",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="EligibilityCriterion.category, EligibilityCriterion.number",
    )
    subjects: Mapped[SubjectPlan | None] = relationship(
        "SubjectPlan", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    analytes: Mapped[list[Analyte]] = relationship(
        "Analyte", back_populates="project", cascade="all, delete-orphan"
    )
    pk_parameters: Mapped[list[PKParameter]] = relationship(
        "PKParameter", back_populates="project", cascade="all, delete-orphan"
    )
    washout: Mapped[WashoutPlan | None] = relationship(
        "WashoutPlan", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    observation: Mapped[ObservationPlan | None] = relationship(
        "ObservationPlan", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    sampling: Mapped[SamplingPlan | None] = relationship(
        "SamplingPlan", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    blood_volume: Mapped[BloodVolumeCalculation | None] = relationship(
        "BloodVolumeCalculation",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    cv_studies: Mapped[list[CVStudy]] = relationship(
        "CVStudy", back_populates="project", cascade="all, delete-orphan"
    )
    cv_pools: Mapped[list[CVPool]] = relationship(
        "CVPool", back_populates="project", cascade="all, delete-orphan"
    )
    cv_selection: Mapped[CVSelection | None] = relationship(
        "CVSelection", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    statistical_config: Mapped[StatisticalConfig | None] = relationship(
        "StatisticalConfig",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    sample_size_calculations: Mapped[list[SampleSizeCalculation]] = relationship(
        "SampleSizeCalculation", back_populates="project", cascade="all, delete-orphan"
    )
    subject_reserve_calculations: Mapped[list[SubjectReserveCalculation]] = relationship(
        "SubjectReserveCalculation", back_populates="project", cascade="all, delete-orphan"
    )
    validation_issues: Mapped[list[ValidationIssue]] = relationship(
        "ValidationIssue", back_populates="project", cascade="all, delete-orphan"
    )
    research_case: Mapped[ResearchCase | None] = relationship(
        "ResearchCase", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    research_profile: Mapped[ResearchProfile | None] = relationship(
        "ResearchProfile", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )
    documents: Mapped[list[Document]] = relationship(
        "Document", back_populates="project", cascade="all, delete-orphan"
    )
    ai_runs: Mapped[list[AIRun]] = relationship(
        "AIRun", back_populates="project", cascade="all, delete-orphan"
    )
    protocol_drafts: Mapped[list[ProtocolDraft]] = relationship(
        "ProtocolDraft", back_populates="project", cascade="all, delete-orphan"
    )
    generated_documents: Mapped[list[GeneratedDocument]] = relationship(
        "GeneratedDocument", back_populates="project", cascade="all, delete-orphan"
    )
    procedure_schedule: Mapped[ProcedureScheduleRecord | None] = relationship(
        "ProcedureScheduleRecord",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    procedure_definitions: Mapped[list[ProcedureDefinitionRecord]] = relationship(
        "ProcedureDefinitionRecord", back_populates="project", cascade="all, delete-orphan"
    )
    bioanalysis_plan: Mapped[BioanalysisPlanRecord | None] = relationship(
        "BioanalysisPlanRecord",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    safety_plan: Mapped[SafetyPlanRecord | None] = relationship(
        "SafetyPlanRecord",
        back_populates="project",
        uselist=False,
        cascade="all, delete-orphan",
    )
    expert_rules: Mapped[list[ExpertRuleRecord]] = relationship(
        "ExpertRuleRecord", back_populates="project", cascade="all, delete-orphan"
    )
    knowledge_rules: Mapped[list[KnowledgeRuleRecord]] = relationship(
        "KnowledgeRuleRecord", back_populates="project", cascade="all, delete-orphan"
    )
    expert_decisions: Mapped[list[ExpertDecisionRecord]] = relationship(
        "ExpertDecisionRecord", back_populates="project", cascade="all, delete-orphan"
    )
    knowledge_gaps: Mapped[list[KnowledgeGapRecord]] = relationship(
        "KnowledgeGapRecord", back_populates="project", cascade="all, delete-orphan"
    )
    regulatory_bases: Mapped[list[RegulatoryBasisRecord]] = relationship(
        "RegulatoryBasisRecord", back_populates="project", cascade="all, delete-orphan"
    )
    protocol_comparisons: Mapped[list[PreviousProtocolComparisonRecord]] = relationship(
        "PreviousProtocolComparisonRecord",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    protocol_qa_runs: Mapped[list[ProtocolQARunRecord]] = relationship(
        "ProtocolQARunRecord", back_populates="project", cascade="all, delete-orphan"
    )

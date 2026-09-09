"""Protocol content matrix loader — Phase 12A.

Source of truth for documentation is docs/PROTOCOL_CONTENT_MATRIX.md.
This module exposes the structured rows used by tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContentMatrixRow:
    section_code: str
    title: str
    type: str  # DYNAMIC|CONDITIONAL|STATIC_VERIFIED|EXPERT_REQUIRED|UNRESOLVED|NEEDS_REVIEW
    source_of_truth: str
    dependencies: tuple[str, ...]
    generator: str
    evidence_required: bool
    calculation_required: bool
    expert_required: bool
    current_status: str
    notes: str = ""


# Substantive P2-focused matrix (technical classification only).
PROTOCOL_CONTENT_MATRIX: tuple[ContentMatrixRow, ...] = (
    ContentMatrixRow("2.2", "Preclinical/clinical summary", "EXPERT_REQUIRED", "EvidenceClaim VERIFIED", ("evidence",), "preclinical_clinical_summary", True, False, True, "PARTIAL", "Wording deferred pending medical writer"),
    ContentMatrixRow("2.3", "Risk-benefit", "EXPERT_REQUIRED", "EvidenceClaim VERIFIED", ("evidence",), "risk_benefit", True, False, True, "PARTIAL", "Expert narrative deferred"),
    ContentMatrixRow("2.4", "Dose rationale", "DYNAMIC", "Product.dosage + Evidence", ("product", "evidence"), "dose_rationale", True, False, True, "PARTIAL", "Dose from product; clinical rationale may need expert"),
    ContentMatrixRow("2.7", "Literature basis", "EXPERT_REQUIRED", "Evidence / Sources", ("sources", "evidence"), "rationale_literature", True, False, True, "PARTIAL", ""),
    ContentMatrixRow("2.8", "Pharmacology", "EXPERT_REQUIRED", "EvidenceClaim", ("evidence",), "pharmacology", True, False, True, "PARTIAL", ""),
    ContentMatrixRow("4.3", "Randomization/blinding", "DYNAMIC", "Design", ("design",), "randomization", False, False, False, "IMPLEMENTED", "DisplayValueRegistry for enums"),
    ContentMatrixRow("4.4", "Treatment", "DYNAMIC", "Design + Food", ("design", "food"), "treatment", False, False, False, "IMPLEMENTED", ""),
    ContentMatrixRow("4.4.1", "Stages", "DYNAMIC", "Design periods", ("design",), "stages", False, False, False, "IMPLEMENTED", ""),
    ContentMatrixRow("4.4.2", "Blood sampling", "DYNAMIC", "SamplingPlan", ("sampling",), "sampling_plan", False, True, False, "IMPLEMENTED", "Canonical sampling"),
    ContentMatrixRow("4.5", "Participation duration", "DYNAMIC", "Observation + Washout + Design", ("observation", "washout", "design"), "participation_duration", False, True, False, "IMPLEMENTED", ""),
    ContentMatrixRow("4.6", "Stop/exclusion rules", "NEEDS_REVIEW", "Eligibility + expert practice", ("eligibility",), "stop_rules", False, False, True, "PARTIAL", "Clinical stop criteria deferred"),
    ContentMatrixRow("4.7", "Drug accountability", "DYNAMIC", "Product / Reference", ("product", "reference"), "drug_accountability", False, False, False, "IMPLEMENTED", ""),
    ContentMatrixRow("4.7.1", "Test accountability", "DYNAMIC", "Product", ("product",), "drug_accountability_test", False, False, False, "IMPLEMENTED", ""),
    ContentMatrixRow("4.7.2", "Reference accountability", "DYNAMIC", "ReferenceProduct", ("reference",), "drug_accountability_ref", False, False, False, "IMPLEMENTED", ""),
    ContentMatrixRow("4.7.3", "Storage", "DYNAMIC", "Product/Reference storage fields", ("product", "reference"), "storage_conditions", False, False, False, "IMPLEMENTED", "Unresolved if missing"),
    ContentMatrixRow("4.8", "Randomization codes", "DYNAMIC", "Design blinding", ("design",), "randomization_codes", False, False, False, "IMPLEMENTED", ""),
    ContentMatrixRow("4.8.1", "Subject numbering", "DYNAMIC", "SubjectPlan", ("subjects",), "subject_numbering", False, False, False, "IMPLEMENTED", ""),
    ContentMatrixRow("4.8.2", "Code storage/unblinding", "NEEDS_REVIEW", "SOP / expert", ("design",), "unblinding_sop", False, False, True, "PARTIAL", "SOP wording deferred"),
    ContentMatrixRow("4.8.3", "Blinding", "DYNAMIC", "Design", ("design",), "blinding", False, False, False, "IMPLEMENTED", ""),
    ContentMatrixRow("4.9", "Primary data list", "UNRESOLVED", "CRF / center SOP", (), "primary_data_list", False, False, True, "UNRESOLVED", "{{CRF.PRIMARY_DATA_LIST}}"),
    ContentMatrixRow("6.1", "Treatment detail", "DYNAMIC", "Design/Food/Washout/Sampling", ("design", "food", "washout", "sampling"), "treatment_detail", False, False, False, "PARTIAL", "Structural; clinical detail deferred"),
    ContentMatrixRow("6.1.1", "Procedures timeline", "DYNAMIC", "ProcedureSchedule", ("design", "sampling", "food"), "procedures_timeline", False, False, False, "PARTIAL", "Schedule foundation Phase 12A"),
    ContentMatrixRow("6.1.2", "Screening", "NEEDS_REVIEW", "SafetyPlan + Eligibility", ("safety", "eligibility"), "screening_procedures", False, False, True, "PARTIAL", "Battery deferred"),
    ContentMatrixRow("6.1.3", "Randomization procedure", "DYNAMIC", "Design", ("design",), "randomization_procedure", False, False, False, "IMPLEMENTED", ""),
    ContentMatrixRow("6.1.4", "Period 1", "DYNAMIC", "Design + Food + Sampling", ("design", "food", "sampling"), "period_1", False, False, False, "PARTIAL", ""),
    ContentMatrixRow("6.1.5", "Washout procedure", "DYNAMIC", "WashoutPlan", ("washout",), "washout_procedure", False, True, False, "IMPLEMENTED", ""),
    ContentMatrixRow("6.1.6", "Period 2", "DYNAMIC", "Design + Food + Sampling", ("design", "food", "sampling"), "period_2", False, False, False, "PARTIAL", ""),
    ContentMatrixRow("6.1.7", "Final examination", "NEEDS_REVIEW", "SafetyPlan", ("safety",), "final_exam", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("6.1.8", "Completion", "DYNAMIC", "Design", ("design",), "completion", False, False, False, "PARTIAL", ""),
    ContentMatrixRow("6.1.9", "Sample preparation", "EXPERT_REQUIRED", "BioanalysisPlan", ("bioanalysis",), "sample_prep", False, False, True, "UNRESOLVED", "No template defaults"),
    ContentMatrixRow("6.1.10", "Concomitant therapy", "EXPERT_REQUIRED", "Expert / SmPC", ("evidence",), "concomitant_therapy", True, False, True, "PARTIAL", ""),
    ContentMatrixRow("6.2", "Treatment restrictions", "NEEDS_REVIEW", "Expert + Food", ("food",), "treatment_restrictions", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("6.2.1", "Food restrictions", "CONDITIONAL", "FoodCondition + STATIC meal T12", ("food",), "food_restrictions", False, False, False, "IMPLEMENTED", "T12 STATIC_VERIFIED when FED+HIGH_CALORIE"),
    ContentMatrixRow("6.2.2", "Activity restrictions", "STATIC_VERIFIED", "Template SOP wording", (), "activity_restrictions", False, False, False, "NEEDS_REVIEW", "Confirm vs expert interview"),
    ContentMatrixRow("6.2.3", "Contraception", "EXPERT_REQUIRED", "Expert / regulatory", (), "contraception", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("6.3", "Compliance", "STATIC_VERIFIED", "Template boilerplate", (), "compliance", False, False, False, "NEEDS_REVIEW", ""),
    ContentMatrixRow("6.3.1", "Withdrawal follow-up", "NEEDS_REVIEW", "SafetyPlan.follow_up", ("safety",), "withdrawal_followup", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("7.1", "Evaluated parameters", "DYNAMIC", "Analytes + PK", ("analytes", "pk"), "eval_parameters", False, False, False, "IMPLEMENTED", ""),
    ContentMatrixRow("7.2", "Methods/timing", "DYNAMIC", "Sampling + Observation", ("sampling", "observation"), "eval_methods_timing", False, True, False, "PARTIAL", ""),
    ContentMatrixRow("7.3", "Analytical method", "EXPERT_REQUIRED", "BioanalysisPlan", ("bioanalysis",), "analytical_method", False, False, True, "UNRESOLVED", ""),
    ContentMatrixRow("7.3.1", "Bioanalytical method", "EXPERT_REQUIRED", "BioanalysisPlan", ("bioanalysis",), "bioanalysis", False, False, True, "UNRESOLVED", "{{BIOANALYSIS.*}}"),
    ContentMatrixRow("7.3.2", "Validation", "EXPERT_REQUIRED", "BioanalysisPlan.validation_status", ("bioanalysis",), "bio_validation", False, False, True, "UNRESOLVED", ""),
    ContentMatrixRow("7.3.3", "Sample analysis", "EXPERT_REQUIRED", "BioanalysisPlan", ("bioanalysis",), "sample_analysis", False, False, True, "UNRESOLVED", ""),
    ContentMatrixRow("7.3.4", "Run acceptance", "EXPERT_REQUIRED", "BioanalysisPlan.acceptance_criteria", ("bioanalysis",), "run_acceptance", False, False, True, "UNRESOLVED", ""),
    ContentMatrixRow("8.1", "Safety parameters", "NEEDS_REVIEW", "SafetyPlan", ("safety",), "safety_standard", False, False, True, "PARTIAL", "No new thresholds"),
    ContentMatrixRow("8.2", "Safety methods/timing", "NEEDS_REVIEW", "SafetyPlan + ProcedureSchedule", ("safety", "procedures"), "safety_methods", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("8.2.1", "Physical exam", "NEEDS_REVIEW", "SafetyPlan.physical_exam", ("safety",), "physical_exam", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("8.2.2", "Vital signs", "STATIC_VERIFIED", "SAFE.T13 + SafetyPlan", ("safety",), "vital_signs", False, False, False, "PARTIAL", "Scale table preserved"),
    ContentMatrixRow("8.2.3", "Safety labs", "STATIC_VERIFIED", "T09 + SafetyPlan", ("safety",), "safety_labs", False, False, False, "PARTIAL", "T09 not PK analytes"),
    ContentMatrixRow("8.3", "AE/SAE framework", "STATIC_VERIFIED", "T14–T16 + narrative", ("safety",), "ae_framework", False, False, True, "PARTIAL", "Scales STATIC; narrative expert"),
    ContentMatrixRow("8.4", "AE follow-up", "EXPERT_REQUIRED", "SafetyPlan.follow_up", ("safety",), "ae_followup", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("8.5", "Pregnancy", "EXPERT_REQUIRED", "SafetyPlan.pregnancy", ("safety",), "pregnancy", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("9.3", "Alpha", "DYNAMIC", "StatisticalConfig", ("statistics",), "alpha", False, True, False, "IMPLEMENTED", ""),
    ContentMatrixRow("9.4", "Stopping rules", "NEEDS_REVIEW", "Stats + expert", ("statistics",), "stopping_rules", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("9.5", "Missing data", "NEEDS_REVIEW", "SAP / expert", ("statistics",), "missing_data_policy", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("9.6", "SAP deviations", "NEEDS_REVIEW", "Expert", ("statistics",), "sap_deviations", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("9.7", "Analysis populations", "DYNAMIC", "SubjectPlan + stats", ("subjects", "statistics"), "analysis_populations", False, False, False, "PARTIAL", ""),
    ContentMatrixRow("9.7.1", "Statistical analysis", "DYNAMIC", "Stats engines", ("statistics",), "statistical_analysis", False, True, False, "PARTIAL", ""),
    ContentMatrixRow("9.7.1.1", "Descriptive stats", "DYNAMIC", "Stats", ("statistics",), "descriptive_stats", False, True, False, "PARTIAL", ""),
    ContentMatrixRow("9.7.1.2", "ANOVA methods", "DYNAMIC", "Stats", ("statistics",), "anova_methods", False, True, False, "PARTIAL", ""),
    ContentMatrixRow("9.7.2", "BE criteria", "DYNAMIC", "StatisticalConfig", ("statistics",), "be_criteria", False, True, False, "IMPLEMENTED", ""),
    ContentMatrixRow("9.7.3", "Outliers", "NEEDS_REVIEW", "Expert / SAP", ("statistics",), "outliers", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("9.7.4", "Safety analysis", "NEEDS_REVIEW", "SafetyPlan + stats", ("safety", "statistics"), "safety_analysis", False, False, True, "PARTIAL", ""),
    ContentMatrixRow("16", "Appendices", "STATIC_VERIFIED", "Static forms + StudyAdministration signatures", ("administration",), "appendices", False, False, False, "PARTIAL", "Forms preserved; signatures dynamic when present"),
    ContentMatrixRow("17", "Conclusion", "DYNAMIC", "Canonical product/design/reference", ("product", "design", "reference"), "conclusion", False, False, False, "IMPLEMENTED", "Deterministic plan summary only — no results"),
    ContentMatrixRow("18", "Literature", "DYNAMIC", "Sources", ("sources",), "literature", False, False, False, "IMPLEMENTED", "Provenance from sources"),
)


def list_content_matrix() -> list[dict[str, Any]]:
    rows = []
    for r in PROTOCOL_CONTENT_MATRIX:
        rows.append(
            {
                "section_code": r.section_code,
                "title": r.title,
                "type": r.type,
                "source_of_truth": r.source_of_truth,
                "dependencies": list(r.dependencies),
                "generator": r.generator,
                "evidence_required": r.evidence_required,
                "calculation_required": r.calculation_required,
                "expert_required": r.expert_required,
                "current_status": r.current_status,
                "notes": r.notes,
            }
        )
    return rows


def matrix_section_codes() -> set[str]:
    return {r.section_code for r in PROTOCOL_CONTENT_MATRIX}

"""Section tree + configurable mapping (backend-only, never in React)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SectionDef:
    section_code: str
    title: str
    order: int
    parent_section: str | None
    template_key: str
    required_data: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ("always",)
    generator: str = "generic"


# Flattened tree — parent_section links hierarchy; order is document order.
# Phase 11B: P0 sections added for DOCX activation.
SECTION_TREE: list[SectionDef] = [
    SectionDef("SYNOPSIS", "Synopsis", 0, None, "SYNOPSIS", ("study", "design", "subjects"), ("always",), "synopsis"),
    SectionDef("1", "Общая информация", 100, None, "GENERAL_INFO", (), ("always",), "heading"),
    SectionDef("1.1", "Protocol metadata", 110, "1", "PROTOCOL_METADATA", ("study",), ("always",), "protocol_metadata"),
    SectionDef("1.2", "Sponsor", 120, "1", "SPONSOR", (), ("always",), "sponsor"),
    SectionDef("1.3", "Authorized sponsor persons", 130, "1", "SPONSOR_PERSONS", (), ("always",), "sponsor_persons"),
    SectionDef("1.4", "Medical expert", 140, "1", "MEDICAL_EXPERT", (), ("always",), "medical_expert"),
    SectionDef("1.5", "Investigators and clinical centers", 150, "1", "INVESTIGATORS", (), ("always",), "investigators"),
    SectionDef("1.6", "Analytical laboratory", 160, "1", "ANALYTICAL_LAB", (), ("always",), "analytical_lab"),
    SectionDef("1.7", "Key organizations", 170, "1", "KEY_ORGS", (), ("always",), "key_orgs"),
    SectionDef("1.8", "Signatures", 180, "1", "SIGNATURES", (), ("always",), "signatures"),
    SectionDef("1.9", "Investigator agreement", 190, "1", "INVESTIGATOR_AGREEMENT", (), ("always",), "investigator_agreement"),
    SectionDef("2", "Обоснование", 200, None, "RATIONALE", (), ("always",), "heading"),
    SectionDef("2.1", "Products", 210, "2", "PRODUCTS", ("product",), ("always",), "heading"),
    SectionDef("2.1.1", "Test product", 211, "2.1", "TEST_PRODUCT", ("product",), ("always",), "test_product"),
    SectionDef("2.1.2", "Reference product", 212, "2.1", "REFERENCE_PRODUCT", ("reference_product",), ("always",), "reference_product"),
    SectionDef("2.2", "Preclinical/clinical summary", 220, "2", "CLINICAL_SUMMARY", (), ("always",), "preclinical_clinical_summary"),
    SectionDef("2.3", "Risk-benefit", 230, "2", "RISK_BENEFIT", (), ("always",), "risk_benefit"),
    SectionDef("2.4", "Dose rationale", 240, "2", "DOSE_RATIONALE", ("product",), ("always",), "dose_rationale"),
    SectionDef("2.5", "Study conditions", 250, "2", "STUDY_CONDITIONS", ("food", "design"), ("always",), "study_conditions"),
    SectionDef("2.6", "Subjects", 260, "2", "SUBJECTS_RATIONALE", ("subjects",), ("always",), "subjects_rationale"),
    SectionDef("2.7", "Literature / regulatory basis", 265, "2", "RATIONALE_LITERATURE", (), ("always",), "rationale_literature"),
    SectionDef("2.8", "Pharmacology", 268, "2", "PHARMACOLOGY", (), ("always",), "pharmacology"),
    SectionDef("2.9", "Test product details", 269, "2", "TEST_PRODUCT_DETAILS", ("product",), ("always",), "test_product_details"),
    SectionDef("2.10", "Reference justification", 270, "2", "REFERENCE_JUSTIFICATION", ("reference_product",), ("always",), "reference_justification"),
    SectionDef("2.11", "Observation duration rationale", 280, "2", "OBSERVATION_RATIONALE", ("observation",), ("always",), "observation_rationale"),
    SectionDef("2.12", "Washout rationale", 290, "2", "WASHOUT_RATIONALE", ("washout",), ("always",), "washout_rationale"),
    SectionDef("3", "Цель и задачи", 300, None, "OBJECTIVES", ("study",), ("always",), "objectives"),
    SectionDef("4", "Дизайн", 400, None, "DESIGN_ROOT", ("design",), ("always",), "heading"),
    SectionDef("4.1", "PK parameters", 410, "4", "PK_PARAMETERS", ("analytes", "pk_parameters"), ("always",), "pk_parameters"),
    SectionDef("4.2", "Design", 420, "4", "DESIGN", ("design",), ("always",), "design"),
    SectionDef("4.3", "Randomization/blinding", 430, "4", "RANDOMIZATION", ("design",), ("always",), "randomization"),
    SectionDef("4.4", "Treatment", 440, "4", "TREATMENT", ("design", "food"), ("always",), "treatment"),
    SectionDef("4.4.1", "Stages", 441, "4.4", "STAGES", ("design",), ("always",), "stages"),
    SectionDef("4.4.2", "Blood sampling", 442, "4.4", "SAMPLING_PLAN", ("sampling", "analytes"), ("always",), "sampling_plan"),
    SectionDef("4.5", "Participation duration", 450, "4", "PARTICIPATION_DURATION", ("washout", "observation"), ("always",), "participation_duration"),
    SectionDef("4.6", "Stop/exclusion rules", 460, "4", "STOP_RULES", (), ("always",), "stop_rules"),
    SectionDef("4.7", "Drug accountability", 470, "4", "DRUG_ACCOUNTABILITY", ("product",), ("always",), "drug_accountability"),
    SectionDef("4.7.1", "Test product accountability", 471, "4.7", "DRUG_ACC_TEST", ("product",), ("always",), "drug_accountability_test"),
    SectionDef("4.7.2", "Reference accountability", 472, "4.7", "DRUG_ACC_REF", ("reference_product",), ("always",), "drug_accountability_ref"),
    SectionDef("4.7.3", "Storage/accountability", 473, "4.7", "STORAGE", (), ("always",), "storage_conditions"),
    SectionDef("4.8", "Randomization codes", 480, "4", "RAND_CODES", ("design",), ("always",), "randomization_codes"),
    SectionDef("4.8.1", "Subject numbers", 481, "4.8", "SUBJECT_NUMBERS", ("subjects",), ("always",), "subject_numbering"),
    SectionDef("4.8.2", "Code storage/unblinding", 482, "4.8", "UNBLINDING", ("design",), ("always",), "unblinding_sop"),
    SectionDef("4.8.3", "Blinding", 483, "4.8", "BLINDING", ("design",), ("always",), "blinding"),
    SectionDef("4.9", "Primary/direct data", 490, "4", "PRIMARY_DATA", (), ("always",), "primary_data_list"),
    SectionDef("5", "Subjects", 500, None, "SUBJECTS_ROOT", (), ("always",), "heading"),
    SectionDef("5.1", "Inclusion", 510, "5", "INCLUSION_CRITERIA", ("eligibility",), ("always",), "inclusion"),
    SectionDef("5.2", "Non-inclusion", 520, "5", "NON_INCLUSION_CRITERIA", ("eligibility",), ("always",), "non_inclusion"),
    SectionDef("5.3", "Exclusion", 530, "5", "EXCLUSION_CRITERIA", ("eligibility",), ("always",), "exclusion"),
    SectionDef("6", "Treatment procedures", 600, None, "TREATMENT_PROC", ("design", "food"), ("always",), "heading"),
    SectionDef("6.1", "Treatment", 610, "6", "TREATMENT_DETAIL", ("design",), ("always",), "treatment_detail"),
    SectionDef("6.1.1", "Procedures", 611, "6.1", "PROCEDURES", ("design",), ("always",), "procedures_timeline"),
    SectionDef("6.1.2", "Screening", 612, "6.1", "SCREENING", (), ("always",), "screening_procedures"),
    SectionDef("6.1.3", "Randomization", 613, "6.1", "RAND_PROC", ("design",), ("always",), "randomization_procedure"),
    SectionDef("6.1.4", "Period 1", 614, "6.1", "PERIOD_1", ("design", "food"), ("always",), "period_1"),
    SectionDef("6.1.5", "Washout", 615, "6.1", "WASHOUT_PROCEDURE", ("washout",), ("crossover",), "washout_procedure"),
    SectionDef("6.1.6", "Period 2", 616, "6.1", "PERIOD_2", ("design", "food"), ("crossover",), "period_2"),
    SectionDef("6.1.7", "Final examination", 617, "6.1", "FINAL_EXAM", (), ("always",), "final_exam"),
    SectionDef("6.1.8", "Completion", 618, "6.1", "COMPLETION", (), ("always",), "completion"),
    SectionDef("6.1.9", "Blood sample preparation", 619, "6.1", "SAMPLE_PREP", ("sampling",), ("always",), "sample_prep"),
    SectionDef("6.1.10", "Concomitant/emergency therapy", 620, "6.1", "CONCOMITANT", (), ("always",), "concomitant_therapy"),
    SectionDef("6.2", "Allowed/prohibited treatments", 630, "6", "TREATMENT_RESTRICTIONS", (), ("always",), "treatment_restrictions"),
    SectionDef("6.2.1", "Food restrictions", 631, "6.2", "FOOD_RESTRICTIONS", ("food",), ("always",), "food_restrictions"),
    SectionDef("6.2.2", "Physical activity", 632, "6.2", "ACTIVITY", (), ("always",), "activity_restrictions"),
    SectionDef("6.2.3", "Contraception", 633, "6.2", "CONTRACEPTION", (), ("always",), "contraception"),
    SectionDef("6.3", "Compliance", 640, "6", "COMPLIANCE", (), ("always",), "compliance"),
    SectionDef("6.3.1", "Follow-up after withdrawal", 641, "6.3", "WITHDRAWAL_FU", (), ("always",), "withdrawal_followup"),
    SectionDef("7", "Оцениваемые параметры", 700, None, "EVAL_PARAMS", ("analytes",), ("always",), "heading"),
    SectionDef("7.1", "Parameters", 710, "7", "EVAL_PARAMETERS", ("pk_parameters", "analytes"), ("always",), "eval_parameters"),
    SectionDef("7.2", "Methods/timing", 720, "7", "EVAL_METHODS", ("sampling",), ("always",), "eval_methods_timing"),
    SectionDef("7.3", "Analytical method", 730, "7", "ANALYTICAL_METHOD", ("analytes",), ("always",), "analytical_method"),
    SectionDef("7.3.1", "Bioanalytical method", 731, "7.3", "BIOANALYSIS", ("analytes",), ("always",), "bioanalysis"),
    SectionDef("7.3.2", "Validation", 732, "7.3", "BIO_VALIDATION", (), ("always",), "bio_validation"),
    SectionDef("7.3.3", "Sample analysis", 733, "7.3", "SAMPLE_ANALYSIS", (), ("always",), "sample_analysis"),
    SectionDef("7.3.4", "Run acceptance", 734, "7.3", "RUN_ACCEPTANCE", (), ("always",), "run_acceptance"),
    SectionDef("8", "Безопасность", 800, None, "SAFETY", (), ("always",), "heading"),
    SectionDef("8.1", "Safety parameters", 810, "8", "SAFETY_PARAMS", (), ("always",), "safety_standard"),
    SectionDef("8.2", "Safety methods/timing", 820, "8", "SAFETY_METHODS", (), ("always",), "safety_methods"),
    SectionDef("8.2.1", "Physical exam", 821, "8.2", "PHYS_EXAM", (), ("always",), "physical_exam"),
    SectionDef("8.2.2", "Vital signs", 822, "8.2", "VITALS", (), ("always",), "vital_signs"),
    SectionDef("8.2.3", "Laboratory/instrumental", 823, "8.2", "SAFETY_LABS", (), ("always",), "safety_labs"),
    SectionDef("8.3", "AE/SAE framework", 830, "8", "AE_FRAMEWORK", (), ("always",), "ae_framework"),
    SectionDef("8.4", "AE follow-up", 840, "8", "AE_FOLLOWUP", (), ("always",), "ae_followup"),
    SectionDef("8.5", "Pregnancy", 850, "8", "PREGNANCY", (), ("always",), "pregnancy"),
    SectionDef("9", "Statistics", 900, None, "STATISTICS_ROOT", ("sample_size",), ("always",), "heading"),
    SectionDef("9.1", "Methods", 910, "9", "STATISTICAL_METHOD", ("design",), ("always",), "statistical_method"),
    SectionDef("9.2", "Sample size", 920, "9", "SAMPLE_SIZE", ("sample_size", "subjects"), ("always",), "sample_size"),
    SectionDef("9.3", "Alpha", 930, "9", "ALPHA", (), ("always",), "alpha"),
    SectionDef("9.4", "Stopping", 940, "9", "STOPPING_STATS", (), ("always",), "stopping_rules"),
    SectionDef("9.5", "Missing data", 950, "9", "MISSING_DATA", (), ("always",), "missing_data_policy"),
    SectionDef("9.6", "Deviations from plan", 960, "9", "SAP_DEVIATIONS", (), ("always",), "sap_deviations"),
    SectionDef("9.7", "Analysis populations", 970, "9", "ANALYSIS_POPS", ("subjects",), ("always",), "analysis_populations"),
    SectionDef("9.7.1", "Statistical analysis", 971, "9.7", "STAT_ANALYSIS", ("design",), ("always",), "statistical_analysis"),
    SectionDef("9.7.1.1", "Descriptive statistics", 972, "9.7.1", "DESCRIPTIVE", (), ("always",), "descriptive_stats"),
    SectionDef("9.7.1.2", "ANOVA", 973, "9.7.1", "ANOVA", ("design",), ("always",), "anova_methods"),
    SectionDef("9.7.2", "BE criteria", 974, "9.7", "BE_CRITERIA", (), ("always",), "be_criteria"),
    SectionDef("9.7.3", "Outliers", 975, "9.7", "OUTLIERS", (), ("always",), "outliers"),
    SectionDef("9.7.4", "Safety analysis", 976, "9.7", "SAFETY_STATS", (), ("always",), "safety_analysis"),
    SectionDef("10", "Direct access / data", 1000, None, "DATA_ACCESS", (), ("always",), "data_access"),
    SectionDef("11", "Quality", 1100, None, "QUALITY", (), ("always",), "standard_text"),
    SectionDef("12", "Ethics", 1200, None, "ETHICS", (), ("always",), "standard_text"),
    SectionDef("13", "Data and records", 1300, None, "DATA_RECORDS", (), ("always",), "standard_text"),
    SectionDef("14", "Financing and insurance", 1400, None, "FINANCING", (), ("always",), "financing_insurance"),
    SectionDef("15", "Publications", 1500, None, "PUBLICATIONS", (), ("always",), "publications"),
    SectionDef("16", "Appendices", 1600, None, "APPENDICES", (), ("always",), "appendices"),
    SectionDef("17", "Итог", 1700, None, "SUMMARY_END", (), ("always",), "conclusion"),
    SectionDef("18", "Literature", 1800, None, "LITERATURE", ("sources",), ("always",), "literature"),
]

SECTION_BY_CODE: dict[str, SectionDef] = {s.section_code: s for s in SECTION_TREE}


@dataclass
class MappingRow:
    section_code: str
    template_key: str
    required_data: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    generator: str = "generic"


def mapping_as_list() -> list[dict]:
    return [
        {
            "section_code": s.section_code,
            "template_key": s.template_key,
            "required_data": list(s.required_data),
            "conditions": list(s.conditions),
            "generator": s.generator,
        }
        for s in SECTION_TREE
    ]

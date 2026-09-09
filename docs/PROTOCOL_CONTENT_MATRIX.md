# Protocol Content Matrix (Phase 12A / 12A.2)

**Version:** CONTENT.FOUNDATION.v2  
**Scope:** Substantive P2 sections — technical classification only.  
**Rule:** No unverified medical / regulatory wording is finalized here. Expert interview answers may change `expert_required` / `type` rows.

Machine-readable twin: `backend/app/domain/content_matrix.py` (`PROTOCOL_CONTENT_MATRIX`).  
Resolution engine: `backend/app/domain/content_resolver.py` (Canonical → Approved ExpertDecision → Verified → Proposed → KnowledgeGap).  
See also: `docs/PHASE12A2_CONTENT_FOUNDATION.md`.

## Legend

| Column | Meaning |
|--------|---------|
| type | DYNAMIC / CONDITIONAL / STATIC_VERIFIED / EXPERT_REQUIRED / UNRESOLVED / NEEDS_REVIEW |
| evidence_required | Needs Verified EvidenceClaim |
| calculation_required | Needs calculated plan (sampling/stats/washout/…) |
| expert_required | Medical writer / expert rule needed before FINAL wording |
| current_status | IMPLEMENTED / PARTIAL / UNRESOLVED |

## Matrix

| section_code | title | type | source_of_truth | dependencies | generator | evidence | calc | expert | status | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 2.2 | Preclinical/clinical summary | EXPERT_REQUIRED | EvidenceClaim VERIFIED | evidence | preclinical_clinical_summary | Y | N | Y | PARTIAL | Wording deferred pending medical writer |
| 2.3 | Risk-benefit | EXPERT_REQUIRED | EvidenceClaim VERIFIED | evidence | risk_benefit | Y | N | Y | PARTIAL | Expert narrative deferred |
| 2.4 | Dose rationale | DYNAMIC | Product.dosage + Evidence | product, evidence | dose_rationale | Y | N | Y | PARTIAL | Dose from product; clinical rationale may need expert |
| 2.7 | Literature basis | EXPERT_REQUIRED | Evidence / Sources | sources, evidence | rationale_literature | Y | N | Y | PARTIAL | |
| 2.8 | Pharmacology | EXPERT_REQUIRED | EvidenceClaim | evidence | pharmacology | Y | N | Y | PARTIAL | |
| 4.3 | Randomization/blinding | DYNAMIC | Design | design | randomization | N | N | N | IMPLEMENTED | DisplayValueRegistry for enums |
| 4.4 | Treatment | DYNAMIC | Design + Food | design, food | treatment | N | N | N | IMPLEMENTED | |
| 4.4.1 | Stages | DYNAMIC | Design periods | design | stages | N | N | N | IMPLEMENTED | |
| 4.4.2 | Blood sampling | DYNAMIC | SamplingPlan | sampling | sampling_plan | N | Y | N | IMPLEMENTED | Canonical sampling |
| 4.5 | Participation duration | DYNAMIC | Observation + Washout + Design | observation, washout, design | participation_duration | N | Y | N | IMPLEMENTED | |
| 4.6 | Stop/exclusion rules | NEEDS_REVIEW | Eligibility + expert practice | eligibility | stop_rules | N | N | Y | PARTIAL | Clinical stop criteria deferred |
| 4.7 | Drug accountability | DYNAMIC | Product / Reference | product, reference | drug_accountability | N | N | N | IMPLEMENTED | |
| 4.7.1 | Test accountability | DYNAMIC | Product | product | drug_accountability_test | N | N | N | IMPLEMENTED | |
| 4.7.2 | Reference accountability | DYNAMIC | ReferenceProduct | reference | drug_accountability_ref | N | N | N | IMPLEMENTED | |
| 4.7.3 | Storage | DYNAMIC | Product/Reference storage | product, reference | storage_conditions | N | N | N | IMPLEMENTED | Unresolved if missing |
| 4.8 | Randomization codes | DYNAMIC | Design blinding | design | randomization_codes | N | N | N | IMPLEMENTED | |
| 4.8.1 | Subject numbering | DYNAMIC | SubjectPlan | subjects | subject_numbering | N | N | N | IMPLEMENTED | |
| 4.8.2 | Code storage/unblinding | NEEDS_REVIEW | SOP / expert | design | unblinding_sop | N | N | Y | PARTIAL | SOP wording deferred |
| 4.8.3 | Blinding | DYNAMIC | Design | design | blinding | N | N | N | IMPLEMENTED | |
| 4.9 | Primary data list | UNRESOLVED | CRF / center SOP | — | primary_data_list | N | N | Y | UNRESOLVED | `{{CRF.PRIMARY_DATA_LIST}}` |
| 6.1 | Treatment detail | DYNAMIC | Design/Food/Washout/Sampling | design, food, washout, sampling | treatment_detail | N | N | N | PARTIAL | Structural; clinical detail deferred |
| 6.1.1 | Procedures timeline | DYNAMIC | ProcedureSchedule | design, sampling, food | procedures_timeline | N | N | N | PARTIAL | Schedule foundation Phase 12A |
| 6.1.2 | Screening | NEEDS_REVIEW | SafetyPlan + Eligibility | safety, eligibility | screening_procedures | N | N | Y | PARTIAL | Battery deferred |
| 6.1.3 | Randomization procedure | DYNAMIC | Design | design | randomization_procedure | N | N | N | IMPLEMENTED | |
| 6.1.4 | Period 1 | DYNAMIC | Design + Food + Sampling | design, food, sampling | period_1 | N | N | N | PARTIAL | |
| 6.1.5 | Washout procedure | DYNAMIC | WashoutPlan | washout | washout_procedure | N | Y | N | IMPLEMENTED | |
| 6.1.6 | Period 2 | DYNAMIC | Design + Food + Sampling | design, food, sampling | period_2 | N | N | N | PARTIAL | |
| 6.1.7 | Final examination | NEEDS_REVIEW | SafetyPlan | safety | final_exam | N | N | Y | PARTIAL | |
| 6.1.8 | Completion | DYNAMIC | Design | design | completion | N | N | N | PARTIAL | |
| 6.1.9 | Sample preparation | EXPERT_REQUIRED | BioanalysisPlan | bioanalysis | sample_prep | N | N | Y | UNRESOLVED | No template defaults |
| 6.1.10 | Concomitant therapy | EXPERT_REQUIRED | Expert / SmPC | evidence | concomitant_therapy | Y | N | Y | PARTIAL | |
| 6.2 | Treatment restrictions | NEEDS_REVIEW | Expert + Food | food | treatment_restrictions | N | N | Y | PARTIAL | |
| 6.2.1 | Food restrictions | CONDITIONAL | FoodCondition + T12 | food | food_restrictions | N | N | N | IMPLEMENTED | T12 STATIC_VERIFIED when FED+HIGH_CALORIE |
| 6.2.2 | Activity restrictions | STATIC_VERIFIED | Template SOP | — | activity_restrictions | N | N | N | NEEDS_REVIEW | Confirm vs expert interview |
| 6.2.3 | Contraception | EXPERT_REQUIRED | Expert / regulatory | — | contraception | N | N | Y | PARTIAL | |
| 6.3 | Compliance | STATIC_VERIFIED | Template boilerplate | — | compliance | N | N | N | NEEDS_REVIEW | |
| 6.3.1 | Withdrawal follow-up | NEEDS_REVIEW | SafetyPlan.follow_up | safety | withdrawal_followup | N | N | Y | PARTIAL | |
| 7.1 | Evaluated parameters | DYNAMIC | Analytes + PK | analytes, pk | eval_parameters | N | N | N | IMPLEMENTED | |
| 7.2 | Methods/timing | DYNAMIC | Sampling + Observation | sampling, observation | eval_methods_timing | N | Y | N | PARTIAL | |
| 7.3 | Analytical method | EXPERT_REQUIRED | BioanalysisPlan | bioanalysis | analytical_method | N | N | Y | UNRESOLVED | |
| 7.3.1 | Bioanalytical method | EXPERT_REQUIRED | BioanalysisPlan | bioanalysis | bioanalysis | N | N | Y | UNRESOLVED | `{{BIOANALYSIS.*}}` |
| 7.3.2 | Validation | EXPERT_REQUIRED | BioanalysisPlan | bioanalysis | bio_validation | N | N | Y | UNRESOLVED | |
| 7.3.3 | Sample analysis | EXPERT_REQUIRED | BioanalysisPlan | bioanalysis | sample_analysis | N | N | Y | UNRESOLVED | |
| 7.3.4 | Run acceptance | EXPERT_REQUIRED | BioanalysisPlan | bioanalysis | run_acceptance | N | N | Y | UNRESOLVED | |
| 8.1 | Safety parameters | NEEDS_REVIEW | SafetyPlan | safety | safety_standard | N | N | Y | PARTIAL | No new thresholds |
| 8.2 | Safety methods/timing | NEEDS_REVIEW | SafetyPlan + ProcedureSchedule | safety, procedures | safety_methods | N | N | Y | PARTIAL | |
| 8.2.1 | Physical exam | NEEDS_REVIEW | SafetyPlan.physical_exam | safety | physical_exam | N | N | Y | PARTIAL | |
| 8.2.2 | Vital signs | STATIC_VERIFIED | SAFE.T13 + SafetyPlan | safety | vital_signs | N | N | N | PARTIAL | Scale table preserved |
| 8.2.3 | Safety labs | STATIC_VERIFIED | T09 + SafetyPlan | safety | safety_labs | N | N | N | PARTIAL | T09 ≠ PK analytes |
| 8.3 | AE/SAE framework | STATIC_VERIFIED | T14–T16 + narrative | safety | ae_framework | N | N | Y | PARTIAL | Scales STATIC; narrative expert |
| 8.4 | AE follow-up | EXPERT_REQUIRED | SafetyPlan.follow_up | safety | ae_followup | N | N | Y | PARTIAL | |
| 8.5 | Pregnancy | EXPERT_REQUIRED | SafetyPlan.pregnancy | safety | pregnancy | N | N | Y | PARTIAL | |
| 9.3 | Alpha | DYNAMIC | StatisticalConfig | statistics | alpha | N | Y | N | IMPLEMENTED | |
| 9.4 | Stopping rules | NEEDS_REVIEW | Stats + expert | statistics | stopping_rules | N | N | Y | PARTIAL | |
| 9.5 | Missing data | NEEDS_REVIEW | SAP / expert | statistics | missing_data_policy | N | N | Y | PARTIAL | |
| 9.6 | SAP deviations | NEEDS_REVIEW | Expert | statistics | sap_deviations | N | N | Y | PARTIAL | |
| 9.7 | Analysis populations | DYNAMIC | SubjectPlan + stats | subjects, statistics | analysis_populations | N | N | N | PARTIAL | |
| 9.7.1 | Statistical analysis | DYNAMIC | Stats engines | statistics | statistical_analysis | N | Y | N | PARTIAL | |
| 9.7.1.1 | Descriptive stats | DYNAMIC | Stats | statistics | descriptive_stats | N | Y | N | PARTIAL | |
| 9.7.1.2 | ANOVA methods | DYNAMIC | Stats | statistics | anova_methods | N | Y | N | PARTIAL | |
| 9.7.2 | BE criteria | DYNAMIC | StatisticalConfig | statistics | be_criteria | N | Y | N | IMPLEMENTED | |
| 9.7.3 | Outliers | NEEDS_REVIEW | Expert / SAP | statistics | outliers | N | N | Y | PARTIAL | |
| 9.7.4 | Safety analysis | NEEDS_REVIEW | SafetyPlan + stats | safety, statistics | safety_analysis | N | N | Y | PARTIAL | |
| 18 | Literature | DYNAMIC | Sources | sources | literature | N | N | N | IMPLEMENTED | Provenance from sources |

## Static vs dynamic (P2 residual)

| Block | Classification | Notes |
|---|---|---|
| SAFE.T13–T16 | STATIC_VERIFIED | AE/vital scales preserved |
| LAB.T09 | STATIC_VERIFIED | Clinical labs ≠ PK |
| SCHED.T08 | STATIC_VERIFIED | 2×2 crossover schedule |
| MEAL.T12_FED | STATIC_VERIFIED / CONDITIONAL | Preserved when FED+HIGH_CALORIE |
| Activity / contraception / compliance narrative | NEEDS_REVIEW | Confirm with medical writer — do not invent |
| Bioanalysis template paragraphs | LEGACY risk → EXPERT_REQUIRED model | No silent defaults from old DOCX |

## Intentionally deferred (medical writer)

- Clinical stop criteria thresholds  
- Bioanalytical method parameters (matrix, LLOQ, acceptance, …)  
- AE causality / seriousness narrative beyond STATIC scales  
- Concomitant therapy / contraception regulatory interpretation  
- Screening / final exam clinical batteries  

## DOCX policy (12A)

- **No** mass P2 section replacement in DOCX.  
- Anchors / ACTIVE_SECTION_CODES for P0–P1 remain as-is.  
- Mapping prepared via this matrix + ProcedureSchedule / BioanalysisPlan / SafetyPlan models.

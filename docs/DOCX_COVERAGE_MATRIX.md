# DOCX Coverage Matrix (Phase 10 audit)

**Date:** 2026-08-26  
**Template:** `templates/protocol/BE_Protocol_Template_v2.0.docx`  
**Checksum:** `8e6be6aa6f0514dc4ba6a1016feb141946a2ded538a58d306bcf0fa68725d8a6`  
**Scope:** Audit only — no code / generators / Research / AI changes.  
**Sources of truth for this audit:** `_template_inspect.json` body headings (93), `SECTION_TREE`, `ACTIVE_SECTION_CODES`, `TABLE_KEY_TO_INDEX`, `docs/DOCX_*_INVENTORY.md`, SPEC §49.

### Legend — `current rendering status`

| Status | Meaning |
|--------|---------|
| `DOCX_REPLACED` | Body overwritten from ProtocolDraft (`ACTIVE_SECTION_CODES`) |
| `DRAFT_ONLY` | ProtocolDraft generator exists; DOCX body still template text |
| `TABLE_FILL` | Dynamic via mapped table fill only (section body may stay template) |
| `TEMPLATE_STATIC` | Template body preserved as-is |
| `NOT_IN_TREE` | Present in template/SPEC; absent from `SECTION_TREE` |
| `HEADING_ONLY` | Structural heading / no body payload |

### Legend — `implementation status`

| Status | Meaning |
|--------|---------|
| `IMPLEMENTED` | Draft + DOCX path wired for study-linked content |
| `PARTIAL` | Draft and/or light fill; DOCX body incomplete vs template depth |
| `NOT_IMPLEMENTED` | No generator / no mapping — gap for later phases |
| `STATIC_OK` | Intentionally static (forms, SOPs, glossary) |

---

## A. Front matter

| section_code | title | current rendering status | current source | required source | dynamic/static/conditional | generator needed | dependencies | blocking fields | current implementation status |
|---|---|---|---|---|---|---|---|---|---|
| COVER | Cover / title block + T01 | TABLE_FILL | study/product light-fill into T01 | study, product, protocol_number, design | dynamic | cover_fields (extend) | study, product | protocol_number, test product | PARTIAL |
| ABBR | Abbreviations (T02) | TEMPLATE_STATIC | template glossary | optional project glossary / sources | static (default) | abbreviations_table (optional) | — | — | STATIC_OK |
| SYNOPSIS | Synopsis (T03 + ProtocolDraft SYNOPSIS) | TABLE_FILL + DRAFT_ONLY | SYNOPSIS_N / STUDY_METADATA cells; draft text not fully in DOCX body | study, design, subjects, products, PK, stats, orgs | dynamic | synopsis (exists) + synopsis_table fill | study, design, subjects, sample_size, orgs | sponsor, N, products | PARTIAL |

---

## B. §1 General information

| section_code | title | current rendering status | current source | required source | type | generator needed | dependencies | blocking fields | status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Общая информация | HEADING_ONLY / DRAFT_ONLY | SECTION_TREE heading | structural | static heading | heading | — | — | PARTIAL |
| 1.1 | Protocol metadata | DOCX_REPLACED | study | study | dynamic | protocol_metadata | study | protocol_number, title, date | IMPLEMENTED |
| 1.2 | Sponsor | DOCX_REPLACED | sponsor / `{{SPONSOR.NAME}}` | organizations.sponsor | dynamic | sponsor | organizations | SPONSOR.NAME | PARTIAL |
| 1.3 | Authorized sponsor persons | DRAFT_ONLY | unresolved_org placeholder | organizations.sponsor_persons | dynamic | unresolved_org → org_details | organizations | SPONSOR_PERSONS.DETAILS | NOT_IMPLEMENTED (DOCX) / PARTIAL (draft) |
| 1.4 | Medical expert | DRAFT_ONLY | unresolved_org | organizations.medical_expert | dynamic | org_details | organizations | MEDICAL_EXPERT.DETAILS | NOT_IMPLEMENTED (DOCX) |
| 1.5 | Investigators / sites | DRAFT_ONLY | unresolved_org | organizations.investigators | dynamic | org_details | organizations | INVESTIGATORS.DETAILS | NOT_IMPLEMENTED (DOCX) |
| 1.6 | Analytical lab | DRAFT_ONLY | unresolved_org | organizations.analytical_lab | dynamic | org_details | organizations | ANALYTICAL_LAB.DETAILS | NOT_IMPLEMENTED (DOCX) |
| 1.7 | Key organizations | DRAFT_ONLY | unresolved_org | organizations.key | dynamic | org_details | organizations | KEY_ORGS.DETAILS | NOT_IMPLEMENTED (DOCX) |
| 1.8 | Signatures | DRAFT_ONLY + T04 static | draft signatures text; T04 preserve | organizations + signature roles | dynamic | signatures + signature_table | organizations | SIGNATURE.SPONSOR, SIGNATURE.INVESTIGATOR | NOT_IMPLEMENTED (T04) / PARTIAL |
| 1.9 | Investigator agreement | DRAFT_ONLY | unresolved_org | organizations | dynamic | investigator_agreement | organizations | INVESTIGATOR_AGREEMENT.DETAILS | NOT_IMPLEMENTED (DOCX) |

---

## C. §2 Rationale (priority focus)

| section_code | title | current rendering status | current source | required source | type | generator needed | dependencies | blocking fields | status |
|---|---|---|---|---|---|---|---|---|---|
| 2 | Обоснование | HEADING_ONLY / DRAFT_ONLY | heading | structural | static heading | heading | — | — | PARTIAL |
| 2.1 | Products | DRAFT_ONLY | heading | structural | static heading | heading | product | — | PARTIAL |
| 2.1.1 | Test product | DOCX_REPLACED + T05 DYNAMIC | product + TEST_PRODUCT table | product | dynamic | test_product | product | TEST_PRODUCT.* | IMPLEMENTED |
| 2.1.2 | Reference product | DOCX_REPLACED + T06 DYNAMIC | reference_product | reference_product | dynamic | reference_product | reference_product | REFERENCE_PRODUCT.* | IMPLEMENTED |
| 2.2 | Preclinical/clinical summary | NOT_IN_TREE / TEMPLATE_STATIC | template (bosutinib sample text) | evidence / research excerpts / expert narrative | dynamic (molecule) | preclinical_clinical_summary | sources, evidence | narrative + source_ids | NOT_IMPLEMENTED |
| 2.3 | Risk-benefit | NOT_IN_TREE / TEMPLATE_STATIC | template | SmPC risks + expert | dynamic/conditional | risk_benefit | sources, product | risks text | NOT_IMPLEMENTED |
| 2.4 | Dose / regimen / duration | NOT_IN_TREE / TEMPLATE_STATIC | template | product.dosage + regimen | dynamic | dose_rationale | product, design | dosage, regimen | NOT_IMPLEMENTED |
| 2.5 | Study conditions | DOCX_REPLACED | food, design | food, design | dynamic | study_conditions | food, design | FOOD.CONDITION | IMPLEMENTED |
| 2.6 | Subjects (rationale) | DOCX_REPLACED | subjects / sample_size | subjects, sample_size | dynamic | subjects_rationale | subjects, sample_size | EVALUABLE_N | IMPLEMENTED |
| 2.7 | Literature links (rationale) | NOT_IN_TREE / TEMPLATE_STATIC | template | sources | dynamic/conditional | rationale_literature | sources | SOURCES | NOT_IMPLEMENTED |
| 2.8 | Pharmacological properties | NOT_IN_TREE / TEMPLATE_STATIC | template (bosutinib-specific) | molecule PK/PD narrative from sources | dynamic (molecule) | pharmacology | sources, analytes | pharmacology text | NOT_IMPLEMENTED |
| 2.9 | Test product details | NOT_IN_TREE / TEMPLATE_STATIC | template | product (extended attrs) | dynamic | test_product_details | product | product attrs | NOT_IMPLEMENTED |
| 2.10 | Reference justification | DOCX_REPLACED | reference_product | reference_product + sources | dynamic | reference_justification | reference_product | REFERENCE_PRODUCT | IMPLEMENTED |
| 2.11 | Observation duration rationale | DOCX_REPLACED | observation, half-life | observation | dynamic | observation_rationale | observation, analytes | OBSERVATION.DURATION | IMPLEMENTED |
| 2.12 | Washout rationale | DOCX_REPLACED | washout | washout | conditional (crossover) | washout_rationale | washout, design | WASHOUT | IMPLEMENTED |

---

## D. §3 Objectives

| section_code | title | current rendering status | current source | required source | type | generator needed | dependencies | blocking fields | status |
|---|---|---|---|---|---|---|---|---|---|
| 3 | Цель и задачи | DRAFT_ONLY | objectives generator → draft | study objectives | dynamic | objectives (exists) | study, design | objectives text | PARTIAL — **DOCX body not replaced** |

---

## E. §4 Design (priority focus 4.3–4.9)

| section_code | title | current rendering status | current source | required source | type | generator needed | dependencies | blocking fields | status |
|---|---|---|---|---|---|---|---|---|---|
| 4 | Дизайн | HEADING_ONLY / DRAFT_ONLY | heading | structural | heading | heading | design | — | PARTIAL |
| 4.1 | PK parameters | DOCX_REPLACED + T07 DYNAMIC | pk_parameters / analytes | pk_parameters | dynamic | pk_parameters | analytes, pk | PK rows | IMPLEMENTED |
| 4.2 | Design description + T08/T09 | DOCX_REPLACED; T08/T09 static | design text; schedule tables preserved | design + schedule model | dynamic + tables | design + schedule_of_assessments | design, periods | DESIGN.TYPE | PARTIAL (T08/T09 NOT_IMPLEMENTED) |
| 4.3 | Randomization / blinding | DRAFT_ONLY | randomization generator | design.blinding, sequences | dynamic | randomization (exists) | design | DESIGN sequences | PARTIAL — **no DOCX replace** |
| 4.4 | Treatment / dosing / packaging | DRAFT_ONLY | treatment generator | design, food, products | dynamic | treatment (exists) | design, food, products | products, food | PARTIAL — **no DOCX replace** |
| 4.4.1 | Stages / period duration | DRAFT_ONLY | stages generator | design.periods | dynamic | stages (exists) | design | periods | PARTIAL — **no DOCX replace** |
| 4.4.2 | Blood sampling | DOCX_REPLACED + T10 DYNAMIC | sampling plan | sampling | dynamic | sampling_plan | sampling, analytes | SAMPLING points | IMPLEMENTED |
| 4.5 | Participation duration | DRAFT_ONLY | participation_duration | observation, washout, periods | dynamic | participation_duration (exists) | observation, washout | durations | PARTIAL — **no DOCX replace** |
| 4.6 | Stop / exclusion rules | NOT_IN_TREE / TEMPLATE_STATIC | template | eligibility + study stop rules | dynamic/conditional | stop_rules | eligibility, design | stop criteria | NOT_IMPLEMENTED |
| 4.7 | Drug accountability | NOT_IN_TREE / TEMPLATE_STATIC | template | products + pharmacy SOP | dynamic/static mix | drug_accountability | products | product identity | NOT_IMPLEMENTED |
| 4.7.1 | Test product accountability | NOT_IN_TREE / TEMPLATE_STATIC | template | product | dynamic | drug_accountability_test | product | product | NOT_IMPLEMENTED |
| 4.7.2 | Reference accountability | NOT_IN_TREE / TEMPLATE_STATIC | template | reference_product | dynamic | drug_accountability_ref | reference_product | reference | NOT_IMPLEMENTED |
| 4.7.3 | Storage / control | NOT_IN_TREE / TEMPLATE_STATIC | template | storage conditions | static/conditional | storage_conditions | products | storage | NOT_IMPLEMENTED |
| 4.8 | Randomization codes | NOT_IN_TREE / TEMPLATE_STATIC | template | design randomization policy | dynamic | randomization_codes | design | blinding policy | NOT_IMPLEMENTED |
| 4.8.1 | Subject number assignment | NOT_IN_TREE / TEMPLATE_STATIC | template | subject numbering rule | dynamic | subject_numbering | subjects, design | numbering | NOT_IMPLEMENTED |
| 4.8.2 | Code storage / unblinding | NOT_IN_TREE / TEMPLATE_STATIC | template | unblinding SOP | static/conditional | unblinding_sop | design | — | NOT_IMPLEMENTED |
| 4.8.3 | Blinding / masking | NOT_IN_TREE / TEMPLATE_STATIC | template | design.blinding | dynamic/conditional | blinding | design | blinding type | NOT_IMPLEMENTED |
| 4.9 | Direct primary data (CRF) | NOT_IN_TREE / TEMPLATE_STATIC | template | CRF/primary data list | static/conditional | primary_data_list | procedures | — | NOT_IMPLEMENTED |

---

## F. §5 Eligibility

| section_code | title | current rendering status | current source | required source | type | generator needed | dependencies | blocking fields | status |
|---|---|---|---|---|---|---|---|---|---|
| 5 | Subjects root | DRAFT_ONLY heading | heading | structural | heading | heading | — | — | PARTIAL |
| 5.1 | Inclusion | DOCX_REPLACED | eligibility.inclusion | eligibility.inclusion | dynamic | inclusion | eligibility | ELIGIBILITY.INCLUSION | IMPLEMENTED (empty → unresolved) |
| 5.2 | Non-inclusion | DOCX_REPLACED | eligibility.non_inclusion | eligibility.non_inclusion | dynamic | non_inclusion | eligibility | ELIGIBILITY.NON_INCLUSION | IMPLEMENTED |
| 5.3 | Exclusion | DOCX_REPLACED | eligibility.exclusion | eligibility.exclusion | dynamic | exclusion | eligibility | ELIGIBILITY.EXCLUSION | IMPLEMENTED |

---

## G. §6 Treatment procedures (priority 6.1–6.3)

| section_code | title | current rendering status | current source | required source | type | generator needed | dependencies | blocking fields | status |
|---|---|---|---|---|---|---|---|---|---|
| 6 | Treatment procedures (H1 in template titled oddly) | DRAFT_ONLY heading | heading | structural | heading | heading | design, food | — | PARTIAL |
| 6.1 | Treatment overview | DRAFT_ONLY | treatment_detail | design, products, food | dynamic | treatment_detail (exists) | design, products | products | PARTIAL — **no DOCX replace** |
| 6.1.1 | Procedures | NOT_IN_TREE / TEMPLATE_STATIC | template | procedure schedule | dynamic | procedures_timeline | design, sampling | schedule | NOT_IMPLEMENTED |
| 6.1.2 | Screening (+ T11) | NOT_IN_TREE / TEMPLATE_STATIC | template + T11 static | screening panel | dynamic/static | screening_procedures | eligibility, labs | screening tests | NOT_IMPLEMENTED |
| 6.1.3 | Randomization (procedure) | NOT_IN_TREE / TEMPLATE_STATIC | template | design sequences | dynamic | randomization_procedure | design | sequences | NOT_IMPLEMENTED |
| 6.1.4 | Period I (+ T12) | NOT_IN_TREE / TEMPLATE_STATIC | template + T12 | period plan + food timing | conditional | period_1 | design, food, sampling | food, dosing time | NOT_IMPLEMENTED |
| 6.1.5 | Washout | DRAFT_ONLY | washout_procedure (crossover) | washout | conditional | washout_procedure (exists) | washout, design | WASHOUT | PARTIAL — **no DOCX replace** |
| 6.1.6 | Period II | NOT_IN_TREE / TEMPLATE_STATIC | template | period plan | conditional (crossover) | period_2 | design, food | periods≥2 | NOT_IMPLEMENTED |
| 6.1.7 | Final examination | NOT_IN_TREE / TEMPLATE_STATIC | template | end-of-study exams | dynamic/static | final_exam | safety, labs | — | NOT_IMPLEMENTED |
| 6.1.8 | Study completion | NOT_IN_TREE / TEMPLATE_STATIC | template | completion criteria | static/conditional | completion | design | — | NOT_IMPLEMENTED |
| 6.1.9 | Blood sample preparation | NOT_IN_TREE / TEMPLATE_STATIC | template | bioanalytical handling | dynamic/static | sample_prep | sampling, blood_volume | handling | NOT_IMPLEMENTED |
| 6.1.10 | Concomitant / emergency therapy | NOT_IN_TREE / TEMPLATE_STATIC | template | allowed/prohibited meds | static/conditional | concomitant_therapy | — | — | NOT_IMPLEMENTED |
| 6.2 | Allowed/prohibited treatments | NOT_IN_TREE / TEMPLATE_STATIC | template | medication restrictions | static/conditional | treatment_restrictions | food, meds | — | NOT_IMPLEMENTED |
| 6.2.1 | Food restrictions | DOCX_REPLACED | food | food | dynamic | food_restrictions | food | FOOD.* | IMPLEMENTED |
| 6.2.2 | Physical activity | NOT_IN_TREE / TEMPLATE_STATIC | template | activity restrictions | static | activity_restrictions | — | — | STATIC_OK / NOT_IMPLEMENTED if site-specific |
| 6.2.3 | Contraception | NOT_IN_TREE / TEMPLATE_STATIC | template | contraception rules | static/conditional | contraception | population | — | STATIC_OK / gap if dynamic |
| 6.3 | Compliance methods | NOT_IN_TREE / TEMPLATE_STATIC | template | compliance SOP | static | compliance | — | — | STATIC_OK |
| 6.3.1 | Follow-up after withdrawal | NOT_IN_TREE / TEMPLATE_STATIC | template | withdrawal follow-up | static/conditional | withdrawal_followup | — | — | STATIC_OK |

---

## H. §7 Evaluated parameters (priority 7.1–7.3)

| section_code | title | current rendering status | current source | required source | type | generator needed | dependencies | blocking fields | status |
|---|---|---|---|---|---|---|---|---|---|
| 7 | Оцениваемые параметры | DRAFT_ONLY heading | heading | structural | heading | heading | analytes | — | PARTIAL |
| 7.1 | Parameters | DRAFT_ONLY | eval_parameters | pk_parameters, analytes | dynamic | eval_parameters (exists) | pk, analytes | PK list | PARTIAL — **no DOCX replace**; heading may be missing from inspect H2 list |
| 7.2 | Methods / timing | NOT_IN_TREE / TEMPLATE_STATIC | template | assessment timing | dynamic | eval_methods_timing | sampling, design | timing | NOT_IMPLEMENTED |
| 7.3 | Analytical method (parent) | NOT_IN_TREE / TEMPLATE_STATIC | template | bioanalysis | dynamic | analytical_method | analytes | method | NOT_IMPLEMENTED |
| 7.3.1 | Bioanalytical method | DRAFT_ONLY | bioanalysis generator | analytes / method | dynamic | bioanalysis (exists) | analytes | method text | PARTIAL — **no DOCX replace** |
| 7.3.2 | Validation | NOT_IN_TREE / TEMPLATE_STATIC | template | method validation | dynamic/static | bio_validation | analytes | validation | NOT_IMPLEMENTED |
| 7.3.3 | Sample analysis | NOT_IN_TREE / TEMPLATE_STATIC | template | analysis workflow | static/conditional | sample_analysis | — | — | NOT_IMPLEMENTED |
| 7.3.4 | Run acceptance/rejection | NOT_IN_TREE / TEMPLATE_STATIC | template | acceptance criteria | static | run_acceptance | — | — | STATIC_OK / NOT_IMPLEMENTED |

---

## I. §8 Safety (priority 8.1–8.5)

| section_code | title | current rendering status | current source | required source | type | generator needed | dependencies | blocking fields | status |
|---|---|---|---|---|---|---|---|---|---|
| 8 | Безопасность | DRAFT_ONLY heading | heading | structural | heading | heading | — | — | PARTIAL |
| 8.1 | Safety parameters | DOCX_REPLACED | safety_standard text | safety parameter list | dynamic/static | safety_standard (exists) | — | safety list | PARTIAL (generic, not study-specific labs) |
| 8.2 | Safety methods/timing | TEMPLATE_STATIC | template | schedule of safety assessments | dynamic/static | safety_methods | design | — | NOT_IMPLEMENTED |
| 8.2.1 | Physical exam | TEMPLATE_STATIC | template | physical exam SOP | static | — | — | — | STATIC_OK |
| 8.2.2 | Vital signs (+ T13) | TEMPLATE_STATIC | template + T13 | vital sign limits | static | — | — | — | STATIC_OK |
| 8.2.3 | Lab / instrumental | TEMPLATE_STATIC | template | lab panel | dynamic/static | safety_labs | analytes/labs | — | NOT_IMPLEMENTED |
| 8.3 | AE/SAE reporting | TEMPLATE_STATIC | template | AE SOP | static | — | — | — | STATIC_OK |
| 8.3.1 | Medical events | TEMPLATE_STATIC | template | definitions | static | — | — | — | STATIC_OK |
| 8.3.2 | AE definition | TEMPLATE_STATIC | template | definitions | static | — | — | — | STATIC_OK |
| 8.3.3 | Severity (+ T14) | TEMPLATE_STATIC | template + T14 | severity scale | static | — | — | — | STATIC_OK |
| 8.3.4 | Causality (+ T15) | TEMPLATE_STATIC | template + T15 | causality scale | static | — | — | — | STATIC_OK |
| 8.3.5 | Seriousness (+ T16) | TEMPLATE_STATIC | template + T16 | seriousness criteria | static | — | — | — | STATIC_OK |
| 8.3.6 | AE registration | TEMPLATE_STATIC | template | AE form process | static | — | — | — | STATIC_OK |
| 8.3.7 | SAE registration | TEMPLATE_STATIC | template | SAE form process | static | — | — | — | STATIC_OK |
| 8.4 | AE follow-up duration | TEMPLATE_STATIC | template | follow-up window | static/conditional | ae_followup | observation | — | STATIC_OK / gap |
| 8.5 | Pregnancy | TEMPLATE_STATIC | template | pregnancy reporting | static | — | — | — | STATIC_OK |

---

## J. §9 Statistics (priority 9.3–9.7)

| section_code | title | current rendering status | current source | required source | type | generator needed | dependencies | blocking fields | status |
|---|---|---|---|---|---|---|---|---|---|
| 9 | Statistics root | DRAFT_ONLY heading | heading | structural | heading | heading | sample_size | — | PARTIAL |
| 9.1 | Statistical methods | DOCX_REPLACED | statistical_method | stats config / design | dynamic | statistical_method | design, stats | analysis method | IMPLEMENTED |
| 9.2 | Sample size (+ T17) | DOCX_REPLACED + T17 CONDITIONAL | sample_size, CV | sample_size, cv_selection | dynamic | sample_size + CV_EVIDENCE | sample_size, CV | CV, N, power | IMPLEMENTED |
| 9.3 | Alpha / significance | DRAFT_ONLY | alpha generator | stats.alpha | dynamic | alpha (exists) | stats | ALPHA | PARTIAL — **no DOCX replace** |
| 9.4 | Stopping criteria | NOT_IN_TREE / TEMPLATE_STATIC | template | stopping rules | conditional | stopping_rules | design | — | NOT_IMPLEMENTED |
| 9.5 | Missing / unanalysable data | NOT_IN_TREE / TEMPLATE_STATIC | template | missing-data policy | static/conditional | missing_data_policy | stats | — | NOT_IMPLEMENTED |
| 9.6 | Deviations from statistical plan | NOT_IN_TREE / TEMPLATE_STATIC | template | SAP deviation process | static | sap_deviations | — | — | STATIC_OK |
| 9.7 | Analysis populations | NOT_IN_TREE / TEMPLATE_STATIC | template | analysis sets | dynamic/static | analysis_populations | subjects, design | — | NOT_IMPLEMENTED |
| 9.7.1 | Statistical analysis | NOT_IN_TREE / TEMPLATE_STATIC | template | analysis narrative | dynamic | statistical_analysis | stats | — | NOT_IMPLEMENTED |
| 9.7.1.1 | Descriptive statistics | NOT_IN_TREE / TEMPLATE_STATIC | template | descriptive methods | static/dynamic | descriptive_stats | stats | — | NOT_IMPLEMENTED |
| 9.7.1.2 | ANOVA | NOT_IN_TREE / TEMPLATE_STATIC | template | ANOVA model | dynamic | anova_methods | design, stats | — | NOT_IMPLEMENTED |
| 9.7.2 | BE criteria | DRAFT_ONLY | be_criteria | BE limits | dynamic | be_criteria (exists) | stats | BE limits | PARTIAL — **no DOCX replace** |
| 9.7.3 | Outliers | NOT_IN_TREE / TEMPLATE_STATIC | template | outlier policy | static/conditional | outliers | stats | — | NOT_IMPLEMENTED |
| 9.7.4 | Safety analysis | NOT_IN_TREE / TEMPLATE_STATIC | template | safety stats | static | safety_analysis | — | — | STATIC_OK |

---

## K. §10–18 Admin / Appendices / Literature

| section_code | title | current rendering status | current source | required source | type | generator needed | dependencies | blocking fields | status |
|---|---|---|---|---|---|---|---|---|---|
| 10 | Direct access / data (tree) | DRAFT_ONLY heading | heading | structural | heading | heading | — | — | PARTIAL |
| 10.1 | Completion | TEMPLATE_STATIC | template | completion policy | static/conditional | study_completion_admin | — | — | NOT_IMPLEMENTED |
| 10.2 | Protocol compliance | TEMPLATE_STATIC | template | compliance | static | — | — | — | STATIC_OK |
| 10.3 | Protocol deviations | TEMPLATE_STATIC | template | deviation process | static | — | — | — | STATIC_OK |
| 10.4 | Data retention (+ appendix forms nearby) | TEMPLATE_STATIC | template | retention policy | static | — | — | — | STATIC_OK |
| 11 | Quality | DRAFT_ONLY | standard_text | QA text / org | static/dynamic | standard_text / quality | — | — | PARTIAL (generic draft; DOCX static) |
| 12 | Ethics | DRAFT_ONLY | standard_text | ethics / IEC | static/dynamic | ethics | organizations | IEC | PARTIAL |
| 13 | Data and records | DRAFT_ONLY | standard_text | records SOP | static | standard_text | — | — | PARTIAL / STATIC_OK |
| 14 | Financing and insurance | DRAFT_ONLY | unresolved_org | financing/insurance | dynamic | financing | organizations | FINANCING.DETAILS | PARTIAL |
| 15 | Publications | DRAFT_ONLY | standard_text | publication policy | static | standard_text | — | — | PARTIAL / STATIC_OK |
| 16 | Appendices | DRAFT_ONLY + forms STATIC | appendices stub; T18–T33 preserve | appendix index; forms static | static (forms) / dynamic (index) | appendices | — | — | PARTIAL / STATIC_OK forms |
| 17 | Итог | DRAFT_ONLY heading | heading | optional summary | static/dynamic | heading / summary | — | — | PARTIAL |
| 18 | Literature | DRAFT_ONLY | literature + SOURCES table (not mapped to DOCX table index) | sources | dynamic | literature (exists) | sources | SOURCES.LIST | PARTIAL — **no DOCX replace**; SOURCES table not in TABLE_KEY_TO_INDEX |

---

## L. Tables T01–T33

| table_id | title (from template) | current status | static/dynamic/conditional | source data | required generator | current implementation | target implementation |
|---|---|---|---|---|---|---|---|
| T01 | Study metadata | PARTIAL fill | dynamic | study, product, design | study_metadata_table | light label-value fill + STUDY_METADATA key | full row mapping from Study |
| T02 | Abbreviations | preserved | static | template glossary | optional abbreviations | preserve | keep static unless project glossary |
| T03 | Synopsis | PARTIAL fill | dynamic | SYNOPSIS / SYNOPSIS_N | synopsis_table | SYNOPSIS_N fill | full synopsis field mapping |
| T04 | Signatures | preserved | dynamic (needed) | organizations / roles | signature_table | **NOT_IMPLEMENTED** | fill/ensure signature rows |
| T05 | Test product | DYNAMIC | dynamic | product / TEST_PRODUCT | product_table | fill_label_value | keep / enrich attrs |
| T06 | Reference product | DYNAMIC | dynamic | reference_product | product_table | fill_label_value | keep / enrich |
| T07 | PK parameters | DYNAMIC | dynamic | PK_PARAMETERS | pk_table | rebuild_data_rows | keep |
| T08 | Schedule of assessments | preserved | dynamic (needed) | design periods / procedures | schedule_of_assessments | **NOT_IMPLEMENTED** | rebuild from design schedule |
| T09 | Laboratory parameters | preserved | dynamic/conditional | labs / analytes | lab_parameters_table | **NOT_IMPLEMENTED** | fill from lab panel |
| T10 | Blood sampling | DYNAMIC | dynamic | BLOOD_SAMPLING | sampling_table | rebuild_data_rows | keep; align volumes/windows |
| T11 | Screening drug/alcohol/pregnancy | preserved | static | screening panel | optional screening_table | preserve | static unless panel varies |
| T12 | Dosing / meal timing | preserved | conditional (food) | food timing | meal_timing_table | **NOT_IMPLEMENTED** (preserve) | fill from food entity |
| T13 | Vital sign deviations | preserved | static | SOP limits | — | preserve | STATIC_OK |
| T14 | AE severity | preserved | static | severity scale | — | preserve | STATIC_OK |
| T15 | Causality | preserved | static | causality scale | — | preserve | STATIC_OK |
| T16 | Seriousness | preserved | static | seriousness list | — | preserve | STATIC_OK |
| T17 | CV evidence | CONDITIONAL dynamic | conditional | CV_EVIDENCE / cv_studies | cv_evidence_table | rebuild if rows exist | keep |
| T18 | Protocol ID / AE form header | preserved | static | forms | — | preserve | STATIC_OK (appendices) |
| T19 | AE form fields | preserved | static | forms | — | preserve | STATIC_OK |
| T20 | Suspected drug / reaction | preserved | static | forms | — | preserve | STATIC_OK |
| T21 | Concomitant drugs | preserved | static | forms | — | preserve | STATIC_OK |
| T22 | Manufacturer block | preserved | static | forms | — | preserve | STATIC_OK |
| T23 | Patient grid | preserved | static | forms | — | preserve | STATIC_OK |
| T24 | AE outcome | preserved | static | forms | — | preserve | STATIC_OK |
| T25 | Investigator signature (form) | preserved | static | forms | — | preserve | STATIC_OK |
| T26 | Initials / patient no. | preserved | static | forms | — | preserve | STATIC_OK |
| T27 | SAE form (large) | preserved | static | forms | — | preserve | STATIC_OK |
| T28 | SAE header block | preserved | static | forms | — | preserve | STATIC_OK |
| T29 | Pregnancy report | preserved | static | forms | — | preserve | STATIC_OK |
| T30 | Pregnancy header | preserved | static | forms | — | preserve | STATIC_OK |
| T31 | Pregnancy continuation | preserved | static | forms | — | preserve | STATIC_OK |
| T32 | Pregnancy header (repeat) | preserved | static | forms | — | preserve | STATIC_OK |
| T33 | Pregnancy closing | preserved | static | forms | — | preserve | STATIC_OK |

---

## M. Totals (this audit)

Universe = front-matter (3) + all unique body `section_hint` codes from template inspect + SPEC §49 codes missing from inspect (3, 7.x, 8/9/11–18 parents, etc.) as audited rows above.

### Sections (audited rows)

| Metric | Count |
|--------|------:|
| **total sections (audited)** | **118** |
| **generated dynamically (DOCX_REPLACED and/or DYNAMIC table-driven core)** | **19** |
| **static (TEMPLATE_STATIC / STATIC_OK intended)** | **52** |
| **conditional** | **14** |
| **not implemented (NOT_IN_TREE or DOCX/table gap requiring future work)** | **61** |

Notes on section counts:
- A row may be both *conditional* and *not implemented* (counted in both where applicable for gap planning).
- **DOCX_REPLACED active list = 19 codes** (`ACTIVE_SECTION_CODES`).
- **SECTION_TREE = 56** draft sections; only 19 of those overwrite DOCX bodies.
- **NOT_IMPLEMENTED** emphasizes template headings without Study/ProtocolDraft→DOCX binding.

### Tables

| Metric | Count |
|--------|------:|
| **total tables** | **33** |
| **dynamic tables (wired)** | **7** (T01 partial, T03 partial, T05, T06, T07, T10, T17 conditional) |
| **static tables** | **22** (T02, T11, T13–T16, T18–T33) |
| **not implemented tables** | **4** (T04, T08, T09, T12) — needed dynamic/conditional but not wired |

Strict “fully dynamic implemented”: **T05, T06, T07, T10** (+ **T17** when CV rows exist). T01/T03 = partial.

---

## N. Gap summary (what must become dynamic later)

Highest priority Study-linked gaps (template still static / draft-only):

1. **2.2–2.4, 2.7–2.9** — molecule/rationale narratives  
2. **3** — objectives body into DOCX  
3. **4.3–4.9** — randomization, accountability, blinding, stop rules  
4. **6.1–6.3** (except 6.2.1) — period procedures, T12 meal timing  
5. **7.1–7.3.*** — bioanalysis depth into DOCX  
6. **9.3–9.7.*** (except 9.1/9.2) — stats detail into DOCX  
7. **1.3–1.9 / T04** — organizations & signatures  
8. **18 Literature** — DOCX replace + SOURCES mapping  
9. **T08/T09** — schedule & lab tables  

Intentionally static (keep): abbreviations (default), AE/SOP scales T13–T16, appendix forms T18–T33, most 8.2–8.5 / 10.2–10.4 boilerplate.

**STOP.**

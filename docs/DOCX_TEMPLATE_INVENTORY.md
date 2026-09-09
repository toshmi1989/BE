# DOCX Template Inventory

Source: `templates/protocol/BE_Protocol_Template_v2.0.docx`  
Checksum (sha256): `8e6be6aa6f0514dc4ba6a1016feb141946a2ded538a58d306bcf0fa68725d8a6`  
Stats: 1432 paragraphs, 33 tables, 93 body Heading styles, TOC styles separate.  
Meaningful bookmarks: `СХЕМАотбораКРОВИ`, `ОБЬЕМкрови`, `ОБЪЕМкровиСЕРОЛ`, `ОБЪЕМкровиКАТЕТЕР`, `ОБЩИЙобъемКРОВИ`.

Anchors are **section_code via Heading text** (not paragraph index). TOC entries are ignored for rendering.

| Section/Table | Template Location | Protocol Data Source | Rendering Strategy | Condition | Status |
|---|---|---|---|---|---|
| Cover / title block | Early body + T01 | study, product, protocol_number | fill_cover_fields | always | mapped |
| Abbreviations | T02 | static template / sources | preserve_or_static | always | mapped |
| Synopsis | T03 | ProtocolDraft SYNOPSIS | fill_synopsis_table | always | mapped |
| 1.1 Protocol metadata | Heading 2 `1.1` | study | replace_section_body | always | mapped |
| 1.2 Sponsor | Heading 2 `1.2` | sponsor/org | replace_section_body | always | mapped |
| 1.3 Sponsor persons | Heading 2 `1.3` | organizations | replace_section_body | always | mapped |
| 1.4 Medical expert | Heading 2 `1.4` | organizations | replace_section_body | always | mapped |
| 1.5 Investigators | Heading 2 `1.5` | organizations | replace_section_body | always | mapped |
| 1.6 Analytical lab | Heading 2 `1.6` | organizations | replace_section_body | always | mapped |
| 1.7 Key organizations | Heading 2 `1.7` | organizations | replace_section_body | always | mapped |
| 1.8 Signatures | Heading 2 `1.8` + T04 | signature blocks | fill_signature_table | always | mapped |
| 1.9 Investigator agreement | Heading 2 `1.9` | organizations | replace_section_body | always | mapped |
| 2.1 Products | Heading 2 `2.1` | products | heading_keep | always | mapped |
| 2.1.1 Test product | Heading 2 `2.1.1` + T05 | product | fill_product_table + body | always | mapped |
| 2.1.2 Reference product | Heading 2 `2.1.2` + T06 | reference_product | fill_product_table + body | always | mapped |
| 2.2–2.4 Preclinical / risk / dose | Heading 2 | optional / UNRESOLVED | preserve_template_or_mark | optional | preserve |
| 2.5 Study conditions | Heading 2 `2.5` | food, design | replace_section_body | always | mapped |
| 2.6 Subjects | Heading 2 `2.6` | subjects | replace_section_body | always | mapped |
| 2.7 Literature links | Heading 2 `2.7` | sources | replace_section_body | optional | mapped |
| 2.8 Pharmacology | Heading 2 `2.8*` | template / UNRESOLVED | preserve | molecule-specific | preserve |
| 2.9 Test product details | Heading 2 `2.9` | product | replace_section_body | always | mapped |
| 2.10 Reference justification | Heading 2 `2.10` | reference_product | replace_section_body | always | mapped |
| 2.11 Observation rationale | Heading 2 `2.11` | observation | replace_section_body | always | mapped |
| 2.12 Washout rationale | Heading 2 `2.12` | washout | replace_section_body | crossover | mapped |
| 3 Objectives | body section 3 | study/design | replace_or_preserve | always | mapped |
| 4.1 PK parameters | Heading 2 `4.1` + T07 | pk_parameters / ProtocolTable PK_PARAMETERS | fill_pk_table | always | mapped |
| 4.2 Design | Heading 2 `4.2` + T08/T09 | design | replace_section_body + schedule table | always | mapped |
| 4.3 Randomization | Heading 2 `4.3` | design | replace_section_body | always | mapped |
| 4.4 Treatment | Heading 2 `4.4` | design/food | replace_section_body | always | mapped |
| 4.4.1 Stages | Heading 2 `4.4.1` | design.periods | replace_section_body | always | mapped |
| 4.4.2 Blood sampling | Heading 2 `4.4.2` + T10 + bookmark СХЕМАотбораКРОВИ | sampling ProtocolTable BLOOD_SAMPLING | fill_sampling_table | always | mapped |
| 4.5–4.9 | Heading 2 | ProtocolDraft / template | replace_or_preserve | always | partial |
| 5.1 Inclusion | Heading 2 `5.1` | eligibility.inclusion | replace_list | always | mapped |
| 5.2 Non-inclusion | Heading 2 `5.2` | eligibility.non_inclusion | replace_list | always | mapped |
| 5.3 Exclusion | Heading 2 `5.3` | eligibility.exclusion | replace_list | always | mapped |
| 6.* Treatment procedures | Heading 1/2 `6*` | design/food/washout | replace_or_preserve | design-dependent | partial |
| 6.2.1 Food restrictions | Heading 2 `6.2.1` + T12 | food | replace_section_body | always | mapped |
| 7 Bioanalysis | body | analytes | replace_or_preserve | always | partial |
| 8 Safety | Heading 2 `8*` + T13–T16 | safety text blocks | preserve_static + standard text | always | mapped |
| 9 Statistics | Heading 2 `9*` + T17 | sample_size / CV | replace + fill_cv_table | always | mapped |
| 9.2 Sample size | Heading 2 `9.2` | ProtocolDraft 9.2 | replace_section_body | always | mapped |
| 10–15 Admin | headings | template | preserve | always | preserve |
| 16 Appendices | appendices + T18–T33 | appendix forms | preserve_static_forms | always | mapped |
| 17–18 Literature | headings | sources | replace_or_preserve | always | mapped |

Notes:

- Body structure differs from TOC (e.g. 2.9–2.12 present in body). Inventory follows **body headings**.
- Paragraph indexes are informational only; runtime uses section_code → Heading text match.
- Raw inspection dump: `docs/_template_inspect.json` (generated, not source of truth).

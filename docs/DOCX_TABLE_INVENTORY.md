# DOCX Table Inventory (33 tables)

Template: `BE_Protocol_Template_v2.0.docx`  
Checksum: `8e6be6aa6f0514dc4ba6a1016feb141946a2ded538a58d306bcf0fa68725d8a6`

| table_id | Title (from first row / context) | Location/anchor | Source data | Dynamic/static | Conditional | Rendering strategy |
|---|---|---|---|---|---|---|
| T01 | Study metadata | Cover / early body | study, product, design | dynamic cells | always | fill_label_value_rows |
| T02 | Abbreviations | Early body | static template | static | always | preserve |
| T03 | Synopsis | Synopsis block | ProtocolDraft SYNOPSIS / consistency | dynamic cells | always | fill_synopsis_rows |
| T04 | Signatures | §1.8 | organizations / signatures | dynamic rows | always | ensure_signature_rows |
| T05 | Test product | §2.1.1 | product / TEST_PRODUCT | dynamic cells | always | fill_label_value_rows |
| T06 | Reference product | §2.1.2 | reference_product / REFERENCE_PRODUCT | dynamic cells | always | fill_label_value_rows |
| T07 | PK parameters | §4.1 | PK_PARAMETERS | dynamic rows | always | rebuild_data_rows_keep_header |
| T08 | Schedule of assessments | §4.2 | design periods (template skeleton) | mostly static | always | preserve_or_light_fill |
| T09 | Laboratory parameters | §4.2 | analytes / lab params | dynamic/static | always | preserve_or_light_fill |
| T10 | Blood sampling | §4.4.2 / bookmark СХЕМАотбораКРОВИ | BLOOD_SAMPLING | dynamic rows | always | rebuild_data_rows_keep_header |
| T11 | Screening drug/alcohol/pregnancy | §6.1.2 | template | static | always | preserve |
| T12 | Dosing/meal timing | §6.1.4 | food | static/conditional | food | preserve_or_note |
| T13 | Vital sign deviations | §8.2.2 | template | static | always | preserve |
| T14 | AE severity | §8.3.3 | template | static | always | preserve |
| T15 | Causality | §8.3.4 | template | static | always | preserve |
| T16 | Seriousness | §8.3.5 | template | static | always | preserve |
| T17 | CV evidence | §9.x | CV_EVIDENCE | dynamic rows | if CV present | rebuild_data_rows_keep_header |
| T18 | Appendix / AE form start | Appendices | template forms | static | always | preserve |
| T19 | Appendix form | Appendices | template | static | always | preserve |
| T20 | Appendix form | Appendices | template | static | always | preserve |
| T21 | Appendix form | Appendices | template | static | always | preserve |
| T22 | Appendix form | Appendices | template | static | always | preserve |
| T23 | Appendix grid | Appendices | template | static | always | preserve |
| T24 | Appendix | Appendices | template | static | always | preserve |
| T25 | Appendix | Appendices | template | static | always | preserve |
| T26 | Appendix | Appendices | template | static | always | preserve |
| T27 | Appendix | Appendices | template | static | always | preserve |
| T28 | Appendix | Appendices | template | static | always | preserve |
| T29 | Appendix | Appendices | template | static | always | preserve |
| T30 | Appendix | Appendices | template | static | always | preserve |
| T31 | Appendix | Appendices | template | static | always | preserve |
| T32 | Appendix | Appendices | template | static | always | preserve |
| T33 | Appendix | Appendices | template | static | always | preserve |

Mapping to ProtocolDraft `table_key`:

| Protocol table_key | Template table_id |
|---|---|
| STUDY_METADATA | T01 |
| SYNOPSIS (fields) | T03 |
| TEST_PRODUCT | T05 |
| REFERENCE_PRODUCT | T06 |
| PK_PARAMETERS | T07 |
| BLOOD_SAMPLING | T10 |
| CV_EVIDENCE | T17 |
| SYNOPSIS_N | T03 (subject N rows) / STUDY_METADATA |
| SOURCES | literature section (not a fixed template table) |

Display numbers (`Таблица N`) are assigned at render time from final ordered dynamic tables — never hardcoded in ProtocolDraft text permanently.

# SPEC v2.0 — Платформа автоматизированного формирования протоколов клинических исследований биоэквивалентности

**Статус:** инженерное ТЗ для Cursor  
**Версия:** 2.0  
**Дата:** 2026-08-25  
**Язык интерфейса:** русский  
**Язык генерируемого протокола:** русский  
**Основной режим генерации:** детерминированный, без обязательного ИИ  
**Допустимый AI-режим:** локальный LLM через совместимый HTTP API (например, Ollama)  
**Главное правило:** AI не является источником истины и не должен быть обязательным для генерации протокола.

---

## 0. Назначение этого документа

Этот файл является **главным техническим SPEC-файлом проекта**. Его задача — дать Cursor достаточно подробное описание доменной модели, архитектуры, интерфейса, бизнес-правил, API, генерации DOCX, валидации и тестирования.

Исходной базой являются:

1. текущий шаблон протокола БЭ на 107 страниц;
2. 74 встроенных комментария к шаблону;
3. три рабочих диалога коллег, где описан практический процесс подготовки исследования.

Шаблон содержит разделы от общей информации и обоснования до дизайна, фармакокинетики, безопасности, статистики, качества, этики, данных, страхования, публикаций и приложений. В самом документе есть многочисленные повторения одних и тех же параметров, что требует единой модели данных, а не независимого редактирования каждого раздела.

**Критическое требование:** не переносить текст шаблона «как набор строк для find/replace». Реализовать модель:

```text
Structured Study
      ↓
Rules / Calculations
      ↓
Validation
      ↓
Protocol Sections
      ↓
DOCX
```

---

# 1. Что именно строим

## 1.1. Продукт

Web-платформа «AI-конструктор протокола БЭ».

Пользователь создает исследование, вводит/загружает исходные сведения, система:

- структурирует данные;
- помогает определить референт;
- фиксирует источники;
- рекомендует дизайн;
- формирует PK-план;
- формирует sampling plan;
- рассчитывает объём проб и крови;
- рассчитывает/сохраняет статистические расчеты;
- проверяет непротиворечивость;
- собирает протокол DOCX.

## 1.2. Что не является целью MVP

Не требуется сразу делать:

- полноценную автоматическую нормативную экспертизу;
- полностью автономный web-research;
- автономный выпуск регуляторно готового документа без экспертной проверки;
- генерацию всех возможных исследований;
- автоматическую работу с любыми произвольными Word-шаблонами.

---

# 2. Основные принципы

## 2.1. Single Source of Truth

Каждый параметр хранится в одном месте.

Например:

```json
{
  "washout_days": 14
}
```

Этот параметр используется:

- в синопсисе;
- в разделе обоснования;
- в разделе дизайна;
- в разделе лечения;
- в расписании;
- в приложениях.

Нельзя хранить разные независимые копии одного значения.

## 2.2. Deterministic Core

Основная логика должна работать без LLM.

Без AI пользователь должен иметь возможность:

1. создать исследование;
2. заполнить данные;
3. рассчитать параметры;
4. пройти validation;
5. получить DOCX.

## 2.3. AI только как assistive layer

AI можно использовать для:

- извлечения данных из PDF/DOCX;
- классификации источников;
- извлечения параметров из публикаций;
- поиска потенциальных конфликтов;
- подготовки черновиков;
- объяснения найденной информации.

AI не должен напрямую менять подтвержденные поля.

## 2.4. Provenance

Каждое важное значение должно иметь:

- source;
- source type;
- page/section при наличии;
- extraction method;
- confidence;
- status;
- verified_by;
- verified_at.

## 2.5. Explicit uncertainty

Статусы:

```text
MISSING
PROPOSED
NEEDS_REVIEW
VERIFIED
REJECTED
CALCULATED
DERIVED
```

Нельзя молча подставлять неизвестное значение.

---

# 3. Роли

## USER

Создание и редактирование проектов.

## EXPERT

Подтверждение критических решений:

- референт;
- дизайн;
- питание;
- аналиты;
- sampling;
- CV;
- выборка;
- нормативные исключения.

## ADMIN

Управление:

- пользователями;
- шаблонами;
- правилами;
- справочниками;
- версиями генераторов.

---

# 4. Основной workflow

```text
CREATE PROJECT
   ↓
GENERAL
   ↓
TEST PRODUCT
   ↓
REFERENCE PRODUCT
   ↓
SOURCE DOCUMENTS
   ↓
REGULATORY ASSESSMENT
   ↓
DESIGN
   ↓
FOOD CONDITION
   ↓
ANALYTES
   ↓
PK PARAMETERS
   ↓
SAMPLING PLAN
   ↓
BIOANALYTICS
   ↓
SUBJECTS
   ↓
STATISTICS / CV
   ↓
PROCEDURE SCHEDULE
   ↓
VALIDATION
   ↓
PROTOCOL PREVIEW
   ↓
DOCX GENERATION
   ↓
VERSION SNAPSHOT
```

---

# 5. Структура интерфейса

## 5.1. Левое меню проекта

```text
01. Общая информация
02. Организации
03. Исследуемый препарат
04. Референтный препарат
05. Источники
06. Regulatory Assessment
07. Дизайн
08. Добровольцы
09. Критерии отбора
10. Аналиты
11. PK
12. Sampling
13. Bioanalysis
14. Процедуры
15. Безопасность
16. Статистика
17. Проверка
18. Предпросмотр
19. Генерация
20. История версий
```

## 5.2. Dashboard

Показывать:

- progress;
- critical errors;
- errors;
- warnings;
- pending expert decisions;
- missing source data;
- last generated version.

---

# 6. Domain Model

Минимальный набор сущностей:

```text
User
Project
ProjectVersion
Person
Organization
Study
Product
ProductRegistration
ProductComposition
SourceDocument
SourceEvidence
RegulatoryAssessment
Design
Period
Sequence
SubjectPlan
EligibilityCriterion
Analyte
PKParameter
SamplingPlan
SamplingPoint
BioanalysisPlan
Procedure
ProcedureSchedule
LaboratoryTest
SafetyPlan
CVStudy
CVPool
SampleSizeCalculation
ValidationIssue
ProtocolSection
TextBlock
ProtocolTemplate
GeneratedDocument
AuditLog
Rule
RuleVersion
```

---

# 7. Study JSON model

Основной агрегат:

```json
{
  "study": {
    "id": "uuid",
    "protocol_number": null,
    "version": "1.0",
    "version_date": null,
    "title": null,
    "short_title": null,
    "country": null,
    "phase": "bioequivalence",
    "status": "draft"
  },
  "sponsor": {},
  "organizations": {},
  "test_product": {},
  "reference_product": {},
  "regulatory_assessment": {},
  "design": {},
  "subjects": {},
  "eligibility": {},
  "analytes": [],
  "pk": {},
  "sampling": {},
  "bioanalysis": {},
  "procedures": {},
  "safety": {},
  "statistics": {},
  "sources": [],
  "protocol_settings": {}
}
```

Полную машинно-читаемую JSON-схему хранить отдельно в `BE_Protocol_Study_Schema_v1.json`.

---

# 8. Test Product

Поля:

- trade_name;
- inn;
- manufacturer;
- manufacturer_country;
- registration_holder;
- registration_number;
- dosage;
- dosage_form;
- route;
- pharmacological_group;
- composition;
- active_substance;
- excipients;
- coating;
- storage_conditions;
- shelf_life;
- batch_number;
- manufacture_date;
- expiry_date;
- packaging;
- labeling;
- status.

Источники:

- label/OХЛП;
- registration document;
- specification;
- CoA;
- sponsor-provided data.

---

# 9. Reference Product

Поля:

- trade_name;
- inn;
- manufacturer;
- country;
- registration_holder;
- registration_number;
- dosage;
- dosage_form;
- route;
- composition;
- storage;
- shelf_life;
- registration_status;
- source_evidence;
- purchased_status;
- batch_number;
- package;
- label.

`purchased_status`:

```text
NOT_PURCHASED
PURCHASED
UNKNOWN
```

При `NOT_PURCHASED` система должна учитывать соответствующий комментарий шаблона: некоторые детали референтного препарата не следует финализировать как фактически закупленные, если закупки еще нет.

---

# 10. Regulatory Assessment

Внутренний workflow:

```text
1. Identify candidate reference
2. Check completed BE studies
3. Check registration status
4. Check national EAEU registries if necessary
5. Check reference-product list if accessible
6. Search official label
7. Search product-specific BE guideline
8. Record evidence
9. Expert verification
```

Рабочие диалоги указывают на ГРЛС клинических исследований как один из практических способов увидеть ранее проведенные исследования и препарат сравнения.

Это использовать как **экспертный workflow**, а не как универсальное нормативное правило.

---

# 11. Product-specific guideline

В первую очередь искать официальный guide/draft для:

```text
INN + dosage form + route
```

Подходящий документ должен быть привязан к конкретной молекуле и соответствовать лекарственной форме и пути введения.

Из найденного документа извлекать, когда возможно:

- design;
- fasting/fed;
- analytes;
- sampling recommendations;
- biowaiver;
- PK requirements;
- special conditions.

Результат:

```json
{
  "found": true,
  "source_id": "uuid",
  "matched_formulation": true,
  "matched_route": true,
  "confidence": 0.95
}
```

---

# 12. Design Engine

Поддерживаемые режимы:

```text
CROSSOVER_2X2
REPLICATE_2X2X4
PARALLEL
ADAPTIVE
```

Архитектура должна позволять позже добавлять:

```text
CUSTOM
```

без изменения core.

---

# 13. Design entity

```json
{
  "type": "CROSSOVER_2X2",
  "periods": 2,
  "sequences": [
    ["T","R"],
    ["R","T"]
  ],
  "randomization": true,
  "blinding": false
}
```

Не хранить дизайн только как строку.

---

# 14. Design recommendation

Система может предложить дизайн, используя:

- product-specific guideline;
- референт;
- лекарственную форму;
- half-life;
- вариабельность;
- опубликованные исследования;
- экспертные настройки.

Результат должен быть:

```text
RECOMMENDED
RATIONALE
EVIDENCE
CONFIDENCE
```

Пользователь должен подтвердить рекомендацию.

---

# 15. Food Condition Engine

Значения:

```text
FASTING
FED
FASTING_AND_FED
UNKNOWN
```

Источники:

1. product-specific guideline;
2. официальная информация референта;
3. регуляторные требования;
4. экспертное решение.

Если инструкция указывает характер пищи или конкретное время относительно еды, эти параметры должны сохраняться отдельно, а не только как текст.

---

# 16. Food Model

```json
{
  "condition": "FED",
  "meal_type": "HIGH_CALORIE",
  "calories": null,
  "fat_percent": null,
  "composition": [],
  "meal_start_offset_min": null,
  "dose_after_meal_min": null,
  "water_volume_ml": 200
}
```

Справочник стандартных вариантов:

```text
HIGH_CALORIE
STANDARD
LOW_CALORIE
CUSTOM
```

В шаблоне есть комментарий о необходимости трех стандартных завтраков: высококалорийного, обычного и низкокалорийного.

---

# 17. Subjects

Хранить отдельно:

```text
target_evaluable_n
planned_randomized_n
reserve_n
planned_screened_n
```

Не смешивать эти величины.

Комментарий шаблона также отмечает, что использование «дублеров» в современных протоколах встречается редко; это должно быть конфигурационным полем, а не безусловной частью текста.

---

# 18. Eligibility

Три коллекции:

```text
inclusion[]
non_inclusion[]
exclusion[]
```

Каждый объект:

```json
{
  "id": "uuid",
  "number": 1,
  "text": "...",
  "source_ids": [],
  "status": "VERIFIED"
}
```

Один набор критериев должен использоваться:

- в synopsis;
- в разделе 5;
- в процедурах;
- в других необходимых местах.

Не создавать независимые копии.

---

# 19. Analyte model

```json
{
  "id": "uuid",
  "name": "...",
  "type": "PARENT",
  "active": true,
  "matrix": "plasma",
  "assay_method": null,
  "lloq": null,
  "uloq": null,
  "tmax_min": null,
  "tmax_max": null,
  "half_life_min": null,
  "half_life_max": null,
  "pk_parameters": [],
  "sources": []
}
```

Количество аналитів не ограничивать одним.

---

# 20. Analyte selection

Предлагать аналиты на основе:

- guideline;
- label;
- previous BE studies;
- parent/metabolite information;
- expert decision.

Если аналит выбран вручную, сохранять:

```text
selection_method = EXPERT
```

---

# 21. PK Engine

Основные входы:

```text
Tmax
Tmax range
half-life
design
food condition
analytes
```

Основные выходы:

```text
observation duration
washout
sampling plan
PK endpoints
```

---

# 22. PK parameters

Минимальный поддерживаемый набор:

```text
Cmax
Tmax
AUC0_t
AUC0_inf
Kel
T1_2
AUCextr
```

Дополнительные параметры допускаются.

В шаблоне эти параметры представлены как первичные и вторичные фармакокинетические параметры.

---

# 23. Observation Duration Engine

Формула/правило не должно быть захардкожено в UI.

Создать rule object:

```text
rule_id
parameter
formula
source
version
effective_from
```

Для текущего проекта шаблон и рабочие диалоги описывают практическую логику привязки наблюдения к t1/2, однако это необходимо в дальнейшем связать с верифицированным регуляторным источником перед Production.

---

# 24. Washout Engine

Input:

```text
half_life
design
selected_washout
```

Output:

```text
calculated_minimum
selected_value
rationale
status
```

Если selected_value меньше рассчитанного:

```text
CRITICAL_REVIEW
```

---

# 25. Sampling Engine

Главный принцип:

- baseline;
- ранняя абсорбционная часть;
- высокая плотность вокруг Tmax;
- пост-Tmax;
- терминальная часть;
- финальная точка.

В шаблоне содержится логика необходимости достаточного количества точек на восходящей и нисходящей части кривой и достаточного перекрытия для AUC. Рабочие диалоги также подчеркивают необходимость максимальной плотности вокруг ожидаемого Tmax.

---

# 26. SamplingPlan

```json
{
  "points": [
    {
      "time_h": 0,
      "window_min": 0,
      "reason": "BASELINE"
    }
  ],
  "total_points_per_period": 0,
  "final_observation_h": 0,
  "manual_override": false,
  "rationale": "",
  "status": "PROPOSED"
}
```

Каждая точка должна иметь reason:

```text
BASELINE
ABSORPTION
TMAX_CAPTURE
DISTRIBUTION
TERMINAL_PHASE
FINAL
```

---

# 27. Sampling recommendation algorithm

Алгоритм должен быть конфигурируемым и тестируемым.

Пример:

```text
Input:
Tmax = 2–3 h

Generate:
dense window around 1.5–3.5 h
moderate density before
lower density after
terminal points
```

Не фиксировать «18 точек» как закон.

Количество точек — результат алгоритма + экспертного решения.

---

# 28. Sampling validation

Проверять:

- минимум baseline;
- наличие точек до Tmax;
- достаточную плотность около Tmax;
- наличие post-Tmax;
- наличие терминальной части;
- соответствие final observation;
- отсутствие дубликатов;
- отсортированность;
- корректность временных окон.

---

# 29. Blood Volume Engine

Формулы:

```text
samples_total =
subjects_used_for_schedule
× periods
× points_per_period
```

Отдельно:

```text
pk_blood
screening_blood
final_visit_blood
flush_blood
other_blood
total_blood
```

Не объединять разные назначения в одну цифру без расшифровки.

---

# 30. Bioanalysis

Поля:

- matrix;
- tube;
- anticoagulant;
- blood volume;
- centrifugation;
- temperature;
- aliquots;
- storage;
- shipment;
- analytical method;
- method validation;
- acceptance criteria.

---

# 31. Procedure Schedule

Модель:

```text
Screening
Hospitalization
Period 1
Washout
Period 2
Final Examination
Follow-up
```

Для каждого этапа:

```text
procedure_id
time_relative_to_dose
mandatory
source
notes
```

---

# 32. Schedule of Assessments

Генерируется автоматически.

Минимальные строки:

- informed consent;
- anamnesis;
- demographics;
- physical examination;
- vital signs;
- ECG;
- lab tests;
- alcohol;
- drugs;
- cotinine;
- pregnancy;
- dosing;
- meals;
- PK blood sampling;
- AE monitoring;
- discharge;
- final examination.

---

# 33. Laboratory Dictionary

Поддержать:

```text
CBC
BIOCHEMISTRY
URINALYSIS
SEROLOGY
PREGNANCY
ALCOHOL
DRUG_SCREEN
COTININE
ECG
VITAL_SIGNS
OTHER
```

Каждая лабораторная группа должна быть редактируемым справочником.

---

# 34. Safety

Safety core должен быть преимущественно шаблонным.

Configurable:

- safety assessments;
- AE;
- SAE;
- severity;
- seriousness;
- causality;
- reporting;
- pregnancy follow-up.

---

# 35. Statistics

Основные параметры:

```text
AUC0_t
AUC0_inf
Cmax
```

Поля:

- analysis population;
- transformation;
- model;
- confidence interval;
- equivalence limits;
- alpha;
- power;
- missing values;
- outliers;
- safety analysis.

В шаблоне описан подход с лог-преобразованием основных PK-параметров, ANOVA и 90% CI для отношения T/R с пределами 80–125%; при реализации эти параметры должны быть конфигурируемыми и сопровождаться источником правила.

---

# 36. CV Study

```json
{
  "source_id": "...",
  "study_name": "...",
  "design": "...",
  "analyte": "...",
  "n_total": null,
  "n_be_analysis": null,
  "cv_cmax": null,
  "cv_auc": null,
  "condition": null
}
```

Критически важно различать `n_total` и `n_be_analysis`.

---

# 37. CV Pooling

Функция:

```text
pool_cv(studies, parameter)
```

Результат:

```text
pooled_cv
confidence_interval
method
input_studies
algorithm_version
```

Если данные недостаточны:

```text
status = NEEDS_REVIEW
```

---

# 38. Sample Size

Не реализовывать через «примерно N».

Расчет должен хранить:

```text
design
parameter
cv
expected_ratio
alpha
power
limits
formula/method
result
software_version
algorithm_version
```

---

# 39. Sample size workflow

```text
Collect CV
↓
Validate CV
↓
Optional pooling
↓
Select design
↓
Calculate evaluable N
↓
Apply reserve strategy
↓
Generate randomized N
↓
Generate screened N
↓
Expert review
```

---

# 40. Adaptive Design

Adaptive design — отдельный режим.

Хранить:

```text
stage_1_n
interim_analysis
decision_rule
stage_2_condition
max_n
```

Не активировать adaptive design автоматически только потому, что CV отсутствует. Система должна показать рекомендацию и потребовать экспертного решения.

---

# 41. Source Management

Source:

```json
{
  "id": "uuid",
  "type": "GUIDELINE",
  "title": "...",
  "authors": [],
  "year": null,
  "url": null,
  "file_id": null,
  "page": null,
  "section": null,
  "checksum": null,
  "verified": false
}
```

Source types:

```text
REGULATION
GUIDELINE
LABEL
REGISTRY
ARTICLE
STUDY_REPORT
PROTOCOL
BROCHURE
COA
OTHER
```

---

# 42. Document ingestion

Поддержать:

- PDF;
- DOCX;
- XLSX;
- TXT;
- изображения.

Pipeline:

```text
Upload
↓
Validation
↓
Extraction
↓
Table extraction
↓
Chunking
↓
Indexing
↓
Optional AI extraction
↓
Source evidence
```

---

# 43. Local AI

AI provider abstraction:

```text
AIProvider
 ├── DisabledProvider
 ├── LocalProvider
 └── ExternalProvider (future)
```

Для LocalProvider использовать совместимый REST API.

Настройки:

```text
AI_ENABLED
AI_BASE_URL
AI_MODEL
AI_TIMEOUT
AI_MAX_TOKENS
```

---

# 44. AI contract

LLM не должен возвращать свободный текст для критических параметров.

Формат:

```json
{
  "field": "tmax",
  "value": "2-3 h",
  "source_id": "uuid",
  "source_page": 47,
  "confidence": 0.94,
  "status": "PROPOSED"
}
```

---

# 45. AI tasks

Разрешенные:

```text
EXTRACT_PRODUCT_DATA
EXTRACT_PK_DATA
EXTRACT_FOOD_CONDITION
EXTRACT_ANALYTES
EXTRACT_CV
EXTRACT_STUDY_DESIGN
SUMMARIZE_CLINICAL_DATA
FIND_CONFLICTS
DRAFT_TEXT_BLOCK
```

Запрещено:

```text
AUTHORITATIVELY_DECIDE_REGULATORY_STATUS
AUTHORITATIVELY_CHOOSE_REFERENCE
AUTHORITATIVELY_CHANGE_VERIFIED_FIELD
```

---

# 46. Validation Engine

Категории:

```text
CRITICAL
ERROR
WARNING
INFO
```

Validation examples:

### Design

```text
2x2 design + periods != 2
```

→ ERROR

### Sampling

Нет baseline.

→ ERROR

Нет плотных точек вокруг Tmax.

→ WARNING/ERROR в зависимости от правила.

### Reference

Нет verified reference.

→ CRITICAL для final generation.

### Statistics

Нет CV для planned sample size.

→ ERROR.

### Document

Broken cross-reference.

→ CRITICAL.

---

# 47. Validation graph

Validation должна работать не только по полям, но и по зависимостям.

Пример:

```text
ReferenceProduct
      ↓
ReferenceLabel
      ↓
Tmax / half-life
      ↓
Sampling / washout
      ↓
Procedures
      ↓
Synopsis
```

Изменение верхнего узла должно запускать re-validation зависимых узлов.

---

# 48. Protocol Section Engine

Раздел:

```json
{
  "section_id": "4.4.2",
  "title": "Отбор крови для фармакокинетического анализа",
  "template_key": "sampling_plan",
  "dependencies": [
    "analytes",
    "sampling",
    "bioanalysis",
    "design"
  ]
}
```

Каждый раздел имеет:

- dependencies;
- generation function;
- conditions;
- source blocks;
- tables;
- references.

---

# 49. Фактическая карта разделов шаблона

Следующие разделы должны быть реализованы как минимум:

## Synopsis

Основные поля:

- название;
- протокол;
- тип;
- спонсор;
- ответственные лица;
- главный исследователь;
- клиническая организация;
- аналитическая лаборатория;
- цель;
- задачи;
- дизайн;
- популяция;
- N;
- препараты;
- dosing;
- washout;
- sampling;
- blood handling;
- eligibility;
- study periods;
- PK;
- statistics;
- safety;
- completion.

## 1. Общая информация

1.1 Protocol metadata  
1.2 Sponsor  
1.3 Authorized sponsor persons  
1.4 Medical expert  
1.5 Investigators and clinical centers  
1.6 Analytical laboratory  
1.7 Key organizations  
1.8 Signatures  
1.9 Investigator agreement

## 2. Обоснование

2.1 Products  
2.1.1 Test product  
2.1.2 Reference product  
2.2 Preclinical/clinical summary  
2.3 Risk-benefit  
2.4 Dose/rationale  
2.5 Study conditions  
2.6 Subjects  
2.7 Literature  
2.8 Pharmacological properties  
2.9 Test product details in actual body of template  
2.10 Reference justification  
2.11 Observation duration rationale  
2.12 Washout rationale

**Важно:** фактический текст основного документа отличается от оглавления: в теле присутствуют 2.9–2.12. Не пытаться слепо копировать только TOC.

## 3. Цель и задачи

Из structured Study.

## 4. Дизайн

4.1 PK parameters  
4.2 Design  
4.3 Randomization/blinding  
4.4 Treatment  
4.4.1 Stages  
4.4.2 Blood sampling  
4.5 Participation duration  
4.6 Stop/exclusion rules  
4.7 Drug accountability  
4.7.1 Test product  
4.7.2 Reference product  
4.7.3 Storage/accountability  
4.8 Randomization code  
4.8.1 Subject number  
4.8.2 Code storage/unblinding  
4.8.3 Blinding  
4.9 Direct primary data

## 5. Subjects

5.1 Inclusion  
5.2 Non-inclusion  
5.3 Exclusion

## 6. Treatment

6.1 Treatment  
6.1.1 Procedures  
6.1.2 Screening  
6.1.3 Randomization  
6.1.4 Period 1  
6.1.5 Washout  
6.1.6 Period 2  
6.1.7 Final examination  
6.1.8 Completion  
6.1.9 Blood sample preparation  
6.1.10 Concomitant/emergency therapy  
6.2 Allowed/prohibited treatments  
6.2.1 Food restrictions  
6.2.2 Physical activity  
6.2.3 Contraception  
6.3 Compliance  
6.3.1 Follow-up after withdrawal

## 7. Оцениваемые параметры

Фактическое тело шаблона содержит более подробную биоаналитическую структуру, чем TOC:

7.1 Parameters  
7.2 Methods/timing  
7.3 Analytical method  
7.3.1 Bioanalytical method  
7.3.2 Validation  
7.3.3 Sample analysis  
7.3.4 Analytical run acceptance/rejection

Это обязательно включить в mapping.

## 8. Безопасность

8.1 Safety parameters  
8.2 Methods/timing  
8.2.1 Physical exam  
8.2.2 Vital signs  
8.2.3 Laboratory/instrumental  
8.3 AE/SAE  
8.3.1 Medical events  
8.3.2 AE  
8.3.3 Severity  
8.3.4 Causality  
8.3.5 Seriousness  
8.3.6 AE registration  
8.3.7 SAE registration  
8.4 AE follow-up  
8.5 Pregnancy

## 9. Statistics

9.1 Methods  
9.2 Sample size  
9.3 Alpha  
9.4 Stopping  
9.5 Missing/unanalysable/falsified data  
9.6 Deviations from SAP/statistical plan  
9.7 Analysis populations  
9.7.1 Statistical analysis  
9.7.1.1 Descriptive statistics  
9.7.1.2 ANOVA  
9.7.2 BE criteria  
9.7.3 Outliers  
9.7.4 Safety analysis

## 10. Direct access / data

10.1 Completion  
10.2 Compliance  
10.3 Protocol deviations  
10.4 Data retention

## 11. Quality

## 12. Ethics

## 13. Data and records

## 14. Financing and insurance

## 15. Publications

## 16. Appendices

## 17. Итог

## 18. Literature

---

# 50. Template table inventory

Исходный DOCX содержит 33 таблицы.

Ключевые таблицы, которые должны стать динамическими:

1. Study metadata  
2. Abbreviations  
3. Synopsis  
4. Responsible persons  
5. Test product  
6. Reference product  
7. PK parameters  
8. Schedule of assessments  
9. Laboratory parameters  
10. Blood sampling  
11. Screening drug/alcohol/pregnancy tests  
12. Dosing/meal timing  
13. Vital sign deviations  
14. AE severity  
15. Causality  
16. Seriousness  
17. CV evidence  
18+ Appendices / AE / pregnancy / safety forms

Все таблицы должны иметь программный ID и источник данных.

---

# 51. Bookmark strategy

Встроенные комментарии шаблона неоднократно предлагают:

- сделать закладки;
- вставлять ссылки на ранее подготовленный текст;
- синхронизировать повторяющиеся таблицы;
- избежать ручной сверки.

В новой системе **не использовать Word bookmarks как основной источник истины**.

Источник истины:

```text
Study JSON
```

Word bookmarks / cross-references использовать только как механизм представления.

---

# 52. Word generation architecture

Pipeline:

```text
Study JSON
↓
Resolve Sections
↓
Generate Text Blocks
↓
Generate Dynamic Tables
↓
Resolve Cross References
↓
Apply Styles
↓
Update TOC
↓
Generate DOCX
↓
Run document validation
```

---

# 53. Template strategy

Не создавать шесть полностью независимых документов как основную архитектуру.

Использовать:

```text
Base Template
+
Design Modules
+
Food Modules
+
Formulation Modules
+
Conditional Blocks
```

Но предусмотреть возможность иметь отдельные template profiles:

```text
2x2_fasted
2x2_fed
2x2x4_fasted
2x2x4_fed
parallel_fasted
parallel_fed
```

Это следует из комментария исходного шаблона, где предлагается набор из шести вариантов.

---

# 54. Combined products

Архитектура должна поддерживать:

```text
Product[]
```

а не только один T.

Для комбинированного препарата:

```text
Product
  ├── ActiveIngredient A
  └── ActiveIngredient B
```

Для каждого active ingredient могут существовать:

- analytes;
- Tmax;
- t1/2;
- PK endpoints;
- sampling justification;
- bioanalytical method.

---

# 55. Document generation conditions

Examples:

```text
IF design == CROSSOVER_2X2
    include 2 periods
    include 2 sequences

IF design == REPLICATE_2X2X4
    include replicate-specific sequence and stats blocks

IF food == FED
    include meal table

IF food == FASTING
    include fasting restrictions

IF number_of_analytes > 1
    repeat analyte-dependent PK content

IF reference_purchased == false
    remove/qualify procurement-specific fields

IF adaptive
    include interim-analysis blocks
```

---

# 56. Audit trail

Каждое изменение критического поля:

```json
{
  "user_id": "...",
  "timestamp": "...",
  "entity": "study",
  "field": "washout_days",
  "old_value": 7,
  "new_value": 14,
  "reason": "...",
  "source_ids": []
}
```

---

# 57. Versioning

Каждый generated protocol должен быть воспроизводим.

Хранить:

- study snapshot;
- ruleset version;
- template version;
- generator version;
- AI provider/model если использовался;
- generation timestamp.

---

# 58. API

Минимум:

```text
POST   /api/projects
GET    /api/projects
GET    /api/projects/{id}
PATCH  /api/projects/{id}

POST   /api/projects/{id}/documents
GET    /api/projects/{id}/documents

POST   /api/projects/{id}/reference/assess
POST   /api/projects/{id}/design/recommend
POST   /api/projects/{id}/pk/calculate
POST   /api/projects/{id}/sampling/generate
POST   /api/projects/{id}/sampling/validate
POST   /api/projects/{id}/statistics/cv/pool
POST   /api/projects/{id}/statistics/sample-size
POST   /api/projects/{id}/validate
POST   /api/projects/{id}/generate-docx

GET    /api/projects/{id}/versions
POST   /api/projects/{id}/versions

GET    /api/rules
GET    /api/templates
GET    /api/reference-data
```

---

# 59. API error contract

Единый формат:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Sampling plan is inconsistent with Tmax range",
    "field": "sampling.points",
    "severity": "ERROR",
    "details": {}
  }
}
```

---

# 60. Database

PostgreSQL.

Обязательные UUID.

Foreign keys обязательны.

Critical fields должны иметь status/provenance.

---

# 61. Recommended backend

Python + FastAPI + Pydantic + SQLAlchemy.

Почему:

- удобен для научных расчетов;
- удобен для DOCX;
- удобен для PDF/document extraction;
- удобно подключать local AI;
- легко тестировать domain logic.

---

# 62. Recommended frontend

React + TypeScript.

Экранная архитектура должна быть schema-driven там, где возможно.

---

# 63. Background tasks

Использовать job queue для:

- document extraction;
- AI extraction;
- large document processing;
- DOCX generation;
- validation of large projects.

---

# 64. Search

MVP:

- PostgreSQL full-text.

Later:

- pgvector или Qdrant.

Semantic search нужен только для источников и документов.

Не использовать vector search как основной механизм расчета протокола.

---

# 65. Security

Обязательно:

- auth;
- RBAC;
- HTTPS;
- secure secret storage;
- file MIME validation;
- file-size limits;
- audit log;
- document access permissions.

Если включен внешний AI:

```text
external_ai_enabled = explicit_user_setting
```

---

# 66. Local AI privacy mode

В Local mode:

```text
documents
→ local extraction
→ local embedding
→ local retrieval
→ local model
```

Документы не покидают сервер.

---

# 67. Golden Test

Первый эталонный проект:

```text
Bosutinib 400 mg
```

В качестве reference source использовать данные из предоставленного шаблона.

Цель теста:

проверить, что система сможет:

- собрать данные;
- воспроизвести структуру;
- сформировать sampling;
- сформировать sample size section;
- сформировать statistics;
- создать DOCX;
- не создать broken references.

Не требовать пиксель-в-пиксель идентичности, если шаблон содержит ручные ошибки/неактуальные элементы; проверять семантическую эквивалентность.

---

# 68. Golden test assertions

Проверить минимум:

```text
Protocol metadata exists
Test product exists
Reference product exists
Design = 2x2
Periods = 2
Sequences = 2
Food condition = FED
Sampling points = expected set
Washout = expected configured value
Analytes = expected set
Primary PK parameters exist
Statistics section exists
Safety section exists
All tables numbered
No broken cross references
```

---

# 69. Unit tests

Обязательны для:

- design rules;
- food rules;
- eligibility;
- PK;
- sampling;
- washout;
- blood volume;
- CV;
- pooling;
- sample size;
- validation;
- conditional sections.

---

# 70. Integration tests

Минимум:

1. Create project → generate DOCX.
2. Change design → regenerate DOCX.
3. Change sampling → all dependent sections update.
4. Add analyte → analyte-dependent sections update.
5. Change subject numbers → synopsis/statistics update.
6. Enable/disable AI without breaking generation.

---

# 71. Regression tests

Каждое исправление бизнес-правила должно добавлять regression test.

---

# 72. Definition of Done

Feature считается завершенной только если:

- backend реализован;
- frontend реализован;
- tests существуют;
- tests проходят;
- documentation обновлена;
- audit trail работает;
- API documented;
- no regression.

---

# 73. Phase plan

## Phase 0 — Repository and architecture

Deliverables:

- repo;
- README;
- architecture;
- Docker Compose;
- local dev environment.

## Phase 1 — Domain core

- Study model;
- Product;
- Reference;
- Design;
- Eligibility;
- Source;
- database.

## Phase 2 — UI wizard

- dashboard;
- project wizard;
- forms;
- validation UI.

## Phase 3 — PK/Sampling

- analytes;
- Tmax;
- t1/2;
- washout;
- sampling;
- blood volume.

## Phase 4 — Statistics

- CV;
- CV studies;
- pooling;
- sample size.

## Phase 5 — Protocol Engine

- sections;
- blocks;
- tables;
- conditions.

## Phase 6 — DOCX

- template;
- placeholders;
- tables;
- references;
- TOC;
- final output.

## Phase 7 — Validation

- graph;
- rules;
- final quality report.

## Phase 8 — Document ingestion

- PDF;
- DOCX;
- XLSX.

## Phase 9 — Local AI

- provider;
- extraction;
- source evidence.

## Phase 10 — Advanced research

- regulatory research;
- literature extraction;
- advanced design support.

---

# 74. Cursor execution protocol

Cursor должен работать **только по одному Phase за раз**.

После завершения Phase:

1. run tests;
2. fix tests;
3. update docs;
4. show changed files;
5. show acceptance criteria;
6. STOP.

Не переходить к следующей Phase автоматически.

---

# 75. Coding rules for Cursor

1. Type hints mandatory.
2. Pydantic validation.
3. No business logic in React.
4. No database calls from UI components.
5. No hard-coded protocol text inside React.
6. No magic numbers in calculations.
7. Rules must have identifiers.
8. Calculations must be unit-tested.
9. Critical decisions must have provenance.
10. AI output must be schema-validated.
11. No silent fallback to invented values.
12. No breaking API changes without migration.
13. Use migrations for schema changes.
14. Log generation and validation events.
15. Keep core independent from AI.

---

# 76. Правила доменной логики vs экспертные рекомендации

Ниже два класса правил.

## HARD RULE

Источник верифицирован.

Может использоваться автоматически.

## EXPERT RECOMMENDATION

Получено из рабочего процесса специалистов или неоднозначной практики.

Система показывает:

```text
Recommendation
Source
Confidence
Need expert verification
```

Не превращать такую рекомендацию автоматически в hard rule.

Это особенно важно для:

- design;
- washout;
- sampling density;
- food condition exceptions;
- CV selection;
- adaptive design.

---

# 77. Что взять из комментариев исходного шаблона

Ключевые выводы 74 комментариев:

### Design variants

Нужно поддержать варианты:

- 2×2;
- 2×2×4;
- parallel;
- fasting/fed;
- combined products.

### Cross references

Использовать единый источник данных вместо ручной сверки.

### Reference

Учитывать статус закупки референта.

### Organizations

Для БЭ особенно важны контакты аналитической лаборатории; структура организаций должна быть конфигурируемой.

### Procedures

Процедуры должны синхронизироваться с соответствующими разделами.

### Analytes

Поддерживать несколько аналитів.

### Food

Иметь стандартные варианты завтраков и настраиваемый meal schedule.

### Documentation

Предусмотреть TMF/SMF/IMF storage fields.

### Structure

Не слепо воспроизводить неправильную структуру исходного Word-файла; при генерации использовать нормализованную модель.

---

# 78. Source-derived vs inferred

Все документы проекта должны различать:

```text
SOURCE_DERIVED
CALCULATED
EXPERT_ENTERED
AI_PROPOSED
RULE_DERIVED
```

Пример:

```text
tmax:
value = 2-3 h
origin = SOURCE_DERIVED

washout:
value = 14 days
origin = RULE_DERIVED

reference:
value = Bosulif
origin = EXPERT_VERIFIED

meal_type:
value = HIGH_CALORIE
origin = AI_PROPOSED
status = NEEDS_REVIEW
```

---

# 79. Финальный generated package

Для каждого проекта:

```text
/project-id/
  source-documents/
  study-snapshot.json
  validation-report.json
  audit-log.json
  protocol-v1.0.docx
  protocol-v1.0.pdf
```

---

# 80. Следующий этап после MVP

После успешного MVP можно добавить:

- regulatory research agent;
- literature search;
- automatic reference discovery;
- CV extraction;
- local vector DB;
- automatic evidence graph;
- Investigator's Brochure generator;
- SAP generator;
- schedule of assessments generator;
- final report generator.

---

# 81. Главное требование проекта

**Не создавать «чат, который пишет протокол».**

Создать:

> **систему управления структурированной моделью исследования, которая умеет автоматически генерировать протокол.**

AI является дополнительным помощником.

---

# 82. Первое сообщение Cursor

Использовать файл `CURSOR_BOOTSTRAP.md` из этого же пакета как первичную инструкцию.

Не начинать генерацию всего проекта одним действием.

Сначала:

```text
Read SPEC
Read Schema
Read source template
Read project structure
Produce architecture plan
STOP
```

После подтверждения:

```text
Implement Phase 0
Run tests
STOP
```

---

# 83. Первый реальный deliverable Cursor

Первым готовым результатом должен стать не протокол, а рабочий skeleton:

```text
Frontend
Backend
PostgreSQL
Docker
Project model
API
Basic dashboard
Tests
```

После этого начинать domain implementation.

---

# 84. Acceptance target для первой рабочей версии

Пользователь должен суметь:

```text
Создать исследование
↓
Ввести Бозутиниб
↓
Ввести Bosulif
↓
Выбрать 2×2
↓
Выбрать FED
↓
Указать Tmax/t1/2
↓
Получить sampling recommendation
↓
Указать N
↓
Пройти validation
↓
Нажать Generate
↓
Получить DOCX
```

---

# 85. Важное ограничение

Нельзя утверждать, что сгенерированный документ автоматически соответствует всем действующим нормативным требованиям без отдельной актуальной нормативной проверки.

Платформа должна формировать:

- structured draft;
- expert-reviewed protocol;
- traceable evidence.

---

# 86. Итоговая архитектура

```text
                       ┌─────────────────────┐
                       │      FRONTEND       │
                       │ React / TypeScript  │
                       └──────────┬──────────┘
                                  │
                                  ▼
                       ┌─────────────────────┐
                       │       API           │
                       │      FastAPI        │
                       └──────────┬──────────┘
                                  │
               ┌──────────────────┼──────────────────┐
               │                  │                  │
               ▼                  ▼                  ▼
       ┌──────────────┐   ┌───────────────┐  ┌───────────────┐
       │ Domain Core  │   │ Validation    │  │ AI Layer      │
       │ Rules/Calc   │   │ Engine        │  │ Local/External│
       └──────┬───────┘   └───────────────┘  └───────────────┘
              │
              ▼
       ┌──────────────┐
       │ Study Model  │
       └──────┬───────┘
              │
       ┌──────┴──────────┐
       ▼                 ▼
┌─────────────┐   ┌──────────────┐
│ PostgreSQL  │   │ Source Store │
└─────────────┘   └──────────────┘
              │
              ▼
       ┌──────────────┐
       │ Protocol     │
       │ Engine       │
       └──────┬───────┘
              ▼
       ┌──────────────┐
       │ DOCX Engine  │
       └──────┬───────┘
              ▼
        Protocol DOCX
```

---

# 87. Условия перехода к Production

До Production необходимо:

- финализировать правила;
- верифицировать нормативные источники;
- провести экспертную валидацию;
- расширить regression suite;
- проверить несколько реальных исследований;
- проверить DOCX;
- провести security review;
- определить политику хранения и удаления документов;
- определить резервное копирование.

---

# 88. Конечная архитектурная идея

```text
                USER
                  │
                  ▼
            PROJECT WIZARD
                  │
                  ▼
        STRUCTURED STUDY MODEL
                  │
      ┌───────────┼─────────────┐
      ▼           ▼             ▼
 Regulatory      PK          Statistics
 Engine          Engine       Engine
      │           │             │
      └───────────┼─────────────┘
                  ▼
             VALIDATION
                  │
                  ▼
          PROTOCOL BUILDER
                  │
                  ▼
            DOCX ENGINE
                  │
                  ▼
         FINAL PROTOCOL
```

Это и является целевой архитектурой проекта.


---

# Приложение A — фактическая структура исходного DOCX

Исходный DOCX содержит **1432 абзаца и 33 таблицы**. Ниже перечислены фактические заголовки основного тела документа, а не только TOC; это важно, поскольку структура тела местами отличается от оглавления.



---

# Приложение B — выводы из 74 комментариев исходного шаблона

Встроенные комментарии должны быть преобразованы в backlog/правила, а не копироваться в новый шаблон. Наиболее значимые группы:

## design_variants

- C0: Поменять если другой дизайн 
- C1: Для удобства, и повышения скорости подготовки документов в идеале сделать несколько готовых шаблонов под разные дизайны исследования (2х2, 2х2х4 и параллельный) и соответственно под условия приема пищи (натощак, после еды). Т.е. в сумме 6 документов. Но это позволит в разы ускорить работы по написанию протоколов, т.к. меньше времени придется уделять правкам одного исходного шаблона. И в идеале еще иметь отдельные шаблоны на комбинированные препараты. 
- C16: Поменять если другой дизайн 
- C17: Для удобства, и повышения скорости подготовки документов в идеале сделать несколько готовых шаблонов под разные дизайны исследования (2х2, 2х2х4 и параллельный) и соответственно под условия приема пищи (натощак, после еды). Т.е. в сумме 6 документов. Но это позволит в разы ускорить работы по написанию протоколов, т.к. меньше времени придется уделять правкам одного исходного шаблона. И в идеале еще иметь отдельные шаблоны на комбинированные препараты. 
- C61: Поменять если другой дизайн 
- C62: Для удобства, и повышения скорости подготовки документов в идеале сделать несколько готовых шаблонов под разные дизайны исследования (2х2, 2х2х4 и параллельный) и соответственно под условия приема пищи (натощак, после еды). Т.е. в сумме 6 документов. Но это позволит в разы ускорить работы по написанию протоколов, т.к. меньше времени придется уделять правкам одного исходного шаблона. И в идеале еще иметь отдельные шаблоны на комбинированные препараты. 
- C80: Поменять если другой дизайн 
- C81: Для удобства, и повышения скорости подготовки документов в идеале сделать несколько готовых шаблонов под разные дизайны исследования (2х2, 2х2х4 и параллельный) и соответственно под условия приема пищи (натощак, после еды). Т.е. в сумме 6 документов. Но это позволит в разы ускорить работы по написанию протоколов, т.к. меньше времени придется уделять правкам одного исходного шаблона. И в идеале еще иметь отдельные шаблоны на комбинированные препараты. 
- C103: На практике сейчас дублеров очень редко одобряют, поэтому возможно имеет смысл исключить из шаблона совсем упоминание дублеров 

## cross_references_bookmarks

- C22: Требования Пункта 6.1.7.  Решений Совета Евразийской экономической комиссии от 03.11.2016 N 79 или это информация содержится в отдельном соглашении или в других документах, ссылки на которые имеются в протоколе. 
- C24: Если сделать закладки на определенные места текста в синопсисе, в теле протокола можно будет автоматом вставлять целые куски готового текста, и обновлять автоматически при измени текста исходной закладки. Это позволяет значимо экономить на времени написания протокола. 
- C25: Можно сделать Закладку (см. Выше). 
- C26: Можно сделать Закладку 
- C34: Можно сделать Закладку 
- C37: Лучше прописать критерии включения, невключение и исключения в синопсисе, сделать закладки, а раздела 5.1-5.3 вставить ссылки на закладки. 
- C39: Можно сделать закладку 
- C40: Все представленные ниже процедуры сверить с разделом 7.3 
- C41: Чтобы не сверять, сделать закладки в синопсисе и ссылки в 6.1.4. 
- C42: Можно сделать закладку 
- C44: Можно сделать закладку 
- C45: Все представленные ниже процедуры сверить с разделом 6.1.6 

## reference_product

- C3: Удалить, если не закуплен рефрентный препарат на момент финального согласования протокола 
- C18: Удалить, если не закуплен рефрентный препарат на момент финального согласования протокола 
- C28: Также способ применения должен быть максимально приближенным к ОХЛП референта. 
- C63: Удалить, если не закуплен рефрентный препарат на момент финального согласования протокола 
- C82: Удалить, если не закуплен рефрентный препарат на момент финального согласования протокола 

## source_and_documentation

- C13: МИ 20240709: я бы добавила TMF, SMF, IMF, все равно в тексте надо указывать где хранятся/планируют храниться документы по исследованию 
- C23: Обычно указывают контакты аналитической лаборатории, а клиническую лабораторию не указывают в протоколах БЭ. 

## lab_and_procedures

- C22: Требования Пункта 6.1.7.  Решений Совета Евразийской экономической комиссии от 03.11.2016 N 79 или это информация содержится в отдельном соглашении или в других документах, ссылки на которые имеются в протоколе. 
- C40: Все представленные ниже процедуры сверить с разделом 7.3 
- C45: Все представленные ниже процедуры сверить с разделом 6.1.6 
- C47: Сверить с разделом 6.1.7 
- C48: Что бы не сверять сделать закладку и ссылку в 6.1.7 

## food

- C167: Необходимо подготовить 3 таблицы стандартного завтрака (высококалорийного, обычного, низкокалорийного). 
- C168: Примерные таблицы с высококалорийным и низкокалорийный завтраком могу предоставить при необходимости. 
- C169: По согласованию с клиническим центром принято решение не указывать объемы жидкости кроме той которой запивают препараты. 

## analytes

- C23: Обычно указывают контакты аналитической лаборатории, а клиническую лабораторию не указывают в протоколах БЭ. 
- C50: Добавить для каждого аналита 

## stats_sample_size

- C103: На практике сейчас дублеров очень редко одобряют, поэтому возможно имеет смысл исключить из шаблона совсем упоминание дублеров 

## structure_cleanup

- C78: В сокращения 
- C107: Этот и последующие подразделы не имеют отношения к фармакологическим свойства. Поэтому их лучше выделить в разделы 2.9, 2.10,и т.д. 
- C127: Сюда по смыслу нужно перенести 4.7.1 и 4.7.2, и продублировать информацию из синопсиса в отношении приема препаратов. 
- C129: Этот подраздел по смыслу не входит в 4.4. По смыслу это скорее 4.2. 
- C131: Этот подраздел по смыслу не входит в 4.4. По смыслу это скорее 4.2. 
- C283: Приложения должны быть самым последним разделом. Поэтому возможно следует раздел 17 объединить с разделом 15. А раздел 18 удалить. 


---

# Приложение C — обязательные артефакты репозитория

После Phase 0 в репозитории должны существовать минимум:

```text
README.md
ARCHITECTURE.md
docs/SPEC.md
docs/DOMAIN.md
docs/BUSINESS_RULES.md
docs/DOCX_MAPPING.md
docs/API.md
docs/TESTING.md
backend/
frontend/
tests/
templates/
docker-compose.yml
.env.example
```

---

# Приложение D — что Cursor не должен делать

- Не писать весь проект одним сообщением.
- Не использовать LLM как расчетный движок.
- Не хранить бизнес-логику в React.
- Не копировать один и тот же текст в десятках функций.
- Не использовать magic numbers в PK/statistics.
- Не считать практический совет коллеги нормативной нормой без источника.
- Не генерировать окончательный протокол при наличии critical validation issues.
- Не удалять audit trail.
- Не менять подтвержденные данные на основании AI-output без подтверждения пользователя.
- Не ломать существующую структуру API при добавлении новых модулей.

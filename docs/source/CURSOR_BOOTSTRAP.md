# CURSOR BOOTSTRAP — BE Protocol Platform

## 0. Перед началом

Прочитай:

- `BE_Protocol_Platform_SPEC_v2.0.md`
- `BE_Protocol_Study_Schema_v1.json`
- исходный DOCX-шаблон протокола БЭ
- три рабочих диалога коллег

Не начинай реализацию всего приложения сразу.

## 1. Главная архитектурная установка

Мы строим не чат для написания протокола и не систему find/replace для Word.

Основная архитектура:

```text
Structured Study
→ Domain Rules
→ Calculations
→ Validation
→ Protocol Sections
→ DOCX
```

AI является опциональным assistive layer.

Если AI выключен, приложение должно продолжать работать.

## 2. Обязательные правила разработки

- Domain logic не помещать в React.
- Не использовать magic numbers.
- Все расчеты покрыть тестами.
- Все критические поля должны иметь provenance/status.
- AI output валидировать схемой.
- AI не может напрямую перезаписывать VERIFIED данные.
- Не придумывать отсутствующие данные.
- Не превращать фразы из рабочего диалога специалистов в нормативные правила без verified source.
- Не делать жесткий текст протокола внутри UI.
- Использовать versioned rules.
- Использовать migrations.
- Все critical validation issues блокируют финальную генерацию.

## 3. Порядок выполнения

### Phase 0
Создай:

- repo structure;
- backend skeleton;
- frontend skeleton;
- PostgreSQL;
- Docker Compose;
- migrations;
- test framework;
- basic README.

### После Phase 0
Запусти tests и покажи:

- созданные файлы;
- команды запуска;
- результаты tests;
- проблемы.

**STOP.**

Не переходи дальше.

### Phase 1
После отдельного подтверждения:

- Study;
- Sponsor;
- Organization;
- Product;
- ReferenceProduct;
- Source;
- basic project API;
- basic dashboard.

**STOP.**

### Phase 2

- Design Engine;
- Eligibility;
- Food;
- Subjects.

**STOP.**

### Phase 3

- Analytes;
- PK;
- Sampling;
- Washout;
- Blood Volume.

**STOP.**

### Phase 4

- CV studies;
- pooling;
- sample size;
- statistics.

**STOP.**

### Phase 5

- Validation Engine.

**STOP.**

### Phase 6

- Protocol Section Engine;
- TextBlocks;
- dynamic tables.

**STOP.**

### Phase 7

- DOCX Engine;
- original template mapping;
- bookmarks/cross references;
- TOC;
- output QA.

**STOP.**

### Phase 8

- document ingestion;
- PDF/DOCX extraction.

**STOP.**

### Phase 9

- Local AI provider;
- structured extraction;
- evidence proposals.

**STOP.**

## 4. Первый acceptance test

После Phase 7 использовать test study based on:

- Bosutinib 400 mg
- reference Bosulif
- 2×2 crossover
- fed condition

и проверить:

- project creation;
- data storage;
- design;
- PK;
- sampling;
- blood volume;
- validation;
- DOCX generation;
- no broken references.

## 5. Не делай

Не:

- писать весь проект одним запросом;
- заменять LLM математическим движком;
- заставлять пользователя вручную дублировать значения;
- создавать отдельную копию одного и того же параметра для каждого раздела протокола;
- считать старые практические решения нормативными автоматически.

## 6. Формат отчета после каждого Phase

```text
PHASE:
STATUS:
FILES CREATED:
FILES CHANGED:
TESTS:
TEST RESULT:
KNOWN LIMITATIONS:
NEXT PHASE:
```

Затем остановись.

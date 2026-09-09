# Business Rules

Правила versioned (`Rule` / `RuleVersion`). Источник нормы должен быть verified.

## Статусы происхождения правил

| Класс | Смысл |
|-------|--------|
| VERIFIED_REGULATORY | подтверждённый нормативный источник |
| PRODUCT_SPECIFIC_GUIDELINE | guide по молекуле/форме |
| EXPERT_VERIFIED | экспертное решение с audit |
| PRACTICAL_WORKFLOW | практика из рабочих диалогов — **не норма** без verified source |
| TEMPLATE_COMMENT | комментарий шаблона — требует review |

## Инварианты MVP

1. Single source of truth для каждого параметра (например `washout_days`).
2. Critical validation issues блокируют Generate.
3. Нет magic numbers в PK/statistics — константы в `domain/constants` + `/api/reference-data/*`.
4. Практические советы коллег не становятся нормами автоматически.
5. При `NOT_PURCHASED` детали референта не финализировать как фактически закупленные.

## Phase 7 — Local AI (assistive only)

- AI никогда не является источником истины и не пишет VERIFIED Study напрямую.
- AI claims только `PROPOSED` / `AI_PROPOSED` с обязательным source grounding.
- Confidence ≠ verification.
- AI не утверждает reference / design / sample size / CV / washout / sampling и не заменяет Validation Engine.
- Study updates только через expert Verify → `apply_verified_evidence()`.

## Phase 8 — Protocol Assembly

- ProtocolDraft собирается детерминированно из Study snapshot.
- Critical validation issues → `BLOCKED` (не READY).
- Запрещены выдуманные плейсхолдеры `ХХ` / `XXX` / «примерно»; только явные `{{FIELD}}`.
- Нумерация таблиц динамическая по `table_key`.
- DOCX не генерируется в Phase 8.

## Phase 9 — DOCX Rendering

- Renderer не содержит business logic исследования.
- Исходный template immutable (checksum).
- FINAL блокируется при missing sponsor / protocol_number / critical `{{...}}`.
- Не подставлять N/A вместо missing values.
- Версии generated DOCX не перезаписываются.

## Phase 2 structural rules

| Design | Constraint |
|--------|------------|
| CROSSOVER_2X2 | periods=2, sequences=2 |
| PARALLEL | periods=1, treatment groups≥2 |
| REPLICATE_2X2X4 | periods≥3, sequences valid vs periods |
| ADAPTIVE | stage_1 + interim_analysis required |
| CUSTOM | extensibility placeholder |

Subject plan: missing N is `null`, never coerced to 0.
`planned_randomized_n >= target_evaluable_n`
`planned_screened_n >= planned_randomized_n`

## Sampling / Tmax capture (shared domain)

- Canonical capture window: `TmaxCaptureWindow` (`backend/app/domain/tmax_capture_window.py`).
- **Sampling Engine** and **Validation Engine** must use the same `compute_tmax_capture_window(...)` for a given `tmax_min`/`tmax_max` and sampling density rule.
- Default rule: `PK.SAMP.DENSITY.v1` — status **PROPOSED** (margin fractions are workflow parameters, **not** verified regulatory norms).
- Forbidden: Validation-only hardcoded check against literal `[tmax_min, tmax_max]` while Sampling densifies an expanded window.

## Phase 11A — Canonical consistency

- `SubjectPlan` is the only protocol source for evaluable / randomized / screened / reserve N.
- `SampleSizeCalculation` stores CALCULATED results; on calculate, values are synced into `SubjectPlan` (accepted counts). Divergence → ERROR.
- `SamplingPlan.points` is the only source of sampling times; consumers use `get_canonical_sampling_plan()`.
- Human-readable enums only via `DisplayValueRegistry` — raw codes (`CROSSOVER_2X2`, `FED`, …) forbidden in DOCX.
- Product table cells filled by label mapping (`product_mapping`), never blind row index.
- Registries: Table / Reference / Placeholder / Static blocks; `validate_canonical_consistency` + `DocumentConsistencyReport`.

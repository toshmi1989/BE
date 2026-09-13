# Phase 29 — Пробелы данных, поиск в открытых источниках, 5-шаговый пайплайн

Отчёт-передача для продолжения разработки. Состояние на 13.09.2026.
Предыдущие отчёты по UX писателя: `PHASE26_WRITER_UX_REPORT.md`, `PHASE27_WRITER_WORKFLOW_REPORT.md`,
`PHASE28_WORKSPACE_INTEGRITY_REPORT.md`.

## 1. Задача, из которой выросла фаза

Продукт — **генератор протокола БЭ**: писатель загружает вводные документы, из них извлекаются данные,
а то, чего в документах нет, ищется в открытых источниках с помощью ИИ и подтверждается экспертом.

Что было не так до фазы 29:

- «Run preflight» выдавал экран «Actionable blockers» с сырыми кодами
  (`MISSING_CVINTRA_CMAX`, `Sample size approved`), непонятными писателю;
- кнопка «Открыть Решения» вела на вкладку Statistics, которая снова отправляла в «Решения» —
  навигационный тупик, потому что карточки STATISTICS-решения не существовало;
- 8 вкладок без порядка прохождения: было неясно, что делать первым;
- часть блокеров дублировала друг друга или сообщала норму, а не проблему;
- отсутствие одного значения (например Tmax) выглядело как блокировка всего протокола.

## 2. Что сделано

### 2.1. Единая поверхность пробелов (ядро фазы)

`backend/app/domain/workspace_gaps.py` — один каталог пробелов. Пробел = входные данные, которых
не дали документы. У каждого пробела есть заголовок, объяснение «зачем нужно», список шагов, которые
без него не считаются, и **ровно один способ закрытия**.

| Код | Пробел | Блокирует | Как закрывается |
|---|---|---|---|
| `MISSING_TMAX_FOR_SAMPLING` | Ожидаемый Tmax | Sampling | RESEARCH, MANUAL |
| `MISSING_HALF_LIFE_FOR_WASHOUT` | Период полувыведения t½ | Washout, Sampling | RESEARCH, MANUAL |
| `MISSING_CVINTRA` | Внутрииндивидуальная вариабельность | Sample Size, Statistics | RESEARCH, MANUAL |
| `MISSING_MEAL_COMPOSITION` | Состав стандартного приёма пищи | Food | RESEARCH, MANUAL |
| `MISSING_ANALYTE` | Определяемый аналит | Analyte / PK | MANUAL, RESEARCH |
| `MISSING_PRIMARY_BE_SELECTION` | Основной endpoint БЭ | Statistics, Sample Size | EXPERT_DECISION |
| `MISSING_ANALYSIS_POPULATION_RULE` | Популяция анализа | Statistics | EXPERT_DECISION |

Маршруты закрытия: `RESEARCH` (поиск + верификация эксперта), `MANUAL` (эксперт вводит значение
с обоснованием, пишется как VERIFIED MANUAL ResearchClaim), `EXPERT_DECISION` (выбор внутри движка,
делается в шаге «Решения»).

Сырые коды движков сводятся к каноническим через `CANONICAL_ALIASES`
(`MISSING_VERIFIED_CVINTRA`, `MISSING_CVINTRA_CMAX`, `CV_PROPOSED_NOT_ALLOWED`, `CV_NOT_USABLE` → `MISSING_CVINTRA`;
`MISSING_PRIMARY_PK_PARAMETER`, `REQUIRES_EXPERT_SELECTION` → `MISSING_PRIMARY_BE_SELECTION`).
Общие маркеры (`REQUIRES_EXPERT_DECISION`, `AI_CANNOT_APPROVE`, `AI_CANNOT_SELECT_METHOD`) отбрасываются
как не несущие информации — `IGNORED_ENGINE_CODES`.

Ключевые инварианты:

- **Soft-gate**: `protocol_frozen: False`, `scope: "STEP"` — пробел гасит только зависимые шаги;
- пробелы движков появляются только после анализа пакета (`analysed`), иначе пустое исследование
  показывало ложный «нет CVintra»;
- `study_mutated: False` — сбор пробелов ничего не меняет в исследовании.

### 2.2. Плановый и наблюдаемый Tmax

Разделены: плановый (`pk.expected_tmax`) идёт в дизайн отбора проб, наблюдаемый (результат исследования) —
нет. Мост `research_decision_bridge.py` применяет оба имени поля (`pk.expected_tmax` + `pk.Tmax`,
`pk.expected_t_half` + `pk.t_half`), чтобы движки и legacy-путь видели одно и то же значение.

### 2.3. Поиск в открытых источниках: выбор провайдера на сервере

Ранее фронтенд сам решал, чем искать, и при включённом ИИ просил `use_mock_provider: false`, что
в бэкенде означало `NullResearchProvider` — провайдер, возвращающий пустой список. Запрос завершался
успешно, результатов не было, кнопка выглядела мёртвой.

Теперь провайдер выбирается в `_search_provider()` (`backend/app/api/study_workspace.py`):

- по умолчанию — `RealWebResearchProvider` (реальный поиск, DuckDuckGo HTML, без API-ключа);
- `MOCK` — только по явному запросу (кнопка «Показать демо-набор», появляется после безуспешного поиска);
- если `research_web_enabled=false` — статус `SEARCH_UNAVAILABLE` с текстом, а не тишина.

Кнопка всегда возвращает определённый исход: `OK`, `SOURCES_ONLY`, `NOTHING_FOUND`, `SEARCH_FAILED`,
`SEARCH_UNAVAILABLE`.

### 2.4. Глубокое чтение источников (`research_deep_read.py`)

Сниппет выдачи почти никогда не содержит PK-число: оно внутри PDF или статьи. Если из сниппетов
значение не извлеклось, платформа **открывает сами документы**:

1. источники сортируются по `priority_class` (официальные раньше публикаций);
2. `research_fetch.fetch_and_snapshot` качает HTML или PDF (PDF идёт через ingest фазы 14.1);
3. `relevant_passages()` вырезает фрагменты, где название параметра стоит рядом с числом;
   упоминание без числа отбрасывается — это и защищает от выдумывания значений;
4. по каждому фрагменту работает та же детерминированная экстракция `extract_claims_from_hit`;
5. недоступные документы (403, paywall) перечисляются, а не заминаются.

Дополнительная проверка применимости: если документ ни разу не упоминает активное вещество,
claim получает `applicability = "LOW"` и текст причины
(«Документ не упоминает «X» — значение может относиться к другому препарату»).
Реальный случай на живом прогоне: `intra-subject CV 7%` пришёл из обзора NDA другого препарата.

### 2.5. Извлечение вариабельности

`research_extract.py`:

- синонимы within-subject (`within/intra-subject`, `intra-individual`, `CVw`, `CVintra`,
  «внутрииндивидуальная») и between-subject (`between/inter-subject`, `inter-individual`, `CVb`);
- если в одной фразе названы оба типа — `UNKNOWN`, а не догадка;
- значение и его квалификатор читаются из **одной фразы** (`_clause_at`), включая левый контекст:
  «the **between-subject** variability (CV %) … was 20% to 35%»;
- из абзаца с несколькими процентами выбирается тот, чья фраза упоминает Cmax/AUC
  (иначе брался CV клиренса);
- диапазон остаётся диапазоном: «20% to 35%» и «(i.e., 5-7%)» → `CV_range_low/high`,
  `CV_value = None`. Точечного значения нет → в расчёт размера выборки не проходит,
  эксперт выбирает сам;
- строки оглавления (`.....`, «page N», «see section») отбрасываются;
- выдержка claim'а — та фраза, где стоит число, а не начало страницы (важно для верификации);
- PDF-текст читается как сплошной: переносы строк больше не разрывают связку «параметр → число».

Модель `CVintraEvidence` получила поля `CV_range_low` / `CV_range_high`.

### 2.6. Between-subject никогда не выдаётся за CVintra

`_claim_matches` для `cv_intra` требует `variability_type == "WITHIN_SUBJECT"`. Найденная
межиндивидуальная вариабельность попадает в отдельный список `related_findings` с объяснением,
почему она не подходит, и её нельзя «Подтвердить» как CVintra.

Практический вывод по домену: по упадацитинибу открытые источники дают именно between-subject
CV 20–35% (FDA-обзор), поэтому CVintra для такого препарата закрывается данными предыдущих
БЭ-исследований или экспертным вводом, а не литературой.

### 2.7. Человекочитаемые блокеры

`workspace_progress.py`:

- `PREFLIGHT_ALREADY_REPORTED` — коды, которые сообщали норму (`SAMPLE_SIZE_APPROVED`,
  `PRIMARY_BE_APPROVED`, `HAS_DOCUMENTS`, `HAS_CANDIDATES`), больше не показываются как блокеры;
- `REASON_COPY_RU` + `_humanize_reasons()` — вместо `MISSING_VERIFIED_CVINTRA` фраза
  «нет подтверждённой внутрииндивидуальной вариабельности (CVintra)»;
- блокеры из пробелов ведут на нужный шаг: `tab: "gaps"` для значений,
  `tab: "decisions"` для экспертных решений; у всех `soft_gate: True`, `scope: "STEP"`.

## 3. API

Все ручки — под префиксом `/api`, файл `backend/app/api/study_workspace.py`.

### 3.1. Пробелы (новое в фазе 29)

| Метод | Путь | Права | Назначение |
|---|---|---|---|
| GET | `/api/studies/{study_id}/gaps` | `view` | Панель пробелов: `gaps`, `resolved`, `counts`, `protocol_frozen: false` |
| POST | `/api/studies/{study_id}/gaps/{code}/research` | `view` | Поиск значения в открытых источниках + глубокое чтение документов |
| POST | `/api/studies/{study_id}/gaps/{code}/verify` | `approve_decisions` | Эксперт подтверждает предложение → пересчёт зависимых доменов |
| POST | `/api/studies/{study_id}/gaps/{code}/resolve-manual` | `approve_decisions` | Эксперт вводит значение с обоснованием (MANUAL, VERIFIED) |

**POST `/gaps/{code}/research`**

Запрос: `active_substance`, `dosage_form`, `dose`, `use_mock_provider` (не задавать в обычном режиме),
`package_id`.

Ответ:

```json
{
  "code": "MISSING_CVINTRA",
  "research_task_id": "RT-…",
  "provider": "WEB",
  "status": "OK | SOURCES_ONLY | NOTHING_FOUND | SEARCH_FAILED | SEARCH_UNAVAILABLE",
  "found": 1,
  "awaiting_verification": 1,
  "sources": [{ "title": "…", "url": "…", "source_type": "REGULATORY" }],
  "documents_read": [{ "title": "…", "url": "…", "passages": 2 }],
  "documents_unavailable": [{ "title": "…", "url": "…", "error": "ACCESS_DENIED" }],
  "message": "текст для писателя на русском",
  "gap": { "…": "срез панели по этому пробелу" },
  "auto_verified": false,
  "study_mutated": false
}
```

Аудит: `GAP_RESEARCH_RUN`, `GAP_VALUE_VERIFIED`, `GAP_RESOLVED_BY_EXPERT`.

Структура пробела в панели: `code`, `title`, `why`, `note`, `blocks`, `blocked_by_this`,
`requested_by`, `field_path`, `unit`, `numeric`, `requires_pk_parameter`, `pk_parameter_options`,
`resolution`, `sources_hint`, `status` (`OPEN|PROPOSED|VERIFIED`), `proposals`,
`related_findings`, `research_task_id`, `needs_apply`, `severity`, `scope`.

Предложение (`proposals[]`): `claim_id`, `value`, `unit`, `excerpt`, `location`,
`applicability_reason`, `confidence`, `verification_status`, `applicability`, `usable`,
`extraction_method`, `pk_parameter`.

### 3.2. Остальные ручки воркспейса (без изменений в этой фазе)

Каталог и жизненный цикл: `GET /api/studies`, `POST /api/studies/create`,
`POST /api/studies/{id}/workflow/run`, `GET /api/workflows/{id}`,
`POST /api/studies/{id}/workspace/hydrate`.

Обзор и готовность: `GET /api/studies/{id}/workspace`, `/readiness`, `/conflicts`, `/preflight`,
`/writer-progress`, `/audit`, `/snapshots` (GET/POST).

Документы: `POST /api/studies/{id}/documents/upload`, `GET /api/studies/{id}/documents`,
`POST /api/studies/{id}/documents/{document_id}/classify`.

Данные и решения: `GET /api/studies/{id}/canonical-facts/{field_path}/detail`,
`POST /api/studies/{id}/canonical-facts/review`, `POST /api/studies/{id}/decisions/expert`,
`POST /api/studies/{id}/decisions/request-evidence`.

Протокол: `GET /api/studies/{id}/protocol/preview`, `POST /api/studies/{id}/protocol/generate-docx`,
`GET /api/studies/{id}/protocol/artifacts`, `…/artifacts/{artifact_id}`,
`…/artifacts/{artifact_id}/download`, `GET /api/studies/{id}/protocol-drafts`, `…/protocol-drafts/diff`.

Роли: `GET /api/workspace/roles`, `POST /api/workspace/roles/check`.

Research Center (`backend/app/api/research_center.py`) остаётся отдельным низкоуровневым API
(`/api/research-tasks/{id}/run`, `/run-real-search`, `/api/research-results/{id}/register-source`,
разрешение конфликтов). Кнопка в панели пробелов не использует его напрямую — она идёт через
`/gaps/{code}/research`.

## 4. Состояние бэкенда

Полный прогон: **1990 тестов, все проходят** (`python -m pytest -q`, ~54 мин).

Новое/изменённое в фазе 29:

| Файл | Что |
|---|---|
| `app/domain/workspace_gaps.py` | новый — каталог пробелов, сбор, ручное закрытие, применение верифицированного |
| `app/domain/research_deep_read.py` | новый — чтение полного текста источников, вырезка фрагментов |
| `app/api/study_workspace.py` | + 4 ручки пробелов, выбор провайдера, сообщения писателю |
| `app/domain/research_extract.py` | вариабельность: синонимы, диапазоны, выбор фразы, выдержка по месту числа |
| `app/domain/research_evidence_models.py` | `CVintraEvidence.CV_range_low/high` |
| `app/domain/research_decision_bridge.py` | применяет и `expected_*`, и legacy-имена полей |
| `app/domain/workspace_progress.py` | человекочитаемые блокеры, маршрутизация на шаги |
| `app/domain/ai_runtime_settings.py` | `reset_runtime()` — снятие process-global оверрайдов |
| `tests/conftest.py` | autouse-фикстура сброса AI-состояния между тестами |

Тесты фазы: `tests/test_workspace_gaps.py` (10), `tests/test_workspace_gaps_api.py` (12),
`tests/test_research_deep_read.py` (10) — итого 32.

Инварианты, закреплённые тестами: ничего не верифицируется автоматически;
`study_mutated: False` у поиска и чтения; between-subject не выдаётся за CVintra; диапазон не
сворачивается в точку; статистические пробелы нельзя закрыть введённым значением (422);
предложение выживает после записи в БД (`after_mutation` чистит process-кэш, research-payload
персистится); недоступный источник не останавливает чтение.

## 5. Состояние фронтенда

`npx tsc --noEmit` — чисто. `npx vitest run` — **33 теста проходят** (6 файлов).

Навигация — 5 шагов пайплайна вместо 8 вкладок (`frontend/src/pages/StudyWorkspace.tsx`):
Обзор · **1. Документы** · **2. Данные** · **3. Пробелы** · **4. Решения** · **5. Протокол** · История.

- шаг «Решения» вмещает блоки Sample Size и Statistics (раньше отдельные вкладки-тупики);
- шаг «Протокол» вмещает финальную проверку («Что осталось сделать») и генерацию DOCX;
- вкладки Evidence / Sample Size / Statistics / Preflight удалены, их id мапятся через `TAB_ALIASES`.

| Файл | Что |
|---|---|
| `components/GapsPanel.tsx` | новый — карточки пробелов: поиск, предложения со ссылкой на источник, `related_findings`, ручной ввод, демо-набор |
| `components/EngineForms.tsx` | новый — `StatisticsPlanForm` (PRIMARY BE + популяция анализа), `SampleSizeCalcForm` |
| `api/client.ts` | типы `StudyGap`, `GapProposal`, `GapRelatedFinding`, `GapsPanel`, `GapResearchResult`; функции `listStudyGaps`, `researchStudyGap`, `verifyStudyGap`, `resolveStudyGapManually` |
| `nextAction.ts` | переписан: новые `NavId`, `TAB_ALIASES`, `buildPipelineSteps()` с агрегацией статусов |
| `workspace/refreshSlices.ts` | слайс `gaps` и алиасы обновления |
| `workspace/decisionExplain.ts` | объяснения ведут в шаг «Пробелы» (`nextTab: "gaps"`) |
| `writerLabels.ts` | `REASON_RU` + `humanReasons()` |
| `components/FindExpectedTmaxFlow.tsx` | удалён — заменён общей панелью пробелов |
| `styles/global.css` | `.gaps-panel`, `.gap-card`, `.gap-manual-form`, `.engine-form`, `.progress-step.current` |

## 6. Как пользователь проходит путь

1. **Документы** — загрузка вводных файлов, классификация.
2. **Данные** — извлечённые канонические факты, конфликты, проверка фактов.
3. **Пробелы** — то, чего в документах не было. По каждому: «Найти в источниках (ИИ)» →
   предложения PROPOSED с выдержкой и ссылкой → «Подтвердить» (право `approve_decisions`) →
   пересчёт зависимых доменов. Либо «Ввести вручную» со значением и обоснованием.
4. **Решения** — экспертные решения движков: PRIMARY BE, популяция анализа, расчёт размера выборки.
5. **Протокол** — что осталось сделать, предпросмотр, генерация DOCX.

## 7. Ограничения и очевидные следующие шаги

- Поиск идёт через HTML-выдачу DuckDuckGo без API-ключа: часть источников закрыта (403/paywall),
  такие документы перечисляются как недоступные. Подключение PubMed/Crossref API дало бы
  и стабильность, и метаданные.
- Глубокое чтение открывает до 5 источников за вызов и запускается только когда из сниппетов
  ничего не извлеклось. Повторный вызов не создаёт дублей, но и не расширяет охват — нужна
  постраничная стратегия «читать дальше».
- Экстракция детерминированная (регулярные выражения по фразам). Табличные значения
  (CV в таблицах PK-параметров) не читаются — это следующий крупный источник CVintra.
- `MISSING_ANALYTE` и `MISSING_MEAL_COMPOSITION` формально имеют маршрут RESEARCH, но качество
  извлечения для них не проверялось на живых источниках так подробно, как для Tmax/t½/CV.
- Русскоязычные источники (ОХЛП, ЕАЭС) в паттернах учтены, но живых прогонов по ним не было.
- Прогон полного бэкенд-набора занимает ~54 минуты; для итераций достаточно
  `tests/test_workspace_gaps*.py tests/test_research_deep_read.py tests/test_phase15_2*.py tests/test_phase15_3*.py`.

## 8. Среда разработки (грабли)

- Windows + PowerShell: команды соединять через `;`, не `&&`.
- `rg` и `find` через шелл недоступны (нет sandbox-бэкенда) — искать инструментом Grep.
- Живые сетевые прогоны требуют повышенных прав у команды (`full_network`).
- PDF-парсер шумит предупреждениями fontTools — глушить `-W ignore`, вывод смотреть с `-X utf8`.
- AI-настройки живут в process-global состоянии; между тестами их сбрасывает autouse-фикстура
  в `tests/conftest.py` (иначе один тест включал ИИ для следующих).

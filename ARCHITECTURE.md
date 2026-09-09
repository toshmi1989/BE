# Architecture — BE Protocol Platform

## Цель

Не чат для написания протокола и не find/replace по Word.

Система управляет **структурированной моделью исследования** и детерминированно генерирует протокол.

## Поток данных

```text
Structured Study
      ↓
Domain Rules (versioned)
      ↓
Calculations
      ↓
Validation (critical → block generate)
      ↓
Protocol Sections / TextBlocks
      ↓
DOCX Engine (template mapping)
```

## Слои

| Слой | Ответственность | Где живёт |
|------|-----------------|-----------|
| UI | формы, dashboard, статусы | `frontend/` |
| API | HTTP, auth (позже), DTO | `backend/app/api/` |
| Domain | rules, calc, provenance | `backend/app/domain/` |
| Persistence | ORM, migrations | `backend/app/models/`, Alembic |
| Protocol | sections, tables | Phase 6+ |
| DOCX | template, bookmarks, TOC | Phase 7+ |
| AI | extraction proposals | Phase 9, optional |

## Инварианты

1. Domain logic **не** в React.
2. Нет magic numbers — константы в versioned rules / `domain/constants`.
3. Critical fields имеют provenance + status.
4. AI не перезаписывает `VERIFIED` напрямую.
5. Отсутствующие данные не выдумываются (`MISSING` / `NEEDS_REVIEW`).
6. Critical validation issues блокируют финальную генерацию.
7. Schema changes — только через migrations.

## Phase 0 scope

Skeleton: repo, FastAPI health, React shell, Postgres compose, Alembic initial migration, pytest, docs.

## Phase 2 scope

Design Engine (validate + recommend), Food, Eligibility CRUD, SubjectPlan, ClientInput,
reference-data endpoint for UI templates, thin project-detail cards. No Research Engine.

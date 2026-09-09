# BE Protocol Platform

Web-платформа для детерминированного формирования протоколов клинических исследований биоэквивалентности.

## Архитектура (ядро)

```text
Structured Study → Domain Rules → Calculations → Validation → Protocol Sections → DOCX
```

AI — опциональный assistive layer. При выключенном AI приложение остаётся работоспособным.

## Стек

| Слой | Технология |
|------|------------|
| Backend | Python, FastAPI, Pydantic, SQLAlchemy |
| DB | PostgreSQL |
| Migrations | Alembic |
| Frontend | React, TypeScript, Vite |
| Tests | pytest |
| Runtime | Docker Compose |

## Структура репозитория

```text
backend/          FastAPI + domain core
frontend/         React UI (без domain logic)
docs/             SPEC, API, domain, rules
schemas/          JSON Schema исследования
templates/        исходный DOCX-шаблон
tests/            smoke / cross-cutting tests
docker-compose.yml
```

## Быстрый старт (локально, без Docker)

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload --port 8000
```

Health: `GET http://localhost:8000/api/health`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: `http://localhost:5173`

### PostgreSQL + Compose

Требуется установленный Docker Desktop / Docker Engine:

```bash
cp .env.example .env
docker compose up --build
```

- API: `http://localhost:8000`
- UI: `http://localhost:5173`
- Postgres: `localhost:5432`

Миграции внутри backend-контейнера:

```bash
docker compose exec backend alembic upgrade head
```

## Тесты

```bash
cd backend
pytest -q

# root smoke (structure)
cd ..
python -m pytest tests -q
```

## Фазы

Сейчас завершена **Phase 10** (End-to-End Validation + Golden Protocol).
Golden artifacts: `golden/`; report: [docs/PHASE10_E2E_REPORT.md](docs/PHASE10_E2E_REPORT.md).

## Документация

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [docs/SPEC.md](docs/SPEC.md)
- [docs/DOMAIN.md](docs/DOMAIN.md)
- [docs/API.md](docs/API.md)
- [docs/TESTING.md](docs/TESTING.md)

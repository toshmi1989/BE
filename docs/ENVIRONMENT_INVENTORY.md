# Runtime Environment Inventory

**Version:** 0.30.0  
**Status:** Documented for handoff. Compatibility claims limited to what images/files specify; **Docker/Postgres not executed on the current development host.**

## OS assumptions

- Linux or Windows host with Docker Engine + Compose V2 preferred for beta.
- Current Cursor workspace host: Windows without Docker CLI → beta compose **BLOCKED** here.

## Container images (from Dockerfiles / compose)

| Component | Specified | Notes |
|-----------|-----------|-------|
| Backend | `python:3.12-slim` | See `backend/Dockerfile` |
| Frontend | `node:22-alpine` | See `frontend/Dockerfile` |
| Postgres | `postgres:16-alpine` | See `docker-compose.beta.yml` |

Docker Engine / Compose **version range:** not empirically validated on this host (Docker absent). Use current Docker Desktop / Engine with Compose V2 plugin.

## Local (non-compose) optional

| Tool | Typical |
|------|---------|
| Python | 3.12+ (matches image) |
| Node | 22+ (matches image) |
| PostgreSQL | 16 (matches image) |

## Environment variables

See `.env.example`. Critical for beta:

- `POSTGRES_PASSWORD` (required by compose)
- `AUTH_SECRET` (required by compose; ≥24 chars, not a default)
- `AUTH_REQUIRED=true`
- `DATABASE_URL` (compose sets this for backend)

## Persistent volumes (compose)

| Volume | Purpose |
|--------|---------|
| `be_beta_pg_data` | Postgres data |
| `be_beta_docs` | Document uploads (`DOCUMENT_STORAGE_ROOT=/data/documents`) |
| `be_beta_artifacts` | Protocol/DOCX artifacts |

## Migrations

- Tool: Alembic (`backend/alembic.ini`)
- On backend container start: `alembic upgrade head` then uvicorn
- Fresh empty Postgres → migrate → health → ready (designed path; validate on beta host)

## Startup commands

```bash
# Preferred
export POSTGRES_PASSWORD=... AUTH_SECRET=... AUTH_REQUIRED=true
./scripts/start_beta.sh
# or Windows: .\scripts\start_beta.ps1

# Equivalent
docker compose -f docker-compose.beta.yml up -d --build
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/ready
curl -s http://127.0.0.1:8000/api/version
```

## Ports

| Service | Host port (default) |
|---------|---------------------|
| Backend API | 8000 |
| Frontend | 5173 |
| Postgres | 5433 |

## Health checks

- Compose DB: `pg_isready`
- App: `GET /api/health`, `GET /api/ready`

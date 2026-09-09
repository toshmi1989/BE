# Beta Host Handoff

**Version:** 0.30.0  
Move the repo to a **Docker-capable** host. Do not invent REAL packages or writers.

## 1. Prerequisites

- Docker Engine + Compose V2
- Git clone of this repository
- Strong secrets prepared offline (not committed)
- Read: `docs/ENVIRONMENT_INVENTORY.md`, `.env.example`

## 2. Installation

```bash
git clone <repo-url> BE && cd BE
cp .env.example .env.beta   # edit secrets
```

## 3. Env config

Set at minimum:

```bash
export POSTGRES_PASSWORD='<strong>'
export AUTH_SECRET='<strong-min-24-chars>'
export AUTH_REQUIRED=true
```

Never commit real secrets.

## 4–6. Database setup / migration / startup

```bash
./scripts/start_beta.sh
# Windows: powershell -File scripts/start_beta.ps1
```

Compose starts Postgres → waits healthy → backend runs `alembic upgrade head` → uvicorn.

Manual equivalent:

```bash
docker compose -f docker-compose.beta.yml up -d --build
```

## 7. Health check

```bash
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/ready
curl -s http://127.0.0.1:8000/api/version
python scripts/beta_preflight.py
python scripts/phase23_beta_gate.py
python scripts/collect_beta_diagnostics.py
```

## 8. Auth setup

- Stack forces `AUTH_REQUIRED=true` in compose.
- Register first admin/writer via `/api/auth/register` (or your org process).
- Confirm weak/default `AUTH_SECRET` rejected by preflight.

## 9. Organization / user setup

1. Create Organization A + Writer A (pseudonym for analytics, e.g. `W-01`).
2. Create Organization B + Writer B.
3. Verify A cannot open B studies (tenant isolation).

## 10. Package upload

- Only sanitized REAL packages → `fixtures/real_packages/` + intake API.
- Classes: **TEST** / **SYNTHETIC** / **REAL** — TEST/SYNTHETIC never increment REAL counters.
- Need **≥9 additional** distinct full REAL packages (current in-repo: 1 full + 1 partial).
- Checklist: `fixtures/real_packages/SANITIZATION_CHECKLIST.md`

## 11. Writer session

Follow `docs/WRITER_BETA_PROTOCOL.md` and UI **Controlled beta** tab:

1. MANUAL timer → stop  
2. SYSTEM_ASSISTED with same `pair_id` → stop  
3. Feedback  

Target ≥5 paired sessions before publishing time aggregates.

## 12–13. Backup / restore

**Do not report success until executed on the beta host.**

```bash
# Postgres backup
docker compose -f docker-compose.beta.yml exec -T db \
  pg_dump -U be_beta be_beta > backup_$(date +%Y%m%d).sql

# Artifact/document volumes (example)
docker run --rm -v be_beta_docs:/data -v "$PWD:/out" alpine \
  tar czf /out/be_beta_docs.tgz -C /data .
docker run --rm -v be_beta_artifacts:/data -v "$PWD:/out" alpine \
  tar czf /out/be_beta_artifacts.tgz -C /data .

# Restore (destructive — confirm): recreate volumes, restore dump + tarballs, restart stack
# docker compose -f docker-compose.beta.yml down
# ... restore pg + volumes ...
# docker compose -f docker-compose.beta.yml up -d
```

Verify after restore: org, users, studies, documents, evidence, decisions, snapshots, protocol drafts, artifacts, audit.

## 14. Shutdown

```bash
docker compose -f docker-compose.beta.yml down
# add -v only if intentionally wiping volumes
```

## 15. Logs

```bash
docker compose -f docker-compose.beta.yml logs -f backend
docker compose -f docker-compose.beta.yml logs -f db
```

Diagnostics (no secrets): `python scripts/collect_beta_diagnostics.py`

## 16. Troubleshooting

| Symptom | Action |
|---------|--------|
| Docker absent | Move host; compose cannot run |
| Postgres unavailable | `docker compose ps`; check `POSTGRES_PASSWORD` |
| Migration failure | `docker compose logs backend`; fix DB URL; rerun |
| Auth misconfiguration | `AUTH_REQUIRED=true`, strong `AUTH_SECRET` |
| Storage unavailable | Check `be_beta_docs` volume writable |
| Artifact mismatch | Restore artifacts volume with DB |
| Tenant access denied | Expected across orgs; verify wrong-org returns 403 |
| Workflow failure | Check preflight CRITICAL blockers; open conflicts |

## Beta entry gate

Authoritative: `scripts/phase23_beta_gate.py` / `GET /api/field-study/beta-gate`  
Do **not** weaken. `BETA_READY` only when criteria met.

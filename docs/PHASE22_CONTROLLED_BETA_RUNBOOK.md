# Phase 22 — Controlled Beta Runbook

**Version:** 0.27.0  
**Purpose:** Exact procedure for the first real controlled beta session.  
**Do not** invent packages, writers, timings, or ROI.

## 0. Preconditions

- Host with Docker (required for Postgres beta)
- Strong secrets prepared offline (do not commit)
- At least one sanitized REAL package ready for intake

Preflight:

```bash
cd <repo>
set AUTH_REQUIRED=true
set AUTH_SECRET=<strong-secret-min-24-chars>
set POSTGRES_PASSWORD=<strong-db-password>
set DATABASE_URL=postgresql+psycopg://be_beta:<password>@localhost:5433/be_beta
python scripts/beta_preflight.py
```

Expected: lines `[PASS] ...` and overall `BETA_PREFLIGHT PASS` or `WARN`.  
Any `[BLOCK]` → stop.

If Docker missing: overall `BLOCK` with `POSTGRES_EXECUTION_BLOCKED` — do not substitute file DB as Postgres proof.

---

## 1–4. Environment / secrets / Postgres / migrations

```bash
# 1–2. Configure (example .env.beta — do not commit secrets)
# POSTGRES_PASSWORD=...
# AUTH_SECRET=...
# AUTH_REQUIRED=true

# 3–4. Start stack (runs alembic upgrade head on backend start)
docker compose -f docker-compose.beta.yml up -d --build
```

Expected:

```text
db ... healthy
backend ... started
```

Checks:

```bash
curl -s http://localhost:8000/api/health
curl -s http://localhost:8000/api/ready
```

Expected JSON with `"status"` healthy/ready and version `0.27.0`.

---

## 5–7. Organization / writer / study

Use existing auth + projects/studies APIs (AUTH_REQUIRED=true).

```bash
# Register / login per deployment auth endpoints
# Create organization membership (tenant isolation)
# Create study key e.g. STUDY-BETA-001
```

Expected: authenticated responses; cross-tenant access denied.

Writer identity in field-study analytics must be a **pseudonym** (`W-…`), not email.

---

## 8–9. Sanitize + upload

```bash
# Validate filenames (heuristic only)
curl -s -X POST http://localhost:8000/api/field-study/intake/validate-filenames \
  -H "Content-Type: application/json" \
  -d "{\"filenames\":[\"synopsis.docx\",\"checklist.docx\"]}"
```

Expected: `"ok": true`. If blocked → do not upload.

Complete sanitization checklist (`fixtures/real_packages/SANITIZATION_CHECKLIST.md`).  
Only then:

```bash
curl -s -X POST http://localhost:8000/api/field-study/intake/cases/.../sanitization \
  -H "Content-Type: application/json" \
  -d "{\"sanitized\":true,\"notes\":\"checklist completed\"}"
```

Upload study documents via study-input / workspace upload endpoints.  
Inventory statuses: PRESENT / ABSENT / NOT_REQUIRED (absence ≠ automatic error).

---

## 10–20. Writer workflow (system-assisted)

In Study Workspace (or API equivalents):

10. Review extraction — classify fields (`CORRECT_AUTO` / …)  
11. Review conflicts — no AI auto-resolve  
12. Review evidence / provenance  
13. Research Center — real queries only  
14. Expert decisions — recommendation ≠ approval  
15. Sample size — ACCEPTED/MODIFIED/REJECTED/BLOCKED  
16. Statistics — same  
17. Generate protocol  
18. Preflight — CRITICAL blockers stop FINAL  
19. Generate DOCX — open and review  
20. Writer review + corrections

Invariant: AI cannot approve decisions, conflicts, sample size, statistics, or FINAL.

---

## 21. Field-study timings (paired)

UI: **Controlled beta** tab → Session launcher  
Or API:

```bash
# Manual baseline
curl -s -X POST http://localhost:8000/api/field-study/sessions/timed/start \
  -H "Content-Type: application/json" \
  -d "{\"case_id\":\"REAL-…\",\"writer_id\":\"W-01\",\"session_type\":\"MANUAL\"}"
# → pair_id, session_id ; timer running (CASE_STARTED, SESSION_STARTED)

curl -s -X POST http://localhost:8000/api/field-study/sessions/<session_id>/timed/stop \
  -H "Content-Type: application/json" -d "{}"
# → SESSION_COMPLETED, CASE_COMPLETED ; duration from timestamps

# Assisted (same pair_id)
curl -s -X POST http://localhost:8000/api/field-study/sessions/timed/start \
  -H "Content-Type: application/json" \
  -d "{\"case_id\":\"REAL-…\",\"writer_id\":\"W-01\",\"session_type\":\"SYSTEM_ASSISTED\",\"pair_id\":\"PAIR-…\"}"
```

No estimated times. Aggregates publish only at n≥5 paired.

---

## 22–23. Backup / restore

```bash
# Backup (example)
docker compose -f docker-compose.beta.yml exec db \
  pg_dump -U be_beta be_beta > backup_$(date +%Y%m%d).sql
# Also snapshot document/artifact volumes

# Restore into clean volume (destructive — confirm)
# docker compose ... down -v
# up db; psql < backup_….sql; restore volumes
```

Verify after restore: study, documents, evidence, decisions, snapshot, protocol, artifact, audit.

Record `BACKUP_OK` / `RESTORE_OK` or exact failure in ops evidence JSON.

Supplemental file-DB script (not Postgres proof):

```bash
python scripts/beta_backup_restore_check.py
python scripts/phase20_field_ops_execution.py
```

---

## 24. Export metrics

```bash
curl -s http://localhost:8000/api/field-study/export > field_study_export.json
python scripts/generate_phase22_report.py field_study_export.json
```

Expected: `docs/PHASE22_BETA_READINESS_REPORT.md` with only observed metrics.

---

## Status

```bash
curl -s http://localhost:8000/api/field-study/status
```

Expect until evidence exists:

```text
BETA NOT READY
Reason: only 1 full real package; 0 writers; 0 paired sessions; Postgres not executed
```

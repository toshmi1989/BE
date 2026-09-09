# Phase 17.5 — Multi-Worker Consistency Hardening

**Version:** 0.22.1

## Goals

- DB is the **authoritative** source for workspace state
- Process memory is an optimization only
- Multi-worker / multi-process reads stay consistent
- Concurrent snapshot/decision mutations are race-safe
- Canonical tenant **Organization** model (vs project-party **StudyParty**)

## DB authority

Every canonical API read uses `ensure_db_authoritative` /
`read_workspace_summary` / `read_readiness` / `read_preflight`:

```
request → authz → hydrate from DB (clear process cache) → respond
```

Stale process-local state cannot override DB.

## Cache policy

| Event | Action |
|-------|--------|
| API read | hydrate from DB first |
| Mutation (decision, snapshot, upload, workflow, audit, DOCX) | `persist` then `invalidate_study_cache` |
| Conflict | **DB wins** |

Module: `app.domain.workspace_authority`

## Transactions / concurrency

- Snapshot versions: `UNIQUE(study_key, version)` + retry on `IntegrityError`
- Content-hash / idempotency-key short-circuit duplicate logical creates
- Protocol drafts: `UNIQUE(study_key, version)` (existing)
- Artifacts: unique `artifact_id`; download verifies sha256 vs stored bytes

## Organization model

| Model | Table | Role |
|-------|-------|------|
| **Organization** (alias `WorkspaceOrganization`) | `workspace_organizations` | Canonical **tenant** — users, memberships, studies |
| **StudyParty** (alias `Organization` in project APIs) | `organizations` | Project-scoped CRO/site/ethics party |

Target tree:

```
Organization (tenant)
 ├── Users / Memberships
 └── WorkspaceStudy
```

## Idempotency

- `Idempotency-Key` header and/or body `idempotency_key` on workflow / snapshots / decisions
- Completed workflow replay returns prior `workflow_id` without duplicating drafts/snapshots
- Decision replay by stable `decision_id`

## Artifact integrity

On download: recompute sha256 of stored bytes; mismatch → refuse delivery.

## Workflow recoverability

`WorkspaceWorkflowRun` persists stage/status/steps/error.  
`GET /api/workflows/{workflow_id}` returns durable state after crash/restart.

## Migration

`0015_phase17_5_consistency` — `state_version`, snapshot/workflow `idempotency_key` indexes.

## Known limitations

- Process cache invalidation is study-global (clears working set); acceptable for correctness
- StudyParty remains project-scoped (intentional dual use of “organization” word in protocol admin)
- True cross-process locking relies on DB unique constraints (SQLite in-memory tests use one engine)

## Production readiness

Improved vs 0.22.0 for multi-worker; still **READY-WITH-BLOCKERS** until production `AUTH_REQUIRED=true` and strong `AUTH_SECRET`.

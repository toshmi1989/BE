# Phase 17 — Production Workspace Hardening

**Version:** 0.22.0 → see also **0.22.1** ([PHASE17_5_MULTI_WORKER_CONSISTENCY.md](./PHASE17_5_MULTI_WORKER_CONSISTENCY.md))

Removes critical process-memory dependency for Study Workspace, adds real
authentication + organization isolation, and routes Preview/DOCX through
canonical ProtocolDraft → Artifact storage (not Legacy Project generation).

## CURRENT → TARGET

| CURRENT | TARGET |
|---------|--------|
| Project ORM ‖ in-memory Study lane | Organization → WorkspaceStudy → bags/snapshots |
| Soft RBAC string | User + Membership + signed token |
| tempfile / memory packages | Persistent workspace_documents + state bags |
| Protocol draft markers only | DB drafts + DOCX artifacts on disk |
| Workspace → Legacy Project DOCX | Workspace → Snapshot → Draft → Artifact |

## Persistence model

Tables (Alembic `0014_phase17_workspace`):

- `workspace_organizations`, `user_accounts`, `org_memberships`, `workspace_studies`
- `workspace_state_bags` — serialized package + draft/audit meta
- `workspace_snapshots` — immutable canonical versions
- `workspace_decisions`, `workspace_evidence_claims`, `workspace_documents`
- `workspace_protocol_drafts`, `workspace_protocol_artifacts`
- `workspace_audit_events`, `workspace_workflow_runs`

Engines (decision / sample size / statistics / research) remain unchanged;
`persist_workspace_bundle` / `hydrate_workspace_bundle` bridge memory ↔ DB.

## Auth model

- Password: stdlib `scrypt` (never plaintext)
- Token: HMAC-signed bearer (`be1.<payload>.<sig>`)
- `AUTH_REQUIRED=false` by default (dev / regression); set `true` in production
- `AUTH_SECRET` must be overridden outside local dev

## RBAC

Roles: ADMIN, MEDICAL_WRITER, REVIEWER, VIEWER  
Vocabulary reused from `workspace_rbac.py`; membership role enforced when
authenticated.

## Organization isolation

Studies belong to `workspace_organizations`. Cross-org access returns 404/403
(IDOR-safe).

## Snapshot versioning

Approved expert decisions create a **new** snapshot. Prior snapshots are never
mutated. Protocol drafts reference snapshot ids.

## Protocol artifacts

`POST /studies/{id}/protocol/generate-docx` → Preflight → Renderer → store bytes  
`GET .../artifacts/{id}/download` returns **stored** bytes + integrity hash  
(no rebuild from mutable state).

`legacy_project_path: false` on workspace preview.

## Workflow state

Runs persist to `workspace_workflow_runs` with stage/status/error/steps.

## Security

- Auth required mode → 401 without token
- Org isolation tests
- Viewer cannot run workflow
- Upload: extension allow-list, size limit, path traversal denied, safe storage names

## Migrations

`alembic upgrade head` applies `0014_phase17_workspace` after `0013`.

## Known limitations

- ~~Phase 14–15 engine hot-path still uses in-process caches; durability is via
  explicit persist/hydrate (called from workflow API)~~ **Addressed in 17.5:**
  API reads are DB-authoritative (`workspace_authority`).
- Study-party orgs are **StudyParty** (`organizations`); tenant is **Organization**
  (`workspace_organizations`) — see Phase 17.5 docs.
- Legacy Dashboard / Project protocol path kept for backward compatibility
- Full evidence claim dual-write from every Research Center mutation remains partial
- Production needs strong `AUTH_SECRET` and `AUTH_REQUIRED=true`

## Production readiness

**READY-WITH-BLOCKERS** for controlled deployments with auth enabled; expert
approvals still required before FINAL.

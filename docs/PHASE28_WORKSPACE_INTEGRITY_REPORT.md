# PHASE 28 — Workspace Contract & State Integrity

**Version:** 0.33.0

## Summary

Writer Workspace is now **DB-authoritative** for study-key state. Engine payloads
(decisions, sample size, statistics, research) round-trip through
`WorkspaceStateBag`. Study creation is unified under `WorkspaceStudy` with a
**globally unique `study_key`**. Frontend starts at **Мои исследования**, uses
Bearer auth when required, typed contract parsers, operation-local loading, and
`DecisionForm` (no Writer `window.prompt`). Protocol/DOCX reject **stale**
dependency identities after approved state drifts.

Legacy `Project` / `project_id` APIs remain isolated compatibility surface.

## Architecture

See `docs/PHASE28_WORKSPACE_ARCHITECTURE.md`.

Canonical ownership:

`Organization → WorkspaceStudy (global study_key) → Workspace state bags / documents / snapshots / drafts / artifacts`

## Delivered

| Area | Status |
|------|--------|
| Architecture doc + Alembic `0016` (global unique key, catalog denorm) | Done |
| Engine state collect/hydrate round-trip | Done |
| Unified study create + `GET /api/studies` catalog | Done |
| Document count from `WorkspaceDocumentRecord` | Done |
| Canonical facts: real status/source/evidence_id; empty `affected_sections` | Done |
| Pydantic Writer response models (`writer_phase28.py`) | Done |
| Protocol dependency stale checker → preflight CRITICAL + DOCX block | Done |
| Draft `based_on_snapshot` = SNAP-* (not package_id) | Done |
| Frontend contracts + Bearer auth + AuthProvider | Done |
| Study list entry + targeted refresh slices | Done |
| DecisionForm + decision detail panel | Done |
| Phase 28 contract/restart/security/golden/AI-off tests | Done |
| Version bump 0.33.0 | Done |

## Tests

- Backend: `tests/test_phase28_workspace_contract.py` (16)
- Frontend Vitest: contracts, auth 401/403, StudyList, DecisionForm (19)
- Regressions: Phase 26–27, 15–17 persistence/engine suites (after soft-fail for memory-only fixtures)

## Guards retained

- Recommendation ≠ approval
- No auto-resolve of critical conflicts
- AI-off path remains functional
- Org isolation + role gates when `AUTH_REQUIRED=true`

## Remaining production blockers

1. **Global cache invalidate** still clears all studies’ process memory (Phase 17.5 limitation); multi-study workers rely on per-request hydrate.
2. **`/api/auth/me` permissions[]** not yet a first-class API field — frontend mirrors RBAC by role.
3. **Extraction quality** for real multi-doc packages unchanged (pipeline-bound).
4. **Medical engines** still require real CV / PRIMARY BE expert selection before SS/statistics FINAL.
5. **Controlled beta host gate** unchanged from prior phases.
6. Soft-fail when workspace tables missing allows legacy Phase 15 memory-only fixtures; production must always run migrations through `0016`.

## Migration

```text
alembic upgrade head   # includes 0016_phase28_workspace_integrity
```

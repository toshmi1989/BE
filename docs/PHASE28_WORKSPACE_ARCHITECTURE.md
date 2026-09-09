# Phase 28 — Workspace Architecture & State Ownership

**Version:** 0.33.0  
**Goal:** One writable source of truth for the Writer Workspace path.

## Canonical model

```
Organization (workspace_organizations)
  └── WorkspaceStudy (study_key — globally unique)
        └── Workspace state (workspace_state_bags + documents/snapshots/artifacts)
```

Legacy `Project` / `project_id` remains for compatibility APIs under `/api/projects/*`.
It is **not** a writable twin of Writer state.

## Ownership labels

| Domain | Writer path (canonical) | Derived | Legacy (isolated) |
|--------|-------------------------|---------|-------------------|
| Study registry | `WorkspaceStudy` | catalog readiness fields on same row | `Project` / `Study` ORM |
| Documents | `WorkspaceDocumentRecord` | UI status from ingestion/classification/extraction | `Document` / pages / chunks |
| Package / facts | `StudyInputPackage` in `package_payload` | `canonical_facts` projection | ClientInput / Product ORM |
| Decisions (recommendations + expert actions) | In-memory Decision Center restored from `decisions_payload` | `WorkspaceDecisionRecord` audit/projection | `ExpertDecisionRecord` |
| Sample size | `SampleSizeCalculationRecord` in `sample_size_payload` | readiness / writer-progress | `SampleSizeCalculation` ORM |
| Statistics | `StatisticsPlan` in `statistics_payload` | readiness / writer-progress | `StatisticalConfig` / CV tables |
| Research | Research store restored from `research_payload` | coverage views | Project research case ORM |
| Protocol draft | Memory drafts + `WorkspaceProtocolDraftRecord` | preview | `ProtocolDraft` tree |
| DOCX | `WorkspaceProtocolArtifact` | download URL | `GeneratedDocument` |
| Snapshots | `WorkspaceSnapshotRecord` | progress versions | `ProjectVersion` |

## Temporary bridges

- `POST /api/auth/studies` delegates to the same create service as `POST /api/studies/create`.
- Golden UPDCB keys may auto-bind into the caller's org for fixtures only.
- Decision Center approvals remain authoritative in `decisions_payload`; workspace expert endpoint also writes `WorkspaceDecisionRecord` for audit.

## Rules

1. Writer APIs must hydrate from DB before mutation and persist after mutation.
2. Document counts for workspace / overview / progress use `WorkspaceDocumentRecord` only.
3. Protocol / DOCX must reject stale draft dependencies vs current approved SS / stats / snapshot.
4. No silent dual-write to Legacy Project tables from Writer mutations.

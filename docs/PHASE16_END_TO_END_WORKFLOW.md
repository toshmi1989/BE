> **Phase 17 (0.22.0):** Persistence, auth, and org isolation — see
> [PHASE17_PRODUCTION_WORKSPACE_HARDENING.md](./PHASE17_PRODUCTION_WORKSPACE_HARDENING.md).

# Phase 16 — End-to-End Protocol Workflow Integration

**Version:** 0.21.0 (superseded by 0.22.0 for production hardening)  

Composes existing Phase 14–15 engines into a Study Workspace. Does **not** create
parallel medical engines.

## 1. Architecture

```
Documents (Study Input)
  → Candidates / Conflicts / Gaps
  → Decision Center recommendations
  → Research Center (optional)
  → Sample Size Engine (deterministic)
  → Statistics Engine (deterministic)
  → Readiness / Preflight
  → Protocol Draft versions
  → DOCX (gated by CRITICAL blockers)
```

Orchestrator: `app.domain.protocol_workflow.run_protocol_workflow`  
Workspace: `app.domain.study_workspace`  
API: `/api/studies/{id}/workspace|readiness|conflicts|preflight|audit|workflow/run`

## 2. User workflow

1. Open Study Workspace  
2. Run UPDCB workflow (or upload docs via Legacy console)  
3. Review conflicts (15 vs 30 mg never auto-resolved)  
4. Expert decisions / evidence review  
5. Sample size + statistics recommendations  
6. Preflight  
7. Protocol draft / DOCX only when CRITICAL clear  

## 3. Lifecycle

`DRAFT → INGESTING → EXTRACTED → REVIEW_REQUIRED → DECISIONS_PENDING →
READY_FOR_PROTOCOL → PROTOCOL_DRAFT → QA_REQUIRED → READY_FOR_FINAL → FINAL`

Transitions requiring expert approval are **not** automatic.

## 4–8. Decision / evidence / sample size / statistics / protocol

Reuse Phase 15 Decision Center, Research Center, Sample Size Engine, Statistics
Engine, Protocol Assembly + DOCX. Recommendation ≠ approval.

## 9. Preflight

Categories: documents, data, evidence, decisions, sample size, statistics, protocol.  
Severities: INFO / WARNING / CRITICAL.  
CRITICAL → cannot FINALIZE / DOCX gated.

## 10. Security

Soft RBAC vocabulary: ADMIN / MEDICAL_WRITER / REVIEWER / VIEWER  
(`workspace_rbac.py`). No JWT rewrite. Upload validation remains Phase 14.1.

## 11. Deployment

Existing `docker-compose.yml`, `/api/health`, `/api/ready`. AI defaults off.

## 12. Known blockers / limitations

- ORM Project protocol path and Phase 14–15 in-memory study lanes remain bridged
  by expert projection (no silent Study mutation)  
- Soft RBAC is not full multi-tenant auth  
- Protocol draft versions in workspace store are markers; full DOCX still via
  project protocol endpoints  
- Golden E2E leaves CRITICAL dose conflict open until expert resolves  

## 13. Observability

Workflow runs emit a `workflow_id` on every step payload from
`run_protocol_workflow`. Use it to correlate ingestion, research, sample size,
statistics, readiness, and preflight logs for one study run.

Health: `GET /api/health` · Ready: `GET /api/ready`

## Ready vs requires expert

| Ready | Requires expert |
|-------|-----------------|
| Workflow orchestration | Resolve 15/30 mg dose |
| Conflict Center visibility | Approve PRIMARY_BE |
| Preflight / readiness | Approve sample size / statistics |
| AI-off path | FINAL / production sign-off |


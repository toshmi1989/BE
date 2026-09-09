# PHASE 26 — Writer Workflow UX Completion

**Version:** 0.31.0  
**Gate:** Writer workspace usable without Legacy console for normal flow.

## Summary

Study Workspace primary UX is a medical-writer workflow: New Study → upload → analyze → review data/decisions → sample size / statistics → protocol preview / DOCX / preflight. Demo UPDCB is separated. Controlled beta and Legacy console moved under Advanced.

## Delivered

| Area | Change |
|------|--------|
| New Study | `POST /api/studies/create` + UI `+ New Study` |
| Documents | Upload document / package, checklist, Analyze package |
| Demo vs real | `Run demo UPDCB workflow` vs `Analyze study package` |
| NEXT ACTION | Overview clickable next step |
| Canonical | Review / Edit proposal with audit (no silent SoT mutation) |
| Decisions | Approve / Reject / Modify / Request evidence / View sources |
| Sample Size / Statistics | Actionable empty + approve paths |
| Protocol | Preview, preflight, Generate DOCX from Workspace |
| Nav | Primary RU writer nav; Advanced / Legacy secondary |
| Labels | Humanized enums in UI (`writerLabels.ts`) |
| Persistence | Persist never clobbers package with `None` after cache invalidate |

## Tests

- `backend/tests/test_phase26_writer_ux.py` — create, upload, E2E no Legacy, golden conflict, AI-off
- Regression: Phase 16–17 (+ Phase 15–25 suite)

## Known limitations

- Real multi-document analyze still depends on existing package/workflow engines (no new medical rules).
- Some sample-size / statistics approvals remain blocked until verified inputs / PRIMARY BE expert selection (by design).
- Controlled beta host gate remains **BETA_NOT_READY** (unchanged from Phase 25).

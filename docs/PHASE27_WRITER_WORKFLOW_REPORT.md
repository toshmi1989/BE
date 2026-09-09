# PHASE 27 — Guided Writer Workflow & Protocol Generation

**Version:** 0.32.0

## Summary

Study Workspace presents one continuous guided medical-writer path from package upload to DOCX, driven by backend progress state (not UI clicks). Demo UPDCB remains under Advanced only.

## Delivered

| Area | Status |
|------|--------|
| Progress rail (8 steps) | Backend `GET /writer-progress` |
| Single primary next action | RU labels + navigate |
| Actionable blockers | WHAT / WHY / WHERE / ACTION |
| New Study wizard | 5 steps |
| Upload + classify | Workspace only |
| Analyze stages + summary | UX over existing workflow |
| Canonical + field drawer | `canonical-facts/.../detail` |
| Decisions + dependency impact | `affects` on expert approve |
| Sample Size / Statistics | Actionable blocked/available |
| Protocol builder + preview | TOC / body / field panel |
| Preflight routes | No dead-ends |
| DOCX confirm + download | Critical blockers disable |
| Humanized enums | Extended labels |
| Demo separation | Advanced only |

## Tests

- `test_phase27_writer_workflow.py`
- Golden: 15 vs 30 remains OPEN until expert
- AI-off: workflow functional

## Known limitations

- Medical engines unchanged; SS/statistics remain blocked until real inputs / PRIMARY BE expert selection.
- Real multi-doc extraction quality still depends on existing package pipeline.
- Controlled beta host gate unchanged.

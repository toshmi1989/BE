#!/usr/bin/env python3
"""Generate docs/PHASE22_BETA_READINESS_REPORT.md from field-study export.

Only reports metrics present in the export / live status — never invents ROI.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "docs" / "PHASE22_BETA_READINESS_REPORT.md"


def main(argv: list[str]) -> int:
    from app.domain.field_study_status import field_study_status
    from app.domain.field_study import production_readiness
    from app.domain.controlled_beta import export_field_study, intake_slots_dashboard, writer_session_dashboard

    export = export_field_study()
    if len(argv) > 1:
        path = Path(argv[1])
        if path.exists():
            export = json.loads(path.read_text(encoding="utf-8-sig"))

    st = field_study_status()
    gate = production_readiness()
    intake = intake_slots_dashboard()
    sess = writer_session_dashboard()

    def obs(label: str, value: object) -> str:
        if value in (None, "", [], {}, 0) and label.endswith("time"):
            return "not observed"
        return str(value)

    lines = [
        "# Phase 22 — Beta Readiness Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Packages",
        f"- Full REAL: **{st.get('real_full_packages')}**",
        f"- Partial: **{st.get('real_partial_packages')}**",
        f"- Display: {intake.get('display')}",
        f"- Empty slots: {intake.get('empty')}",
        "",
        "## Writers / sessions",
        f"- Writers: **{sess.get('writers')}**",
        f"- Sessions: **{sess.get('sessions')}**",
        f"- Paired: **{sess.get('paired')}** (complete: {sess.get('paired_complete')})",
        f"- Completed: **{sess.get('completed')}**",
        "",
        "## Postgres / backup / restart",
        f"- Postgres ops: **{st.get('postgres_ops')}**",
        f"- Backup/restore: **{st.get('backup_restore')}** (file DB supplemental ≠ Postgres proof)",
        f"- Restart test: **{st.get('restart_test')}**",
        "",
        "## Timing / ROI",
        "- Aggregate timing: **unpublished** unless n≥5 observed paired sessions in export",
        f"- Timing aggregates published flag: {st.get('timing_aggregates_published')}",
        "",
        "## Issues",
        f"- Open P1: {', '.join(st.get('open_P1') or []) or 'none listed'}",
        "",
        "## Production gate",
        f"- **{gate.get('gate')}** / beta label **{st.get('beta_label')}**",
        "- Reasons:",
    ]
    for r in st.get("reasons") or []:
        lines.append(f"  - {r}")
    lines.extend(
        [
            "",
            "## Export summary",
            f"- Sessions in export: {len(export.get('sessions') or [])}",
            f"- Secrets included: {export.get('secrets_included')}",
            f"- Document contents included: {export.get('document_contents_included')}",
            "",
            "## Note",
            "No metric invented. Controlled Beta still requires ≥10 full REAL, ≥5 paired sessions, Postgres executed.",
            "",
        ]
    )
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("WROTE", OUT.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

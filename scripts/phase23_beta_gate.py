#!/usr/bin/env python3
"""Phase 23 — Controlled beta entry gate.

Exit 0 = PASS (or WARN-only), 2 = BLOCK.
Never prints secret values.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    from app.domain.beta_entry_gate import beta_gate_checks

    report = beta_gate_checks()
    print(f"PHASE23_BETA_GATE {report['overall']}")
    print(f"state={report['entry']['state']} classification={report['entry']['classification']}")
    for c in report["checks"]:
        print(f"  [{c['result']}] {c['id']}: {c['detail']}")
    print(
        f"summary pass={report['pass_count']} warn={report['warn_count']} "
        f"block={report['block_count']} secrets_exposed={report['secrets_exposed']}"
    )
    if report["entry"]["blockers"]:
        print("blockers:")
        for b in report["entry"]["blockers"]:
            print(f"  - {b}")
    out = ROOT / "fixtures" / "field_study" / "phase23_gate_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Strip any accidental secret fields
    safe = json.loads(json.dumps(report, default=str))
    out.write_text(json.dumps(safe, indent=2) + "\n", encoding="utf-8")
    print("WROTE", out.as_posix())
    return 2 if report["overall"] == "BLOCK" else 0


if __name__ == "__main__":
    raise SystemExit(main())

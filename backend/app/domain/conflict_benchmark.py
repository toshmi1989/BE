"""Phase 19 — Conflict detection benchmark on REAL packages (labeled).

Aggregate precision/recall/F1 only when expected labels are reliable.
"""

from __future__ import annotations

from typing import Any

from app.domain.study_input_pipeline import load_real_fixture_package

# Reliable expected labels for UPDCB writer golden package only
UPDCB_EXPECTED_CONFLICTS: tuple[dict[str, str], ...] = (
    {
        "type": "dose",
        "field_path": "reference_product.dose",
        "note": "Checklist 30 mg vs synopsis/SmPC 15 mg (OPEN CRITICAL)",
    },
)


def _normalize_type(raw: str | None) -> str:
    t = (raw or "").lower()
    for key in (
        "dose",
        "reference",
        "design",
        "washout",
        "food",
        "sampling",
        "pk",
        "population",
        "statistics",
    ):
        if key in t:
            return key
    return t or "unknown"


def evaluate_updcb_conflicts() -> dict[str, Any]:
    """Compare expected UPDCB dose conflict vs pipeline detections."""
    pkg = load_real_fixture_package()
    detected_raw = list(getattr(pkg, "conflicts", None) or [])
    detected_types: list[str] = []
    for c in detected_raw:
        if isinstance(c, dict):
            detected_types.append(
                _normalize_type(str(c.get("type") or c.get("field_path") or c.get("kind") or ""))
            )
        else:
            detected_types.append(_normalize_type(str(getattr(c, "field_path", "") or getattr(c, "type", ""))))

    expected_types = [_normalize_type(e["type"]) for e in UPDCB_EXPECTED_CONFLICTS]
    expected_set = set(expected_types)
    detected_set = set(detected_types)

    tp = expected_set & detected_set
    fp = detected_set - expected_set
    fn = expected_set - detected_set

    precision = (len(tp) / (len(tp) + len(fp))) if (tp or fp) else None
    recall = (len(tp) / (len(tp) + len(fn))) if (tp or fn) else None
    f1 = None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "case_id": "REAL-UPDCB-02-BE-2026",
        "labels_reliable": True,
        "expected_conflicts": list(UPDCB_EXPECTED_CONFLICTS),
        "detected_count": len(detected_raw),
        "detected_types": sorted(detected_set),
        "true_positives": sorted(tp),
        "false_positives": sorted(fp),
        "missed_conflicts": sorted(fn),
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "auto_resolve_forbidden": True,
        "aggregate_note": (
            "Only UPDCB has reliable expected conflict labels among REAL packages in-repo. "
            "Do not extrapolate F1 to synthetic fixtures as real-case quality."
        ),
        "b001_status": "monitor",
        "b001_still_blocker": False,
        "b001_note": "OPEN dose conflict is correct behavior; blocks FINAL until expert resolution",
    }


def conflict_benchmark_summary() -> dict[str, Any]:
    updcb = evaluate_updcb_conflicts()
    return {
        "real_cases_with_reliable_labels": 1,
        "cases": [updcb],
        "aggregate_precision": updcb.get("precision"),
        "aggregate_recall": updcb.get("recall"),
        "aggregate_f1": updcb.get("f1"),
        "aggregate_valid": True,
        "limitation": "n=1 reliable REAL labeled case; expand when more sanitized packages land",
    }

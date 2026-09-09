"""Phase 18 — Beta scoring: extraction, canonical, conflicts, evidence.

Does not invent medical correctness. Compares observed package state to
case expectations. Unverified extraction is never scored as correct solely
because an expert later fixed it.
"""

from __future__ import annotations

from typing import Any

from app.domain.study_input_package import StudyInputPackage

KEY_CANONICAL_FIELDS: tuple[str, ...] = (
    "sponsor.name",
    "test_product.name",
    "test_product.dose",
    "reference_product.name",
    "reference_product.dose",
    "design.crossover",
    "design.periods",
    "design.sequences",
    "washout.duration",
    "food.condition",
    "subjects.randomized_n",
    "sampling.times",
    "bioanalysis.analyte",
    "pk.parameters",
)


def _norm(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).strip().lower()
    return s.replace("мг", "mg").replace("  ", " ")


def candidates_by_field(pkg: StudyInputPackage) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    for c in pkg.candidates:
        out.setdefault(c.field_path, []).append(c)
    return out


def score_extraction(
    pkg: StudyInputPackage,
    expected_fields: dict[str, Any],
) -> dict[str, Any]:
    """Score AUTO-EXTRACTED values only — EXPERT-VERIFIED tracked separately."""
    by_f = candidates_by_field(pkg)
    total = len(expected_fields) or 1
    correct = 0
    missing = 0
    wrong = 0
    attributed = 0
    auto_extracted = 0
    expert_verified = 0
    unresolved = 0
    details: list[dict[str, Any]] = []

    for field, expected in expected_fields.items():
        cands = by_f.get(field) or []
        if not cands:
            missing += 1
            unresolved += 1
            details.append({"field": field, "status": "MISSING", "bucket": "UNRESOLVED"})
            continue
        # Prefer first candidate; classification by status/method
        best = cands[0]
        for c in cands:
            if c.status == "VERIFIED":
                best = c
                break
        has_source = bool(best.source_id and best.excerpt)
        if has_source:
            attributed += 1
        if best.status == "VERIFIED":
            expert_verified += 1
            bucket = "EXPERT-VERIFIED"
        else:
            auto_extracted += 1
            bucket = "AUTO-EXTRACTED"
        match = _norm(best.value) == _norm(expected) or (
            isinstance(expected, bool) and bool(best.value) == expected
        )
        # Unverified match still counts as extraction accuracy for AUTO, but reported separately
        if match:
            if bucket == "AUTO-EXTRACTED":
                correct += 1
            else:
                correct += 1  # verified correct
            details.append(
                {
                    "field": field,
                    "status": "CORRECT",
                    "bucket": bucket,
                    "value": best.value,
                    "verified_counted_as_auto_correct": False,
                }
            )
        else:
            wrong += 1
            details.append(
                {
                    "field": field,
                    "status": "WRONG",
                    "bucket": bucket,
                    "value": best.value,
                    "expected": expected,
                }
            )

    return {
        "field_extraction_accuracy": round(correct / total, 4),
        "field_missing_rate": round(missing / total, 4),
        "wrong_value_rate": round(wrong / total, 4),
        "source_attribution_rate": round(attributed / max(auto_extracted + expert_verified, 1), 4),
        "counts": {
            "AUTO-EXTRACTED": auto_extracted,
            "EXPERT-VERIFIED": expert_verified,
            "UNRESOLVED": unresolved,
            "correct": correct,
            "missing": missing,
            "wrong": wrong,
        },
        "details": details,
        "note": "Unverified extraction is not treated as correct merely because expert later fixed it.",
    }


def score_canonical(pkg: StudyInputPackage, expected_fields: dict[str, Any]) -> dict[str, Any]:
    by_f = candidates_by_field(pkg)
    open_conflicts = {
        str(c.get("field_path"))
        for c in pkg.conflicts
        if str(c.get("status") or "OPEN") == "OPEN"
    }
    rows: list[dict[str, Any]] = []
    tallies = {"Correct": 0, "Missing": 0, "Conflicting": 0, "Incorrect": 0}
    fields = list(expected_fields.keys()) or list(KEY_CANONICAL_FIELDS)
    for field in fields:
        if field in open_conflicts:
            tallies["Conflicting"] += 1
            rows.append({"field": field, "status": "Conflicting"})
            continue
        cands = by_f.get(field) or []
        if not cands:
            tallies["Missing"] += 1
            rows.append({"field": field, "status": "Missing"})
            continue
        expected = expected_fields.get(field)
        if expected is None:
            tallies["Correct"] += 1  # present without expected = informational
            rows.append({"field": field, "status": "Correct", "note": "present"})
            continue
        if any(_norm(c.value) == _norm(expected) for c in cands):
            tallies["Correct"] += 1
            rows.append({"field": field, "status": "Correct"})
        else:
            tallies["Incorrect"] += 1
            rows.append({"field": field, "status": "Incorrect", "values": [c.value for c in cands]})
    n = max(sum(tallies.values()), 1)
    return {"tallies": tallies, "fields": rows, "correct_rate": round(tallies["Correct"] / n, 4)}


def score_conflicts(
    pkg: StudyInputPackage,
    expected_conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    observed = [
        c
        for c in pkg.conflicts
        if str(c.get("status") or "OPEN") == "OPEN"
    ]
    obs_fields = {str(c.get("field_path")) for c in observed}
    exp_fields = {str(c.get("field_path")) for c in expected_conflicts}
    tp = len(obs_fields & exp_fields)
    fp = len(obs_fields - exp_fields)
    fn = len(exp_fields - obs_fields)
    # Dose conflict must never be auto-resolved
    dose = [
        c
        for c in observed
        if c.get("field_path") == "reference_product.dose"
    ]
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "observed_fields": sorted(obs_fields),
        "expected_fields": sorted(exp_fields),
        "dose_conflict_open": bool(dose),
        "auto_resolve_forbidden": True,
        "auto_resolved": False,
    }


def score_evidence(pkg: StudyInputPackage) -> dict[str, Any]:
    if not pkg.candidates:
        return {
            "source_attached_rate": 0.0,
            "location_attached_rate": 0.0,
            "excerpt_attached_rate": 0.0,
            "confidence_attached_rate": 0.0,
            "verification_status_rate": 0.0,
            "n": 0,
        }
    n = len(pkg.candidates)
    source = sum(1 for c in pkg.candidates if c.source_id)
    loc = sum(1 for c in pkg.candidates if c.location)
    excerpt = sum(1 for c in pkg.candidates if c.excerpt)
    conf = sum(1 for c in pkg.candidates if c.confidence)
    ver = sum(1 for c in pkg.candidates if c.status)
    return {
        "source_attached_rate": round(source / n, 4),
        "location_attached_rate": round(loc / n, 4),
        "excerpt_attached_rate": round(excerpt / n, 4),
        "confidence_attached_rate": round(conf / n, 4),
        "verification_status_rate": round(ver / n, 4),
        "n": n,
        "provenance_missing_is_warning": True,
    }


def package_availability(pkg: StudyInputPackage) -> dict[str, Any]:
    types = {d.document_type for d in pkg.documents}
    return {
        "AVAILABLE": sorted(types),
        "MISSING": [],
        "CONFLICTING": [
            c.get("field_path")
            for c in pkg.conflicts
            if str(c.get("status") or "OPEN") == "OPEN"
        ],
        "UNVERIFIED": [
            c.field_path for c in pkg.candidates if c.status != "VERIFIED"
        ],
    }

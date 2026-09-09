"""Golden semantic comparison — Phase 14.

Compare structured values, not raw DOCX text.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


COMPARISON_STATES = ("MATCH", "MISMATCH", "MISSING", "NOT_COMPARABLE")


@dataclass
class FieldComparison:
    field_path: str
    expected: Any
    actual: Any
    state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GoldenSemanticReport:
    fixture_id: str
    comparisons: list[FieldComparison] = field(default_factory=list)
    match_count: int = 0
    mismatch_count: int = 0
    missing_count: int = 0
    conflict_ok: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "comparisons": [c.to_dict() for c in self.comparisons],
            "match_count": self.match_count,
            "mismatch_count": self.mismatch_count,
            "missing_count": self.missing_count,
            "conflict_ok": self.conflict_ok,
            "notes": self.notes,
        }


def _norm(v: Any) -> str:
    if isinstance(v, list):
        return "|".join(_norm(x) for x in v)
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return ""
    s = str(v).strip().lower().replace("мг", "mg").replace("ё", "е")
    return " ".join(s.split())


# Expected semantic facts from UPDCB-02-BE-2026 writer package (not medical rules)
UPDCB_SEMANTIC_EXPECTATIONS: dict[str, Any] = {
    "study.protocol_number": "UPDCB-02-BE-2026",
    "sponsor.name": 'ООО «ПРОМОМЕД РУС»',
    "test_product.dose": "15 mg",
    "design.randomized": True,
    "design.open_label": True,
    "design.crossover": True,
    "design.periods": 2,
    "design.sequences": 2,
    "design.groups": 4,
    "subjects.sex": "male",
    "subjects.age_min": 18,
    "subjects.age_max": 45,
    "subjects.screened_n": 62,
    "subjects.randomized_n": 56,
    "subjects.group_allocation": "1:1:1:1",
    "washout.duration": 7,
    "sampling.total_points": 19,
    "bioanalysis.analyte": "upadacitinib",
    "bioanalysis.method": "LC-MS/MS",
    "statistics.method": "ANOVA",
    "statistics.transformation": "log",
    "statistics.confidence_interval": "90%",
    "statistics.acceptance_interval": "80.00-125.00%",
}


DESIGN_ONLY_EXPECTATIONS: dict[str, Any] = {
    "design.randomized": True,
    "design.open_label": True,
    "design.crossover": True,
    "design.periods": 2,
    "design.sequences": 2,
    "design.groups": 4,
    "subjects.sex": "male",
    "subjects.age_min": 18,
    "subjects.age_max": 45,
    "subjects.screened_n": 62,
    "subjects.randomized_n": 56,
    "subjects.group_allocation": "1:1:1:1",
}


def compare_semantic(
    *,
    fixture_id: str,
    actual_by_path: dict[str, Any],
    expectations: dict[str, Any],
    conflict_field: str | None = "reference_product.dose",
    conflict_values: set[str] | None = None,
) -> GoldenSemanticReport:
    report = GoldenSemanticReport(fixture_id=fixture_id)
    for path, expected in expectations.items():
        actual = actual_by_path.get(path)
        if actual is None:
            state = "MISSING"
            report.missing_count += 1
        elif _norm(actual) == _norm(expected):
            state = "MATCH"
            report.match_count += 1
        else:
            # Soft match for sponsor containing name
            if path == "sponsor.name" and _norm(expected) in _norm(actual):
                state = "MATCH"
                report.match_count += 1
            else:
                state = "MISMATCH"
                report.mismatch_count += 1
        assert state in COMPARISON_STATES
        report.comparisons.append(FieldComparison(path, expected, actual, state))

    if conflict_field and conflict_values:
        # Conflict detection expectation: both doses present among candidates
        present = {_norm(v) for v in (actual_by_path.get(f"{conflict_field}__all") or [])}
        needed = {_norm(v) for v in conflict_values}
        report.conflict_ok = needed.issubset(present) and len(needed) > 1
        report.notes = f"conflict_field={conflict_field} values={sorted(needed)} present={sorted(present)}"
    return report

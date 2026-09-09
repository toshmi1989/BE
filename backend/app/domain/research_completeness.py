"""Research completeness score — informational, not regulatory readiness."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


REQUIRED_TASK_TYPES = (
    "REFERENCE_PRODUCT",
    "PRODUCT_LABEL",
    "PK",
    "BIOEQUIVALENCE_STUDIES",
    "CV",
    "FOOD_CONDITION",
)


@dataclass
class CompletenessResult:
    required_tasks: list[str]
    completed_tasks: list[str]
    blocked_tasks: list[str]
    missing_evidence: list[str]
    conflicts: int
    open_tasks: list[str]
    score: float
    notes: str = "Informational completeness — not regulatory readiness"
    version: str = "RESEARCH.COMPLETENESS.v1"

    def to_dict(self) -> dict:
        return asdict(self)


def calculate_research_completeness(
    *,
    tasks: list[dict],
    evidence_field_codes: list[str],
    unresolved_conflicts: int,
) -> CompletenessResult:
    task_by_type = {t["task_type"]: t for t in tasks}
    required = list(REQUIRED_TASK_TYPES)
    completed: list[str] = []
    blocked: list[str] = []
    open_tasks: list[str] = []
    for ttype in required:
        t = task_by_type.get(ttype)
        if t is None:
            open_tasks.append(ttype)
            continue
        status = t.get("status")
        if status == "DONE":
            completed.append(ttype)
        elif status == "BLOCKED":
            blocked.append(ttype)
        else:
            open_tasks.append(ttype)

    needed_fields = ["reference_product", "tmax", "half_life", "cv_cmax", "food_condition"]
    have = set(evidence_field_codes)
    missing = [f for f in needed_fields if f not in have]

    # score: 50% tasks done, 40% evidence fields, 10% no conflicts
    task_score = (len(completed) / len(required)) * 50.0 if required else 0.0
    ev_score = ((len(needed_fields) - len(missing)) / len(needed_fields)) * 40.0
    conflict_score = 10.0 if unresolved_conflicts == 0 else max(0.0, 10.0 - unresolved_conflicts * 3.0)
    score = round(task_score + ev_score + conflict_score, 1)

    return CompletenessResult(
        required_tasks=required,
        completed_tasks=completed,
        blocked_tasks=blocked,
        missing_evidence=missing,
        conflicts=unresolved_conflicts,
        open_tasks=open_tasks,
        score=score,
    )

"""Canonical subject-count resolution — SubjectPlan is the single source of truth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CanonicalSubjectCounts:
    evaluable_n: int | None
    randomized_n: int | None
    screened_n: int | None
    reserve_n: int | None
    source: str  # subject_plan | sample_size_fallback | missing
    sample_size_evaluable_n: int | None
    sample_size_randomized_n: int | None
    sample_size_screened_n: int | None
    diverges_from_sample_size: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluable_n": self.evaluable_n,
            "randomized_n": self.randomized_n,
            "screened_n": self.screened_n,
            "reserve_n": self.reserve_n,
            "source": self.source,
            "sample_size_evaluable_n": self.sample_size_evaluable_n,
            "sample_size_randomized_n": self.sample_size_randomized_n,
            "sample_size_screened_n": self.sample_size_screened_n,
            "diverges_from_sample_size": self.diverges_from_sample_size,
        }


def get_canonical_subject_counts(ctx: dict) -> CanonicalSubjectCounts:
    """
    SubjectPlan owns protocol N values.

    SampleSizeCalculation stores CALCULATED results; when both are present and
    differ, diverges_from_sample_size=True (validation must ERROR).
    Fallback to sample_size only when SubjectPlan fields are missing.
    """
    subjects = ctx.get("subjects") or {}
    sample_size = ctx.get("sample_size") or {}

    sp_e = subjects.get("target_evaluable_n")
    sp_r = subjects.get("planned_randomized_n")
    sp_s = subjects.get("planned_screened_n")
    sp_res = subjects.get("reserve_n")

    ss_e = sample_size.get("evaluable_n")
    ss_r = sample_size.get("randomized_n")
    ss_s = sample_size.get("screened_n")

    has_sp = any(v is not None for v in (sp_e, sp_r, sp_s))
    has_ss = any(v is not None for v in (ss_e, ss_r, ss_s))

    if has_sp:
        evaluable, randomized, screened = sp_e, sp_r, sp_s
        source = "subject_plan"
    elif has_ss:
        evaluable, randomized, screened = ss_e, ss_r, ss_s
        source = "sample_size_fallback"
    else:
        evaluable = randomized = screened = None
        source = "missing"

    diverges = False
    if has_sp and has_ss:
        for a, b in ((sp_e, ss_e), (sp_r, ss_r), (sp_s, ss_s)):
            if a is not None and b is not None and int(a) != int(b):
                diverges = True
                break

    return CanonicalSubjectCounts(
        evaluable_n=int(evaluable) if evaluable is not None else None,
        randomized_n=int(randomized) if randomized is not None else None,
        screened_n=int(screened) if screened is not None else None,
        reserve_n=int(sp_res) if sp_res is not None else None,
        source=source,
        sample_size_evaluable_n=int(ss_e) if ss_e is not None else None,
        sample_size_randomized_n=int(ss_r) if ss_r is not None else None,
        sample_size_screened_n=int(ss_s) if ss_s is not None else None,
        diverges_from_sample_size=diverges,
    )

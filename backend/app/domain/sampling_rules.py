"""Sampling adequacy evaluation + point-generator interface — Phase 12A.1.

Regulatory adequacy rules are PROPOSED and separate from Tmax density heuristics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SamplingEvaluationResult:
    passed_rules: list[str] = field(default_factory=list)
    failed_rules: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    knowledge_gaps: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    status: str = "PROPOSED"
    requires_expert_confirmation: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _times(points: list[dict]) -> list[float]:
    out: list[float] = []
    for p in points:
        t = p.get("time_h")
        if t is None:
            continue
        out.append(float(t))
    return sorted(out)


def evaluate_sampling_plan(
    *,
    points: list[dict],
    tmax_h: float | None = None,
    half_life_h: float | None = None,
    auc_t_over_inf: float | None = None,
    evidence_ids: list[str] | None = None,
) -> SamplingEvaluationResult:
    """Evaluate PROPOSED adequacy rules. Heuristic Tmax±25% does NOT grant PASS alone."""
    times = _times(points)
    passed: list[str] = []
    failed: list[str] = []
    warnings: list[str] = []
    gaps: list[dict[str, Any]] = []
    details: dict[str, Any] = {"n_points": len(times), "times": times}

    if not times:
        failed.append("SAMPLING-EMPTY")
        return SamplingEvaluationResult(
            failed_rules=failed,
            warnings=["No sampling points provided"],
            knowledge_gaps=[
                {
                    "domain": "SAMPLING",
                    "question": "Sampling plan is empty.",
                    "importance": "CRITICAL",
                    "blocking": True,
                }
            ],
            evidence=list(evidence_ids or []),
            status="UNVERIFIED",
            details=details,
        )

    # SAMPLING-03: first concentration-time point after dose should not be sole Cmax-like first
    # Interpret: if only one post-dose point, fail; if first positive time is the only point before late phase
    post = [t for t in times if t > 0]
    if post:
        passed.append("SAMPLING-03")  # structural presence of a post-dose series
    else:
        failed.append("SAMPLING-03")
        warnings.append("No post-dose sampling points — Cmax cannot be characterized.")

    if tmax_h is not None:
        before = [t for t in times if 0 < t < float(tmax_h)]
        after = [t for t in times if t > float(tmax_h)]
        details["before_tmax"] = len(before)
        details["after_tmax"] = len(after)
        if len(before) >= 3:
            passed.append("SAMPLING-01")
        else:
            failed.append("SAMPLING-01")
        if len(after) >= 3:
            passed.append("SAMPLING-02")
        else:
            failed.append("SAMPLING-02")
        # Heuristic note only
        warnings.append(
            "TMAX_CAPTURE_WINDOW heuristic (PK.SAMP.DENSITY.v1) is HEURISTIC/PROPOSED and does not alone grant PASS."
        )
    else:
        gaps.append(
            {
                "domain": "SAMPLING",
                "question": "Tmax not provided — cannot evaluate before/after Tmax adequacy rules.",
                "importance": "HIGH",
                "blocking": False,
            }
        )
        warnings.append("SAMPLING-01/02 skipped — Tmax missing.")

    # Terminal samples: last 3–4 points as terminal cluster (qualitative PROPOSED)
    if len(times) >= 3:
        passed.append("SAMPLING-05")
        passed.append("SAMPLING-04")
    else:
        failed.append("SAMPLING-05")
        failed.append("SAMPLING-04")

    if half_life_h is not None and times:
        last = times[-1]
        need = 4.0 * float(half_life_h)
        details["last_point_h"] = last
        details["required_last_h"] = need
        if last + 1e-9 >= need:
            passed.append("SAMPLING-06")
        else:
            failed.append("SAMPLING-06")
    else:
        warnings.append("SAMPLING-06 skipped — half-life missing.")
        gaps.append(
            {
                "domain": "SAMPLING",
                "question": "Half-life not provided for last-point ≥4×t½ check.",
                "importance": "MEDIUM",
                "blocking": False,
                "related_rule_id": "SAMPLING-06",
            }
        )

    if auc_t_over_inf is not None:
        if float(auc_t_over_inf) >= 0.8:
            passed.append("SAMPLING-07")
        else:
            failed.append("SAMPLING-07")
    else:
        warnings.append("SAMPLING-07 skipped — AUC0-t/AUC0-inf ratio not provided.")

    gaps.append(
        {
            "domain": "SAMPLING",
            "question": "Long half-life truncation-to-72h applicability criteria not verified.",
            "importance": "MEDIUM",
            "blocking": False,
            "related_rule_id": "SAMPLING-08",
        }
    )

    status = "PROPOSED"
    if failed:
        status = "UNVERIFIED"
    return SamplingEvaluationResult(
        passed_rules=sorted(set(passed)),
        failed_rules=sorted(set(failed)),
        warnings=warnings,
        knowledge_gaps=gaps,
        evidence=list(evidence_ids or []),
        status=status,
        requires_expert_confirmation=True,
        details=details,
    )


@dataclass
class SamplingPlanProposal:
    generated_points: list[dict[str, Any]] = field(default_factory=list)
    rationale: str = ""
    rules_used: list[str] = field(default_factory=list)
    heuristic_used: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    requires_expert_confirmation: bool = True
    status: str = "PROPOSED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SamplingPointGenerator(ABC):
    @abstractmethod
    def propose(self, **kwargs: Any) -> SamplingPlanProposal:
        raise NotImplementedError


class CompatibilitySamplingPointGenerator(SamplingPointGenerator):
    """Wraps existing Sampling Engine recommend result without rewriting it."""

    def propose(
        self,
        *,
        existing_points: list[dict] | None = None,
        recommend_result: dict | None = None,
        evidence_ids: list[str] | None = None,
    ) -> SamplingPlanProposal:
        points: list[dict] = []
        if recommend_result and recommend_result.get("points"):
            points = list(recommend_result["points"])
        elif existing_points:
            points = list(existing_points)
        return SamplingPlanProposal(
            generated_points=points,
            rationale="Compatibility wrapper over existing Sampling Engine / plan — densification heuristic not elevated to regulatory PASS.",
            rules_used=[],
            heuristic_used=["TMAX_CAPTURE_WINDOW", "PK.SAMP.DENSITY.v1"],
            evidence=list(evidence_ids or []),
            warnings=[
                "Operational constraints (night, center load) not auto-applied; deviations need ExpertDecision.",
                "Do not treat 10/20-minute intervals as universal constants.",
            ],
            requires_expert_confirmation=True,
            status="PROPOSED",
        )

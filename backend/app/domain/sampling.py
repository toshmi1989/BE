"""Deterministic sampling recommendation, merge, and validation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.domain.exceptions import ValidationError
from app.domain.pk_rules import RULE_SAMPLING_DENSITY, result_status_for_rules
from app.domain.tmax_capture_window import TmaxCaptureWindow, compute_tmax_capture_window
from app.domain.units import TimeUnit, hours_to_min, to_hours


SAMPLING_REASONS = (
    "BASELINE",
    "ABSORPTION",
    "TMAX_CAPTURE",
    "DISTRIBUTION",
    "TERMINAL_PHASE",
    "FINAL",
)


@dataclass
class AnalyteTmaxWindow:
    analyte_id: str
    name: str
    tmax_min: float
    tmax_max: float
    tmax_unit: str = TimeUnit.H.value


@dataclass
class SamplingPointDraft:
    time_h: float
    reason: str
    window_before_min: float | None = None
    window_after_min: float | None = None
    mandatory: bool = False
    analyte_ids: list[str] = field(default_factory=list)
    origin: str = "RULE_DERIVED"
    status: str = "PROPOSED"


@dataclass
class SamplingRecommendInput:
    analyte_windows: list[AnalyteTmaxWindow]
    observation_duration_h: float | None
    half_life_max_h: float | None = None
    design_type: str | None = None
    target_point_count: int | None = None  # optional soft hint — not a hard law
    clinical_constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class SamplingRecommendResult:
    points: list[SamplingPointDraft]
    rationale: str
    confidence: float | None
    warnings: list[str]
    status: str
    rule_ids: list[str]
    conflicts: list[str] = field(default_factory=list)


def _params() -> dict[str, Any]:
    return dict(RULE_SAMPLING_DENSITY.parameters)


def _round_time(t: float) -> float:
    return round(t * 1000) / 1000.0


def _add_point(
    bucket: dict[float, SamplingPointDraft],
    time_h: float,
    reason: str,
    analyte_ids: list[str],
    *,
    mandatory: bool = False,
    window_before: float | None = None,
    window_after: float | None = None,
) -> None:
    t = _round_time(time_h)
    if t < 0:
        return
    p = _params()
    if t in bucket:
        existing = bucket[t]
        for aid in analyte_ids:
            if aid not in existing.analyte_ids:
                existing.analyte_ids.append(aid)
        # Prefer denser reason hierarchy
        priority = {
            "BASELINE": 0,
            "FINAL": 1,
            "TERMINAL_PHASE": 2,
            "DISTRIBUTION": 3,
            "ABSORPTION": 4,
            "TMAX_CAPTURE": 5,
        }
        if priority.get(reason, 0) > priority.get(existing.reason, 0):
            existing.reason = reason
        existing.mandatory = existing.mandatory or mandatory
        return

    wb = window_before if window_before is not None else float(p["default_window_before_min"])
    wa = window_after if window_after is not None else float(p["default_window_after_min"])
    if reason == "BASELINE":
        wb, wa = 0.0, 0.0
    if reason == "TMAX_CAPTURE":
        wb = float(p["tmax_window_before_min"])
        wa = float(p["tmax_window_after_min"])

    bucket[t] = SamplingPointDraft(
        time_h=t,
        reason=reason,
        window_before_min=wb,
        window_after_min=wa,
        mandatory=mandatory or reason in {"BASELINE", "FINAL"},
        analyte_ids=list(analyte_ids),
        origin="RULE_DERIVED",
        status="PROPOSED",
    )


def merge_sampling_requirements(windows: list[AnalyteTmaxWindow]) -> tuple[float, float, list[str]]:
    """Merge analyte Tmax windows into a combined coverage range."""
    if not windows:
        raise ValidationError("At least one analyte Tmax window required", field="analytes")
    mins = []
    maxs = []
    conflicts: list[str] = []
    for w in windows:
        if w.tmax_min is None or w.tmax_max is None:
            raise ValidationError(f"Tmax range missing for analyte {w.name}", field="tmax")
        if w.tmax_min < 0 or w.tmax_max < 0:
            raise ValidationError("Tmax values must be >= 0", field="tmax")
        tmin = to_hours(w.tmax_min, w.tmax_unit)
        tmax = to_hours(w.tmax_max, w.tmax_unit)
        if tmin > tmax:
            raise ValidationError(f"tmax_min > tmax_max for {w.name}", field="tmax")
        mins.append(tmin)
        maxs.append(tmax)
    combined_min = min(mins)
    combined_max = max(maxs)
    if combined_max - combined_min > 6:
        conflicts.append(
            f"Wide combined Tmax span {combined_min:g}–{combined_max:g} h across analytes"
        )
    return combined_min, combined_max, conflicts


def _capture_window_for(
    tmin: float,
    tmax: float,
    obs_h: float,
    *,
    rule=None,
) -> TmaxCaptureWindow:
    return compute_tmax_capture_window(
        tmin,
        tmax,
        rule=rule or RULE_SAMPLING_DENSITY,
        observation_duration_h=obs_h,
    )


def _generate_for_window(
    bucket: dict[float, SamplingPointDraft],
    tmin: float,
    tmax: float,
    obs_h: float,
    analyte_ids: list[str],
) -> None:
    p = _params()
    min_iv = float(p["min_interval_h"])
    capture = _capture_window_for(tmin, tmax, obs_h)
    win_lo = capture.window_min
    win_hi = capture.window_max
    interval = capture.density_requirement.interval_h

    # Absorption: points before capture window
    absorb_end = max(min_iv, win_lo if win_lo > 0 else min_iv)
    if absorb_end > min_iv:
        n_abs = max(1, int(math.ceil(absorb_end / float(p["absorb_span_factor"]))))
        for i in range(1, n_abs + 1):
            _add_point(bucket, absorb_end * i / (n_abs + 1), "ABSORPTION", analyte_ids)

    # Dense Tmax capture (same window Validation will check)
    t = win_lo
    while t <= win_hi + 1e-9:
        _add_point(bucket, t, "TMAX_CAPTURE", analyte_ids)
        t += interval

    # Post-Tmax distribution with growing intervals
    t = win_hi + float(p["post_interval_start_h"])
    step = float(p["post_interval_start_h"])
    growth = float(p["post_interval_growth"])
    terminal_start = obs_h * float(p["terminal_start_fraction_of_obs"])
    while t < terminal_start and t < obs_h:
        _add_point(bucket, t, "DISTRIBUTION", analyte_ids)
        step = max(min_iv, step * growth)
        t += step

    # Terminal phase
    term_iv = float(p["terminal_interval_h"])
    t = max(terminal_start, win_hi + term_iv)
    while t < obs_h - 1e-9:
        _add_point(bucket, t, "TERMINAL_PHASE", analyte_ids)
        t += term_iv


def generate_sampling_recommendation(inp: SamplingRecommendInput) -> SamplingRecommendResult:
    if inp.observation_duration_h is None or inp.observation_duration_h <= 0:
        raise ValidationError(
            "observation_duration_h required for sampling recommendation",
            field="observation_duration_h",
        )
    if not inp.analyte_windows:
        raise ValidationError("No analyte Tmax windows provided", field="analytes")

    obs_h = float(inp.observation_duration_h)
    combined_min, combined_max, conflicts = merge_sampling_requirements(inp.analyte_windows)
    if combined_max > obs_h:
        raise ValidationError(
            "Tmax window exceeds observation duration",
            field="observation_duration_h",
        )

    bucket: dict[float, SamplingPointDraft] = {}
    all_ids = [w.analyte_id for w in inp.analyte_windows]

    _add_point(bucket, 0.0, "BASELINE", all_ids, mandatory=True, window_before=0, window_after=0)

    # Per-analyte dense coverage then merge into bucket
    for w in inp.analyte_windows:
        tmin = to_hours(w.tmax_min, w.tmax_unit)
        tmax = to_hours(w.tmax_max, w.tmax_unit)
        _generate_for_window(bucket, tmin, tmax, obs_h, [w.analyte_id])

    # Also ensure combined window coverage
    _generate_for_window(bucket, combined_min, combined_max, obs_h, all_ids)

    _add_point(bucket, obs_h, "FINAL", all_ids, mandatory=True)

    points = sorted(bucket.values(), key=lambda p: p.time_h)

    # Optional soft target — thin or warn, never invent a fixed law of N points
    warnings: list[str] = []
    if inp.target_point_count is not None and inp.target_point_count > 0:
        if len(points) > inp.target_point_count * 1.5:
            warnings.append(
                f"Generated {len(points)} points exceeds soft target {inp.target_point_count}"
            )
        elif len(points) < max(5, inp.target_point_count // 2):
            warnings.append(
                f"Generated {len(points)} points below soft target {inp.target_point_count}"
            )

    if conflicts:
        warnings.extend(conflicts)

    rule_ids = [RULE_SAMPLING_DENSITY.rule_id]
    status = result_status_for_rules(rule_ids)
    rationale = (
        f"Combined Tmax coverage {combined_min:g}–{combined_max:g} h over {obs_h:g} h observation; "
        f"{len(points)} points from density rule {RULE_SAMPLING_DENSITY.rule_id} "
        f"(status={RULE_SAMPLING_DENSITY.status})."
    )

    return SamplingRecommendResult(
        points=points,
        rationale=rationale,
        confidence=0.6 if not warnings else 0.45,
        warnings=warnings,
        status=status,
        rule_ids=rule_ids,
        conflicts=conflicts,
    )


@dataclass
class SamplingValidationIssue:
    severity: str
    code: str
    message: str
    field: str | None = None


def validate_sampling_plan(
    points: list[dict[str, Any]],
    *,
    observation_duration_h: float | None,
    analyte_windows: list[AnalyteTmaxWindow] | None = None,
    design_type: str | None = None,
    manual_override: bool = False,
) -> list[SamplingValidationIssue]:
    issues: list[SamplingValidationIssue] = []
    if not points:
        issues.append(
            SamplingValidationIssue("CRITICAL", "NO_POINTS", "Sampling plan has no points", "points")
        )
        return issues

    times = [float(p["time_h"]) for p in points]
    if any(t < 0 for t in times):
        issues.append(
            SamplingValidationIssue("CRITICAL", "NEGATIVE_TIME", "Negative sampling time", "time_h")
        )

    if times != sorted(times):
        issues.append(
            SamplingValidationIssue("ERROR", "UNSORTED", "Points are not sorted by time", "points")
        )

    if len(times) != len(set(_round_time(t) for t in times)):
        issues.append(
            SamplingValidationIssue("ERROR", "DUPLICATE_TIME", "Duplicate sampling times", "time_h")
        )

    if not any(abs(t) < 1e-9 for t in times):
        issues.append(
            SamplingValidationIssue("CRITICAL", "MISSING_BASELINE", "Baseline (t=0) required", "points")
        )

    if observation_duration_h is not None:
        if max(times) - observation_duration_h > 1e-6:
            issues.append(
                SamplingValidationIssue(
                    "CRITICAL",
                    "FINAL_EXCEEDS_OBS",
                    "Final point exceeds observation duration",
                    "time_h",
                )
            )
        if abs(max(times) - observation_duration_h) > 1e-3:
            sev = "WARNING" if manual_override else "ERROR"
            issues.append(
                SamplingValidationIssue(
                    sev,
                    "FINAL_MISMATCH",
                    "Final point does not match selected observation duration",
                    "time_h",
                )
            )

    if analyte_windows:
        for w in analyte_windows:
            tmin = to_hours(w.tmax_min, w.tmax_unit)
            tmax = to_hours(w.tmax_max, w.tmax_unit)
            capture = compute_tmax_capture_window(
                tmin,
                tmax,
                rule=RULE_SAMPLING_DENSITY,
                observation_duration_h=observation_duration_h,
            )
            # Pre/post relative to declared Tmax bounds; coverage uses canonical capture window
            before = [t for t in times if 0 < t < tmin - 1e-9]
            after = [t for t in times if t > tmax + 1e-9]
            if not before:
                issues.append(
                    SamplingValidationIssue(
                        "ERROR",
                        "NO_PRE_TMAX",
                        f"No points before Tmax for {w.name}",
                        "points",
                    )
                )
            if not capture.meets_density(times):
                issues.append(
                    SamplingValidationIssue(
                        "ERROR",
                        "INSUFFICIENT_TMAX_COVERAGE",
                        f"Insufficient Tmax coverage for {w.name}",
                        "points",
                    )
                )
            if not after:
                issues.append(
                    SamplingValidationIssue(
                        "ERROR",
                        "NO_POST_TMAX",
                        f"No points after Tmax for {w.name}",
                        "points",
                    )
                )

        # Terminal coverage: at least one point in last 40% of observation
        if observation_duration_h and observation_duration_h > 0:
            terminal_cut = observation_duration_h * 0.6
            if not any(t >= terminal_cut for t in times if t < observation_duration_h - 1e-9):
                issues.append(
                    SamplingValidationIssue(
                        "WARNING",
                        "WEAK_TERMINAL",
                        "Few/no terminal-phase points before final",
                        "points",
                    )
                )

    if design_type == "PARALLEL" and any(
        str(p.get("reason")) == "WASHOUT" for p in points
    ):
        issues.append(
            SamplingValidationIssue(
                "INFO",
                "PARALLEL_NOTE",
                "Parallel design typically has a single period sampling schedule",
                "design",
            )
        )

    return issues


def point_time_min(time_h: float) -> float:
    return hours_to_min(time_h)

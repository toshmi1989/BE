"""Canonical Tmax capture window — shared by Sampling and Validation.

Margins and density come from the applied sampling DomainRule (default
PK.SAMP.DENSITY.v1). Rule status remains PROPOSED until a verified
regulatory source is attached; fractions are not VERIFIED norms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.exceptions import ValidationError
from app.domain.pk_rules import RULE_SAMPLING_DENSITY, DomainRule


@dataclass(frozen=True)
class TmaxCaptureDensityRequirement:
    """Minimum density expected inside the capture window."""

    min_points_in_window: int
    min_interval_h: float
    interval_h: float
    pre_margin_fraction: float
    post_margin_fraction: float
    interval_fraction: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "min_points_in_window": self.min_points_in_window,
            "min_interval_h": self.min_interval_h,
            "interval_h": self.interval_h,
            "pre_margin_fraction": self.pre_margin_fraction,
            "post_margin_fraction": self.post_margin_fraction,
            "interval_fraction": self.interval_fraction,
        }


@dataclass(frozen=True)
class TmaxCaptureWindow:
    """Reusable capture window for one Tmax range under a sampling density rule."""

    tmax_min_h: float
    tmax_max_h: float
    window_min: float
    window_max: float
    density_requirement: TmaxCaptureDensityRequirement
    rule_id: str
    rule_version: str
    rationale: str
    status: str

    def contains(self, time_h: float, *, eps: float = 1e-6) -> bool:
        return self.window_min - eps <= time_h <= self.window_max + eps

    def points_in_window(self, times: list[float], *, eps: float = 1e-6) -> list[float]:
        return [t for t in times if self.contains(t, eps=eps)]

    def meets_density(self, times: list[float], *, eps: float = 1e-6) -> bool:
        return len(self.points_in_window(times, eps=eps)) >= self.density_requirement.min_points_in_window


def resolve_sampling_density_rule(rule: DomainRule | str | None = None) -> DomainRule:
    if rule is None:
        return RULE_SAMPLING_DENSITY
    if isinstance(rule, DomainRule):
        return rule
    from app.domain.pk_rules import get_rule

    return get_rule(str(rule))


def compute_tmax_capture_window(
    tmax_min_h: float,
    tmax_max_h: float,
    *,
    rule: DomainRule | str | None = None,
    observation_duration_h: float | None = None,
) -> TmaxCaptureWindow:
    """Compute the canonical Tmax capture window used by Sampling and Validation."""
    applied = resolve_sampling_density_rule(rule)
    params = applied.parameters
    if tmax_min_h is None or tmax_max_h is None:
        raise ValidationError("Tmax range required for capture window", field="tmax")
    tmin = float(tmax_min_h)
    tmax = float(tmax_max_h)
    if tmin < 0 or tmax < 0:
        raise ValidationError("Tmax values must be >= 0", field="tmax")
    if tmin > tmax:
        raise ValidationError("tmax_min > tmax_max", field="tmax")

    pre_m = float(params["tmax_pre_margin_fraction"])
    post_m = float(params["tmax_post_margin_fraction"])
    iv_frac = float(params["tmax_interval_fraction"])
    min_iv = float(params["min_interval_h"])
    min_points = int(params.get("min_points_in_capture_window", 2))

    win_lo = max(0.0, tmin * (1 - pre_m) if tmin > 0 else 0.0)
    win_hi = tmax * (1 + post_m)
    if observation_duration_h is not None:
        win_hi = min(win_hi, float(observation_duration_h))
    if win_hi < win_lo:
        raise ValidationError(
            "Capture window collapses under observation duration",
            field="observation_duration_h",
        )

    span = max(min_iv, win_hi - win_lo)
    interval = max(min_iv, span * iv_frac)
    density = TmaxCaptureDensityRequirement(
        min_points_in_window=min_points,
        min_interval_h=min_iv,
        interval_h=interval,
        pre_margin_fraction=pre_m,
        post_margin_fraction=post_m,
        interval_fraction=iv_frac,
    )
    rationale = (
        f"Tmax declared {tmin:g}–{tmax:g} h → capture window {win_lo:g}–{win_hi:g} h "
        f"via {applied.rule_id} (pre={pre_m:g}, post={post_m:g}; status={applied.status}). "
        f"Margins are algorithmic / PROPOSED — not a verified regulatory norm."
    )
    return TmaxCaptureWindow(
        tmax_min_h=tmin,
        tmax_max_h=tmax,
        window_min=win_lo,
        window_max=win_hi,
        density_requirement=density,
        rule_id=applied.rule_id,
        rule_version=applied.version,
        rationale=rationale,
        status=applied.status,
    )


def compute_merged_tmax_capture_window(
    ranges_h: list[tuple[float, float]],
    *,
    rule: DomainRule | str | None = None,
    observation_duration_h: float | None = None,
) -> TmaxCaptureWindow:
    """Capture window for the union of analyte Tmax ranges (min of mins, max of maxes)."""
    if not ranges_h:
        raise ValidationError("At least one Tmax range required", field="tmax")
    combined_min = min(r[0] for r in ranges_h)
    combined_max = max(r[1] for r in ranges_h)
    return compute_tmax_capture_window(
        combined_min,
        combined_max,
        rule=rule,
        observation_duration_h=observation_duration_h,
    )

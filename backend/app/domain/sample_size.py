"""Sample size calculators separated by design family."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.domain.exceptions import ValidationError
from app.domain.stats_rules import ROUNDING_2X2, SAMPLE_SIZE_ALGORITHM_2X2
from app.domain.subject_reserve import ReserveInput, apply_subject_reserve
from app.domain.t_dist import nct_sf as pure_nct_sf
from app.domain.t_dist import student_t_ppf as pure_t_ppf

try:
    from scipy import __version__ as SCIPY_VERSION
    from scipy.stats import nct, t

    def _t_ppf(p: float, df: float) -> float:
        return float(t.ppf(p, df))

    def _nct_sf(x: float, df: float, ncp: float) -> float:
        return float(nct.sf(x, df, ncp))

    SOFTWARE_LABEL = f"scipy=={SCIPY_VERSION}"
except ImportError:  # pragma: no cover
    SCIPY_VERSION = None
    SOFTWARE_LABEL = "pure-python-t_dist.v1"

    def _t_ppf(p: float, df: float) -> float:
        return pure_t_ppf(p, df)

    def _nct_sf(x: float, df: float, ncp: float) -> float:
        return pure_nct_sf(x, df, ncp)


@dataclass
class SampleSizeInput:
    design_type: str
    selected_cv_percent: float
    expected_ratio: float
    alpha: float
    power: float
    be_lower: float
    be_upper: float
    parameter: str | None = None
    analyte_id: str | None = None
    dropout_pct: float = 0.0
    reserve_pct: float = 0.0
    screen_failure_pct: float = 0.0


@dataclass
class SampleSizeResult:
    evaluable_n: int | None
    randomized_n: int | None
    screened_n: int | None
    method: str
    formula: str
    software_version: str | None
    algorithm_version: str
    status: str
    warnings: list[str] = field(default_factory=list)
    inputs_snapshot: dict = field(default_factory=dict)
    achieved_power: float | None = None
    raw_n_before_rounding: float | None = None


class SampleSizeCalculator(ABC):
    method_id: str
    algorithm_version: str

    @abstractmethod
    def calculate(self, inp: SampleSizeInput) -> SampleSizeResult:
        raise NotImplementedError


def _validate_common(inp: SampleSizeInput) -> None:
    if inp.selected_cv_percent <= 0:
        raise ValidationError("selected_cv must be > 0", field="selected_cv")
    if not (0 < inp.alpha < 0.5):
        raise ValidationError("alpha must be in (0, 0.5)", field="alpha")
    if not (0.5 < inp.power < 1.0):
        raise ValidationError("power must be in (0.5, 1)", field="power")
    if inp.be_lower <= 0 or inp.be_upper <= 0 or inp.be_lower >= inp.be_upper:
        raise ValidationError("invalid BE limits", field="be_lower")
    if inp.expected_ratio <= 0:
        raise ValidationError("expected_ratio must be > 0", field="expected_ratio")


def be_power_2x2_nct(
    n_total: int,
    cv_percent: float,
    ratio: float,
    alpha: float,
    be_lower: float,
    be_upper: float,
) -> float:
    """TOST power via non-central t (independent bounds).

    Var(μ̂T−μ̂R) = 2 σ_w² / n for balanced 2×2; σ_w² = ln(1+CV²).
    Algorithm: BE_TOST_2X2_NCT.v1
    """
    if n_total < 4 or n_total % 2 != 0:
        return 0.0
    cv = cv_percent / 100.0
    sigma = math.sqrt(math.log(1.0 + cv * cv))
    se = sigma * math.sqrt(2.0 / n_total)
    df = float(n_total - 2)
    tcrit = _t_ppf(1.0 - alpha, df)
    ncp_l = (math.log(ratio) - math.log(be_lower)) / se
    ncp_u = (math.log(be_upper) - math.log(ratio)) / se
    p1 = _nct_sf(tcrit, df, ncp_l)
    p2 = _nct_sf(tcrit, df, ncp_u)
    return max(0.0, min(1.0, p1 + p2 - 1.0))


class Crossover2x2SampleSizeCalculator(SampleSizeCalculator):
    method_id = "CROSSOVER_2X2_TOST_NCT"
    algorithm_version = SAMPLE_SIZE_ALGORITHM_2X2

    def calculate(self, inp: SampleSizeInput) -> SampleSizeResult:
        _validate_common(inp)
        if inp.design_type != "CROSSOVER_2X2":
            raise ValidationError("This calculator is only for CROSSOVER_2X2", field="design_type")

        warnings: list[str] = []
        if SCIPY_VERSION is None:
            warnings.append("scipy unavailable — using pure-python t_dist fallback")
        if inp.expected_ratio < inp.be_lower or inp.expected_ratio > inp.be_upper:
            warnings.append("expected_ratio outside BE limits — power may be near zero")

        snapshot = {
            "design_type": inp.design_type,
            "selected_cv_percent": inp.selected_cv_percent,
            "expected_ratio": inp.expected_ratio,
            "alpha": inp.alpha,
            "power": inp.power,
            "be_lower": inp.be_lower,
            "be_upper": inp.be_upper,
            "parameter": inp.parameter,
            "analyte_id": inp.analyte_id,
            "dropout_pct": inp.dropout_pct,
            "reserve_pct": inp.reserve_pct,
            "screen_failure_pct": inp.screen_failure_pct,
            "algorithm_version": self.algorithm_version,
            "software": SOFTWARE_LABEL,
        }

        target = inp.power
        chosen_n = None
        achieved = None
        for n in range(4, 502, 2):
            pow_n = be_power_2x2_nct(
                n,
                inp.selected_cv_percent,
                inp.expected_ratio,
                inp.alpha,
                inp.be_lower,
                inp.be_upper,
            )
            if pow_n >= target - 1e-12:
                chosen_n = n
                achieved = pow_n
                break
        if chosen_n is None:
            return SampleSizeResult(
                evaluable_n=None,
                randomized_n=None,
                screened_n=None,
                method=self.method_id,
                formula="iterate even n until TOST nct power >= target",
                software_version=SOFTWARE_LABEL,
                algorithm_version=self.algorithm_version,
                status="NEEDS_REVIEW",
                warnings=warnings + ["No n<=500 satisfies target power"],
                inputs_snapshot=snapshot,
            )

        evaluable = ROUNDING_2X2.round_n(float(chosen_n))
        reserve = apply_subject_reserve(
            ReserveInput(
                evaluable_n=evaluable,
                dropout_pct=inp.dropout_pct,
                reserve_pct=inp.reserve_pct,
                screen_failure_pct=inp.screen_failure_pct,
                rounding=ROUNDING_2X2,
            )
        )
        return SampleSizeResult(
            evaluable_n=evaluable,
            randomized_n=reserve.randomized_n,
            screened_n=reserve.screened_n,
            method=self.method_id,
            formula=(
                "σ²=ln(1+CV²); SE=σ√(2/n); df=n-2; "
                "power≈nct.sf(t_{1-α},df,ncp_L)+nct.sf(t_{1-α},df,ncp_U)-1; "
                + reserve.formula
            ),
            software_version=SOFTWARE_LABEL,
            algorithm_version=self.algorithm_version,
            status="PROPOSED",
            warnings=warnings,
            inputs_snapshot=snapshot,
            achieved_power=achieved,
            raw_n_before_rounding=float(chosen_n),
        )


class ReplicateSampleSizeCalculator(SampleSizeCalculator):
    method_id = "REPLICATE_SAMPLE_SIZE"
    algorithm_version = "NOT_IMPLEMENTED.v0"

    def calculate(self, inp: SampleSizeInput) -> SampleSizeResult:
        return SampleSizeResult(
            evaluable_n=None,
            randomized_n=None,
            screened_n=None,
            method=self.method_id,
            formula="stub — verified replicate method not approved",
            software_version=None,
            algorithm_version=self.algorithm_version,
            status="NOT_IMPLEMENTED",
            warnings=["Replicate sample-size calculator pending verified method"],
            inputs_snapshot={"design_type": inp.design_type},
        )


class ParallelSampleSizeCalculator(SampleSizeCalculator):
    method_id = "PARALLEL_SAMPLE_SIZE"
    algorithm_version = "NOT_IMPLEMENTED.v0"

    def calculate(self, inp: SampleSizeInput) -> SampleSizeResult:
        if inp.design_type == "CROSSOVER_2X2":
            raise ValidationError("Do not use parallel calculator for crossover", field="design_type")
        return SampleSizeResult(
            evaluable_n=None,
            randomized_n=None,
            screened_n=None,
            method=self.method_id,
            formula="stub — crossover formula must not be applied to parallel",
            software_version=None,
            algorithm_version=self.algorithm_version,
            status="NOT_IMPLEMENTED",
            warnings=["Parallel sample-size calculator pending verified method"],
            inputs_snapshot={"design_type": inp.design_type},
        )


class AdaptiveSampleSizeCalculator(SampleSizeCalculator):
    method_id = "ADAPTIVE_SAMPLE_SIZE"
    algorithm_version = "DOMAIN_ONLY.v0"

    def calculate(self, inp: SampleSizeInput) -> SampleSizeResult:
        return SampleSizeResult(
            evaluable_n=None,
            randomized_n=None,
            screened_n=None,
            method=self.method_id,
            formula="domain representation only: stage_1_n / interim / stage_2 / max_n",
            software_version=None,
            algorithm_version=self.algorithm_version,
            status="NEEDS_REVIEW",
            warnings=["Adaptive calculation requires expert method — not auto-computed"],
            inputs_snapshot={
                "design_type": inp.design_type,
                "stage_1_n": None,
                "interim_analysis": None,
                "decision_rule": None,
                "stage_2_n": None,
                "max_n": None,
            },
        )


def calculate_sample_size(inp: SampleSizeInput) -> SampleSizeResult:
    mapping: dict[str, SampleSizeCalculator] = {
        "CROSSOVER_2X2": Crossover2x2SampleSizeCalculator(),
        "REPLICATE_2X2X4": ReplicateSampleSizeCalculator(),
        "PARALLEL": ParallelSampleSizeCalculator(),
        "ADAPTIVE": AdaptiveSampleSizeCalculator(),
    }
    calc = mapping.get(inp.design_type)
    if calc is None:
        raise ValidationError(
            f"No sample-size calculator for design {inp.design_type}",
            field="design_type",
        )
    return calc.calculate(inp)

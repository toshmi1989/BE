"""CV pooling — pluggable methods; no silent pooling of incompatible studies."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.domain.cv_validation import (
    CVStudyData,
    check_cv_compatibility,
    normalize_cv_to_percent,
)
from app.domain.exceptions import ValidationError
from app.domain.stats_rules import POOLING_ALGORITHM_IVW


@dataclass
class CVPoolingInput:
    studies: list[CVStudyData]


@dataclass
class CVPoolingResult:
    pooled_cv: float | None
    confidence_interval: tuple[float, float] | None
    inputs: list[dict]
    method: str
    algorithm_version: str
    status: str
    warnings: list[str] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)


class CVPoolingMethod(ABC):
    method_id: str
    algorithm_version: str

    @abstractmethod
    def pool(self, studies: list[CVStudyData]) -> CVPoolingResult:
        raise NotImplementedError


class InverseVarianceLogCVPooling(CVPoolingMethod):
    """Pool on log-variance scale weighted by (n_be - 1) or (n_total - 1).

    σ² = ln(1 + CV_frac²); pooled σ² = Σ w_i σ_i² / Σ w_i; CV = sqrt(exp(σ²)-1)*100
    Method status is PROPOSED until a verified regulatory/statistics source is attached.
    """

    method_id = "INVERSE_VARIANCE_WEIGHTED_LOG_CV"
    algorithm_version = POOLING_ALGORITHM_IVW

    def pool(self, studies: list[CVStudyData]) -> CVPoolingResult:
        if not studies:
            raise ValidationError("No CV studies to pool", field="studies")

        compat = check_cv_compatibility(studies)
        inputs = [
            {
                "parameter": s.parameter,
                "analyte_id": s.analyte_id,
                "cv_value": s.cv_value,
                "cv_unit": s.cv_unit,
                "n_total": s.n_total,
                "n_be_analysis": s.n_be_analysis,
                "design": s.design,
                "condition": s.condition,
                "cv_type": s.cv_type,
                "source_id": s.source_id,
            }
            for s in studies
        ]
        if not compat.compatible:
            return CVPoolingResult(
                pooled_cv=None,
                confidence_interval=None,
                inputs=inputs,
                method=self.method_id,
                algorithm_version=self.algorithm_version,
                status="NEEDS_REVIEW",
                warnings=compat.warnings
                + ["Incompatible CV studies — pooling blocked (no silent pool)"],
                mismatches=compat.mismatches,
            )

        num = 0.0
        den = 0.0
        for s in studies:
            cv_pct = normalize_cv_to_percent(s.cv_value, s.cv_unit)
            cv_frac = cv_pct / 100.0
            sigma2 = math.log(1.0 + cv_frac * cv_frac)
            n = s.n_be_analysis if s.n_be_analysis is not None else s.n_total
            if n is None or n < 2:
                raise ValidationError(
                    "Each CV study needs n_be_analysis or n_total >= 2 for pooling weights",
                    field="n_be_analysis",
                )
            w = float(n - 1)
            num += w * sigma2
            den += w
        pooled_sigma2 = num / den
        pooled_cv = math.sqrt(math.exp(pooled_sigma2) - 1.0) * 100.0

        # Approximate Wald CI on sigma2 → CV (informative, not a verified CI method)
        # Keep CI None if too few df — honest about method limits
        ci = None
        warnings = list(compat.warnings)
        if den < 3:
            warnings.append("Few degrees of freedom for pooled CV; CI not reported")

        return CVPoolingResult(
            pooled_cv=pooled_cv,
            confidence_interval=ci,
            inputs=inputs,
            method=self.method_id,
            algorithm_version=self.algorithm_version,
            status="PROPOSED",
            warnings=warnings,
            mismatches=[],
        )


DEFAULT_POOLING_METHODS: dict[str, CVPoolingMethod] = {
    InverseVarianceLogCVPooling.method_id: InverseVarianceLogCVPooling(),
}


def pool_cv(
    studies: list[CVStudyData], method_id: str = InverseVarianceLogCVPooling.method_id
) -> CVPoolingResult:
    method = DEFAULT_POOLING_METHODS.get(method_id)
    if method is None:
        raise ValidationError(f"Unknown pooling method: {method_id}", field="method")
    return method.pool(studies)

"""BioanalysisPlan — technical model + field source classification (Phase 12A).

No template defaults are applied. Empty fields remain UNRESOLVED / EXPERT_REQUIRED.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

FieldSource = Literal[
    "SOURCE_DERIVED",
    "USER",
    "STATIC_VERIFIED",
    "EXPERT_REQUIRED",
    "UNRESOLVED",
]

# Default classification per field — expert interview may override later.
BIOANALYSIS_FIELD_CLASSIFICATION: dict[str, FieldSource] = {
    "matrix": "EXPERT_REQUIRED",
    "tube_type": "EXPERT_REQUIRED",
    "anticoagulant": "EXPERT_REQUIRED",
    "sample_volume_ml": "EXPERT_REQUIRED",
    "centrifugation": "EXPERT_REQUIRED",
    "centrifugation_temperature": "EXPERT_REQUIRED",
    "centrifugation_time": "EXPERT_REQUIRED",
    "aliquot_count": "EXPERT_REQUIRED",
    "aliquot_volume_ml": "EXPERT_REQUIRED",
    "storage_temperature": "EXPERT_REQUIRED",
    "storage_duration": "EXPERT_REQUIRED",
    "shipment_conditions": "EXPERT_REQUIRED",
    "analytical_method": "EXPERT_REQUIRED",
    "sample_preparation": "EXPERT_REQUIRED",
    "internal_standard": "EXPERT_REQUIRED",
    "calibration_range": "EXPERT_REQUIRED",
    "lloq": "EXPERT_REQUIRED",
    "acceptance_criteria": "EXPERT_REQUIRED",
    "validation_status": "USER",
}


@dataclass
class BioanalysisPlan:
    matrix: str | None = None
    tube_type: str | None = None
    anticoagulant: str | None = None
    sample_volume_ml: float | None = None
    centrifugation: str | None = None
    centrifugation_temperature: str | None = None
    centrifugation_time: str | None = None
    aliquot_count: int | None = None
    aliquot_volume_ml: float | None = None
    storage_temperature: str | None = None
    storage_duration: str | None = None
    shipment_conditions: str | None = None
    analytical_method: str | None = None
    sample_preparation: str | None = None
    internal_standard: str | None = None
    calibration_range: str | None = None
    lloq: str | None = None
    acceptance_criteria: str | None = None
    validation_status: str | None = None
    source_ids: list[str] = field(default_factory=list)
    origin: str = "USER"
    status: str = "MISSING"
    field_sources: dict[str, str] = field(default_factory=dict)
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.field_sources:
            self.field_sources = dict(BIOANALYSIS_FIELD_CLASSIFICATION)

    def classify_fields(self) -> dict[str, str]:
        """Return effective source class per field given current values."""
        out: dict[str, str] = {}
        for key, default_cls in BIOANALYSIS_FIELD_CLASSIFICATION.items():
            val = getattr(self, key, None)
            if val is None or val == "":
                # Prefer declared EXPERT_REQUIRED over bare UNRESOLVED when expert needed
                out[key] = default_cls if default_cls != "USER" else "UNRESOLVED"
            else:
                # Value present: keep USER/SOURCE_DERIVED from field_sources override or USER
                out[key] = self.field_sources.get(key) or "USER"
        return out

    def unresolved_fields(self) -> list[str]:
        return [k for k, v in self.classify_fields().items() if v in {"UNRESOLVED", "EXPERT_REQUIRED"} and getattr(self, k, None) in (None, "")]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["field_classification"] = self.classify_fields()
        d["unresolved_fields"] = self.unresolved_fields()
        return d


def bioanalysis_plan_from_dict(data: dict | None) -> BioanalysisPlan:
    data = data or {}
    known = {f.name for f in BioanalysisPlan.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in data.items() if k in known}
    return BioanalysisPlan(**kwargs)


def empty_bioanalysis_plan() -> BioanalysisPlan:
    """Empty plan — no template defaults."""
    return BioanalysisPlan(
        origin="UNRESOLVED",
        status="MISSING",
        notes="No bioanalysis parameters set; awaiting expert / user input",
    )

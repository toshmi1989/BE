"""Evidence apply bridge — only VERIFIED claims may update study fields."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domain.exceptions import ProvenanceGuardError, ValidationError


@dataclass
class EvidenceClaimData:
    id: str
    field_name: str
    value: Any
    normalized_value: dict | None
    unit: str | None
    confidence: float | None
    status: str
    origin: str | None
    source_ids: list[str]


@dataclass
class ApplyResult:
    applied: list[dict]
    skipped: list[dict]
    warnings: list[str]


ALLOWED_CLAIM_FIELDS = {
    "tmax": ("analyte", "tmax"),
    "tmax_min": ("analyte", "tmax_min"),
    "tmax_max": ("analyte", "tmax_max"),
    "half_life_min": ("analyte", "half_life_min"),
    "half_life_max": ("analyte", "half_life_max"),
    "half_life": ("analyte", "half_life"),
}


def apply_verified_evidence_claims(
    *,
    claims: list[EvidenceClaimData],
    target_status: str | None,
    mutate: Callable[[EvidenceClaimData], None],
) -> ApplyResult:
    """Apply only VERIFIED claims. Refuse to overwrite VERIFIED study fields with non-verified claims.

    `mutate(field_name, claim)` performs the actual ORM update.
    """
    applied: list[dict] = []
    skipped: list[dict] = []
    warnings: list[str] = []

    for claim in claims:
        if claim.status != "VERIFIED":
            skipped.append(
                {
                    "claim_id": claim.id,
                    "field_name": claim.field_name,
                    "reason": "claim_not_verified",
                    "status": claim.status,
                }
            )
            continue
        if claim.field_name not in ALLOWED_CLAIM_FIELDS and not claim.field_name.startswith(
            ("tmax", "half_life")
        ):
            skipped.append(
                {
                    "claim_id": claim.id,
                    "field_name": claim.field_name,
                    "reason": "unsupported_field",
                }
            )
            continue
        if target_status == "VERIFIED" and claim.status != "VERIFIED":
            raise ProvenanceGuardError("Cannot overwrite VERIFIED study field with non-verified claim")
        try:
            mutate(claim)
            applied.append(
                {
                    "claim_id": claim.id,
                    "field_name": claim.field_name,
                    "source_ids": claim.source_ids,
                    "origin": claim.origin or "SOURCE_DERIVED",
                }
            )
        except ValidationError as exc:
            skipped.append(
                {
                    "claim_id": claim.id,
                    "field_name": claim.field_name,
                    "reason": exc.message,
                }
            )
            warnings.append(exc.message)
    return ApplyResult(applied=applied, skipped=skipped, warnings=warnings)

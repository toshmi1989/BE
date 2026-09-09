from __future__ import annotations

from typing import Any

from app.domain.exceptions import ProvenanceGuardError
from app.domain.provenance import FieldStatus, Origin, assert_ai_may_write, normalize_origin
from app.schemas.common import ProvenanceIn, default_provenance_kwargs, provenance_from_orm


def apply_provenance(target: Any, payload: ProvenanceIn | None, *, creating: bool = False) -> None:
    """Apply provenance fields with AI→VERIFIED guard. Domain-only — not used by frontend."""
    if creating and not getattr(target, "status", None):
        for key, value in default_provenance_kwargs().items():
            setattr(target, key, list(value) if key == "source_ids" else value)

    if payload is None:
        if creating:
            for key, value in default_provenance_kwargs().items():
                if getattr(target, key, None) in (None, "", []):
                    setattr(target, key, list(value) if key == "source_ids" else value)
        return

    current_status = getattr(target, "status", FieldStatus.MISSING) or FieldStatus.MISSING
    incoming_origin = normalize_origin(payload.origin) if payload.origin is not None else None

    try:
        assert_ai_may_write(current_status, incoming_origin)
    except ValueError as exc:
        raise ProvenanceGuardError(str(exc)) from exc

    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] is not None:
        data["status"] = FieldStatus(data["status"]).value
    if "origin" in data and data["origin"] is not None:
        data["origin"] = normalize_origin(data["origin"])
    if "source_ids" in data and data["source_ids"] is None:
        data["source_ids"] = []

    for key, value in data.items():
        setattr(target, key, value)

    # Ensure required provenance columns always present after create
    if creating:
        for key, value in default_provenance_kwargs().items():
            if getattr(target, key, None) is None:
                setattr(target, key, list(value) if key == "source_ids" else value)


def bump_entity_version(target: Any) -> None:
    target.entity_version = int(getattr(target, "entity_version", 1) or 1) + 1


def with_provenance(model_cls: type, obj: Any, **extra: Any) -> Any:
    data = {**extra, "provenance": provenance_from_orm(obj)}
    for name in model_cls.model_fields:
        if name == "provenance":
            continue
        if name in data:
            continue
        data[name] = getattr(obj, name)
    return model_cls(**data)

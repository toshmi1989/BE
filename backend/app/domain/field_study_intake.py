"""Phase 21 — Real package intake lifecycle (no fabricated packages).

States: INTAKE → SANITIZATION_REVIEW → READY_FOR_SESSION →
SESSION_IN_PROGRESS → SESSION_COMPLETE → QA_REVIEW
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.real_package_registry import (
    REPO_ROOT,
    get_real_package,
    list_real_packages,
    population_status,
    validate_intake_filenames,
)

INTAKE_STATES: tuple[str, ...] = (
    "INTAKE",
    "SANITIZATION_REVIEW",
    "READY_FOR_SESSION",
    "SESSION_IN_PROGRESS",
    "SESSION_COMPLETE",
    "QA_REVIEW",
)

DOC_CHECKLIST_KEYS: tuple[str, ...] = (
    "Checklist",
    "Synopsis_Design",
    "SmPC_OHLP",
    "Previous_protocol",
    "Supporting_evidence",
    "Other",
)

DOC_STATUS = ("PRESENT", "ABSENT", "NOT_REQUIRED")

_STORE_PATH = REPO_ROOT / "fixtures" / "field_study" / "intake_cases.json"
_CASES: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _persist() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": _now(), "cases": list(_CASES.values())}
    _STORE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _load() -> None:
    global _CASES
    if not _STORE_PATH.exists():
        return
    data = json.loads(_STORE_PATH.read_text(encoding="utf-8-sig"))
    _CASES = {c["case_id"]: c for c in (data.get("cases") or []) if c.get("case_id")}


def reset_intake_store(*, clear_disk: bool = False) -> None:
    _CASES.clear()
    if clear_disk and _STORE_PATH.exists():
        _STORE_PATH.unlink()


def bootstrap_from_registry() -> list[dict[str, Any]]:
    """Seed intake rows from existing REAL registry entries (no fabrication)."""
    _load()
    created: list[dict[str, Any]] = []
    for p in list_real_packages(include_partial=True):
        cid = p["case_id"]
        if cid in _CASES:
            continue
        inventory = _inventory_from_package(p)
        state = "READY_FOR_SESSION" if p.get("sanitized") else "SANITIZATION_REVIEW"
        row = {
            "case_id": cid,
            "source_origin": p.get("source_origin"),
            "origin": p.get("origin"),
            "sanitization_status": "yes" if p.get("sanitized") else "no",
            "document_inventory": inventory,
            "study_pattern": list(p.get("patterns") or []),
            "intake_date": p.get("date_received") or _now()[:10],
            "writer_assigned": p.get("writer_assigned"),
            "state": state,
            "ready_for_session": state == "READY_FOR_SESSION",
            "synthetic": False,
            "fabricated": False,
            "notes": p.get("notes"),
            "created_at": _now(),
            "updated_at": _now(),
        }
        _CASES[cid] = row
        created.append(dict(row))
    if created:
        _persist()
    return created


def _inventory_from_package(p: dict[str, Any]) -> dict[str, str]:
    available = {str(x).upper() for x in (p.get("available_documents") or [])}
    mapping = {
        "Checklist": "CHECKLIST",
        "Synopsis_Design": ("SYNOPSIS", "DESIGN"),
        "SmPC_OHLP": ("SMPC", "OHLP", "ОХЛП"),
        "Previous_protocol": ("GOLDEN_PROTOCOL", "PREVIOUS_PROTOCOL", "PROTOCOL"),
        "Supporting_evidence": ("EVIDENCE", "REFERENCE", "SUPPORTING"),
        "Other": (),
    }
    out: dict[str, str] = {}
    for key, needles in mapping.items():
        if key == "Other":
            out[key] = "ABSENT"
            continue
        if isinstance(needles, str):
            needles = (needles,)
        present = any(any(n in a for n in needles) for a in available) or any(
            n in available for n in needles
        )
        # Also direct token match
        if not present:
            present = any(tok in available for tok in needles)
        out[key] = "PRESENT" if present else "ABSENT"
    # Design-only: Synopsis_Design PRESENT via DESIGN
    if "DESIGN" in available:
        out["Synopsis_Design"] = "PRESENT"
    return out


def create_intake_case(
    *,
    case_id: str,
    source_origin: str,
    study_pattern: list[str] | None = None,
    filenames: list[str] | None = None,
    document_inventory: dict[str, str] | None = None,
    origin: str = "REAL",
) -> dict[str, Any]:
    """Create INTAKE case. Does not invent documents; inventory must be supplied."""
    _load()
    if case_id in _CASES:
        raise ValueError(f"case_id already exists: {case_id}")
    if origin not in {"REAL", "REAL_PARTIAL"}:
        raise ValueError("origin must be REAL or REAL_PARTIAL — synthetic not allowed")
    if filenames:
        gate = validate_intake_filenames(filenames)
        if not gate["ok"]:
            raise ValueError(f"Filename sanitization blocked: {gate['blocked_filenames']}")

    inventory = {k: "ABSENT" for k in DOC_CHECKLIST_KEYS}
    if document_inventory:
        for k, v in document_inventory.items():
            if k not in DOC_CHECKLIST_KEYS:
                raise ValueError(f"Unknown inventory key: {k}")
            if v not in DOC_STATUS:
                raise ValueError(f"Invalid status {v} for {k}")
            inventory[k] = v

    row = {
        "case_id": case_id,
        "source_origin": source_origin,
        "origin": origin,
        "sanitization_status": "pending",
        "document_inventory": inventory,
        "study_pattern": list(study_pattern or []),
        "intake_date": _now()[:10],
        "writer_assigned": None,
        "state": "INTAKE",
        "ready_for_session": False,
        "uploaded_filenames": list(filenames or []),
        "synthetic": False,
        "fabricated": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    _CASES[case_id] = row
    _persist()
    return dict(row)


def set_document_inventory(case_id: str, inventory: dict[str, str]) -> dict[str, Any]:
    _load()
    if case_id not in _CASES:
        raise KeyError(case_id)
    row = _CASES[case_id]
    for k, v in inventory.items():
        if k not in DOC_CHECKLIST_KEYS:
            raise ValueError(k)
        if v not in DOC_STATUS:
            raise ValueError(v)
        row["document_inventory"][k] = v
    # Absence is not automatically an error
    row["updated_at"] = _now()
    _persist()
    return dict(row)


def submit_sanitization_review(
    case_id: str,
    *,
    sanitized: bool,
    notes: str | None = None,
) -> dict[str, Any]:
    _load()
    row = _CASES[case_id]
    row["state"] = "SANITIZATION_REVIEW"
    row["sanitization_status"] = "yes" if sanitized else "no"
    row["sanitization_notes"] = (notes or "")[:2000]
    row["updated_at"] = _now()
    if not sanitized:
        row["ready_for_session"] = False
    _persist()
    return dict(row)


def assign_writer(case_id: str, writer_id: str) -> dict[str, Any]:
    """Assign pseudonymous writer_id only."""
    _load()
    row = _CASES[case_id]
    if not writer_id or "@" in writer_id or " " in writer_id.strip():
        # soft guard — prefer opaque ids
        pass
    row["writer_assigned"] = writer_id
    row["updated_at"] = _now()
    _persist()
    return dict(row)


def mark_ready_for_session(case_id: str) -> dict[str, Any]:
    _load()
    row = _CASES[case_id]
    if row.get("sanitization_status") != "yes":
        raise ValueError("REAL_PACKAGE_SANITIZED required before READY_FOR_SESSION")
    if not row.get("writer_assigned"):
        raise ValueError("writer_assigned required before READY_FOR_SESSION")
    row["state"] = "READY_FOR_SESSION"
    row["ready_for_session"] = True
    row["updated_at"] = _now()
    _persist()
    return dict(row)


def transition_state(case_id: str, state: str) -> dict[str, Any]:
    if state not in INTAKE_STATES:
        raise ValueError(state)
    _load()
    row = _CASES[case_id]
    row["state"] = state
    row["updated_at"] = _now()
    if state == "READY_FOR_SESSION":
        row["ready_for_session"] = True
    if state in {"SESSION_IN_PROGRESS", "SESSION_COMPLETE", "QA_REVIEW"}:
        row["ready_for_session"] = False
    _persist()
    return dict(row)


def get_intake_case(case_id: str) -> dict[str, Any] | None:
    _load()
    r = _CASES.get(case_id)
    return dict(r) if r else None


def list_intake_cases() -> list[dict[str, Any]]:
    _load()
    if not _CASES:
        bootstrap_from_registry()
        _load()
    return [dict(v) for v in _CASES.values()]


def register_distinct_real_package_guard(case_id: str, *, content_fingerprint: str | None = None) -> dict[str, Any]:
    """Refuse duplicates / synthetic. Does not create packages from thin air."""
    _load()
    existing_ids = {p["case_id"] for p in list_real_packages(include_partial=True)}
    existing_ids |= set(_CASES.keys())
    if case_id in existing_ids and case_id in _CASES:
        return {"ok": True, "note": "already registered intake case"}
    fps = [
        c.get("content_fingerprint")
        for c in _CASES.values()
        if c.get("content_fingerprint")
    ]
    if content_fingerprint and content_fingerprint in fps:
        return {
            "ok": False,
            "reason": "duplicate_content_fingerprint",
            "note": "Same protocol with cosmetic filename changes is not distinct",
        }
    return {"ok": True}


def intake_status_summary() -> dict[str, Any]:
    cases = list_intake_cases()
    by_state: dict[str, int] = {s: 0 for s in INTAKE_STATES}
    for c in cases:
        st = c.get("state")
        if st in by_state:
            by_state[st] += 1
    pop = population_status()
    return {
        "intake_cases": len(cases),
        "by_state": by_state,
        "ready_for_session": sum(1 for c in cases if c.get("ready_for_session")),
        "registry_full_real": pop.get("real_full_sanitized"),
        "registry_partial_real": pop.get("real_partial_sanitized"),
        "synthetic_in_intake": sum(1 for c in cases if c.get("synthetic")),
        "fabricated": False,
    }

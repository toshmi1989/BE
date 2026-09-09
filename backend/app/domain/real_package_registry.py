"""Phase 19 — Real package registry (REAL only; synthetic never counted)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_ROOT = REPO_ROOT / "fixtures" / "real_packages"
REGISTRY_PATH = REAL_ROOT / "registry.json"

# Filename heuristics only — do not deep-scan document content for PII discovery
_BLOCKED_NAME_PATTERNS = (
    re.compile(r"patient", re.I),
    re.compile(r"subject[-_ ]?\d{3,}", re.I),
    re.compile(r"passport", re.I),
    re.compile(r"credential", re.I),
    re.compile(r"\.pem$", re.I),
    re.compile(r"password", re.I),
)


def load_real_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8-sig"))


def list_real_packages(*, include_partial: bool = True) -> list[dict[str, Any]]:
    pkgs = list(load_real_registry().get("packages") or [])
    if include_partial:
        return pkgs
    return [p for p in pkgs if p.get("origin") == "REAL"]


def population_status() -> dict[str, Any]:
    reg = load_real_registry()
    status = dict(reg.get("population_status") or {})
    pkgs = list_real_packages(include_partial=True)
    full = sum(1 for p in pkgs if p.get("origin") == "REAL" and p.get("sanitized") is True)
    # REAL_BETA alias counts as full REAL if sanitized
    full += sum(
        1
        for p in pkgs
        if p.get("origin") == "REAL_BETA" and p.get("sanitized") is True
    )
    partial = sum(1 for p in pkgs if p.get("origin") == "REAL_PARTIAL" and p.get("sanitized") is True)
    # Explicitly exclude TEST / SYNTHETIC
    test_or_synth = [
        p["case_id"]
        for p in pkgs
        if p.get("origin") in {"TEST", "SYNTHETIC"}
    ]
    unsanitized = [p["case_id"] for p in pkgs if not p.get("sanitized")]
    empty_slots = [
        s["slot_id"]
        for s in (reg.get("intake_slots") or [])
        if s.get("status") == "EMPTY"
    ]
    meets = full >= 10  # partial does not satisfy "10 distinct REAL full packages"
    status.update(
        {
            "real_full_sanitized": full,
            "real_partial_sanitized": partial,
            "unsanitized_blocked": unsanitized,
            "empty_intake_slots": empty_slots,
            "meets_minimum_10_full_real": meets,
            "synthetic_counted_as_real": False,
            "test_or_synthetic_excluded": test_or_synth,
            "sample_classes": ["TEST", "SYNTHETIC", "REAL_BETA", "REAL", "REAL_PARTIAL"],
            "production_gate": "READY-WITH-BLOCKERS" if not meets else "CANDIDATE_READY_REVIEW",
        }
    )
    return status


def get_real_package(case_id: str) -> dict[str, Any]:
    for p in list_real_packages():
        if p.get("case_id") == case_id:
            return p
    raise KeyError(case_id)


def validate_intake_filenames(filenames: list[str]) -> dict[str, Any]:
    """Refuse obvious sensitive filenames — does not deep-scan document bodies."""
    blocked: list[str] = []
    for name in filenames:
        base = Path(name).name
        if any(p.search(base) for p in _BLOCKED_NAME_PATTERNS):
            blocked.append(base)
    return {
        "ok": len(blocked) == 0,
        "blocked_filenames": blocked,
        "note": "Filename heuristic only; full sanitization checklist still required",
        "REAL_PACKAGE_SANITIZED_required": True,
    }


def diversity_report() -> dict[str, Any]:
    reg = load_real_registry()
    return dict(reg.get("diversity_coverage") or {})


def field_study_intake_manifest() -> dict[str, Any]:
    """Phase 20 intake view — no fabricated values."""
    pkgs = []
    for p in list_real_packages(include_partial=True):
        pkgs.append(
            {
                "case_id": p.get("case_id"),
                "sanitization_status": "yes" if p.get("sanitized") else "no",
                "document_inventory": {
                    "available": list(p.get("available_documents") or []),
                    "missing": list(p.get("missing_documents") or []),
                },
                "study_pattern": list(p.get("patterns") or []),
                "complexity_notes": p.get("complexity_notes"),
                "writer_assigned": p.get("writer_assigned"),
                "date_received": p.get("date_received"),
                "origin": p.get("origin"),
                "eligible_for_field_study": bool(p.get("sanitized")) and p.get("origin") in {"REAL", "REAL_PARTIAL"},
            }
        )
    status = population_status()
    return {
        "packages": pkgs,
        "empty_intake_slots": status.get("empty_intake_slots"),
        "meets_minimum_10_full_real": status.get("meets_minimum_10_full_real"),
        "limitation": status.get("limitation")
        or (
            None
            if status.get("meets_minimum_10_full_real")
            else "Fewer than 10 distinct full REAL packages available; do not invent packages"
        ),
        "fabricated_values": False,
    }

"""In-memory Study Input Package store — Phase 14 API."""

from __future__ import annotations

from typing import Any

from app.domain.study_input_package import StudyInputPackage

_PACKAGES: dict[str, StudyInputPackage] = {}


def clear_store() -> None:
    _PACKAGES.clear()


def put_package(pkg: StudyInputPackage) -> StudyInputPackage:
    _PACKAGES[pkg.package_id] = pkg
    return pkg


def get_package(package_id: str) -> StudyInputPackage | None:
    return _PACKAGES.get(package_id)


def list_packages() -> list[StudyInputPackage]:
    return list(_PACKAGES.values())


def package_readiness(pkg: StudyInputPackage) -> dict[str, Any]:
    open_conflicts = [c for c in pkg.conflicts if str(c.get("status") or "OPEN") == "OPEN"]
    critical_conflict = any(
        c.get("field_path") == "reference_product.dose" and str(c.get("status") or "OPEN") == "OPEN"
        for c in pkg.conflicts
    )
    ready = bool(pkg.coverage.get("ready_for_assembly")) and not open_conflicts
    return {
        "package_id": pkg.package_id,
        "status": pkg.status,
        "ready_for_assembly": ready,
        "ready_green": ready and not critical_conflict,
        "open_conflicts": len(open_conflicts),
        "blocking_issues": list(pkg.blocking_issues),
        "critical_conflict_unresolved": critical_conflict,
        "study_mutated": False,
        "message": (
            "Not ready: unresolved critical conflicts"
            if critical_conflict
            else ("Ready for assembly" if ready else "Review required")
        ),
    }

"""Phase 16 — Soft RBAC roles (extends org foundation; no auth rewrite).

Does not introduce JWT/users. Provides role vocabulary + permission checks
for workspace commands. Default runtime remains open for local/dev unless
a role is explicitly attached to the request context.
"""

from __future__ import annotations

from typing import Any

ROLES: tuple[str, ...] = ("ADMIN", "MEDICAL_WRITER", "REVIEWER", "VIEWER")

PERMISSIONS: dict[str, frozenset[str]] = {
    "ADMIN": frozenset(
        {
            "manage_users",
            "manage_organization",
            "all_studies",
            "create_study",
            "upload_documents",
            "review_extraction",
            "approve_decisions",
            "generate_protocol",
            "review_evidence",
            "qa",
            "view",
        }
    ),
    "MEDICAL_WRITER": frozenset(
        {
            "create_study",
            "upload_documents",
            "review_extraction",
            "approve_decisions",
            "generate_protocol",
            "view",
        }
    ),
    "REVIEWER": frozenset(
        {
            "review_evidence",
            "approve_decisions",
            "qa",
            "view",
        }
    ),
    "VIEWER": frozenset({"view"}),
}


def normalize_role(role: str | None) -> str:
    if not role:
        return "MEDICAL_WRITER"  # default for unauthenticated local workflow
    r = str(role).strip().upper()
    if r not in ROLES:
        raise ValueError(f"Unknown role: {role}")
    return r


def can(role: str | None, permission: str) -> bool:
    r = normalize_role(role)
    return permission in PERMISSIONS[r]


def require(role: str | None, permission: str) -> dict[str, Any]:
    ok = can(role, permission)
    return {
        "allowed": ok,
        "role": normalize_role(role),
        "permission": permission,
        "message": None if ok else f"Role {normalize_role(role)} lacks {permission}",
    }

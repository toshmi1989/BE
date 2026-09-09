/** Frontend mirror of backend `workspace_rbac` permissions. */

export type Permission =
  | "manage_users"
  | "manage_organization"
  | "all_studies"
  | "create_study"
  | "upload_documents"
  | "review_extraction"
  | "approve_decisions"
  | "generate_protocol"
  | "review_evidence"
  | "qa"
  | "view";

const ROLE_PERMISSIONS: Record<string, ReadonlySet<Permission>> = {
  ADMIN: new Set([
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
  ]),
  MEDICAL_WRITER: new Set([
    "create_study",
    "upload_documents",
    "review_extraction",
    "approve_decisions",
    "generate_protocol",
    "view",
  ]),
  REVIEWER: new Set(["review_evidence", "approve_decisions", "qa", "view"]),
  VIEWER: new Set(["view"]),
};

export function permissionsForRole(role: string | null | undefined): ReadonlySet<Permission> {
  if (!role) return ROLE_PERMISSIONS.MEDICAL_WRITER!;
  const key = role.trim().toUpperCase();
  return ROLE_PERMISSIONS[key] ?? ROLE_PERMISSIONS.VIEWER!;
}

/**
 * When auth is off (local/dev), treat as allowed.
 * When auth is on, gate by role permission (and optional explicit permissions array).
 */
export function canPermission(opts: {
  authRequired: boolean;
  role?: string | null;
  permissions?: string[] | null;
  permission: Permission;
}): boolean {
  if (!opts.authRequired) return true;
  if (Array.isArray(opts.permissions) && opts.permissions.length > 0) {
    return opts.permissions.includes(opts.permission);
  }
  return permissionsForRole(opts.role).has(opts.permission);
}

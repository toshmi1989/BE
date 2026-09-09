/** Phase 28 — Writer API response contracts + runtime parsers. */

export class ContractError extends Error {
  readonly path: string;

  constructor(message: string, path = "") {
    super(path ? `${path}: ${message}` : message);
    this.name = "ContractError";
    this.path = path;
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function requireObject(value: unknown, path: string): Record<string, unknown> {
  if (!isObject(value)) {
    throw new ContractError(`expected object, got ${describe(value)}`, path);
  }
  return value;
}

function requireString(value: unknown, path: string): string {
  if (typeof value !== "string") {
    throw new ContractError(`expected string, got ${describe(value)}`, path);
  }
  return value;
}

function optionalString(value: unknown, path: string): string | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  if (typeof value === "string") return value;
  throw new ContractError(`expected string|null, got ${describe(value)}`, path);
}

function optionalNumber(value: unknown, path: string): number | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  if (typeof value === "number" && Number.isFinite(value)) return value;
  throw new ContractError(`expected number|null, got ${describe(value)}`, path);
}

function requireArray(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new ContractError(`expected array, got ${describe(value)}`, path);
  }
  return value;
}

function describe(value: unknown): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  return typeof value;
}

function asRecord(value: unknown): Record<string, unknown> {
  return isObject(value) ? value : {};
}

/* ---------- Auth ---------- */

export type AuthUser = {
  user_id: string;
  email: string;
  display_name: string;
  organization_id: string | null;
  role: string | null;
};

export type AuthTokenResponse = AuthUser & {
  access_token: string | null;
  token_type: string;
};

export type VersionInfo = {
  version: string;
  git_revision: string | null;
  migration_revision: string | null;
  auth_required: boolean;
  ai_enabled: boolean;
  secrets_included: boolean;
};

export function parseAuthUser(raw: unknown): AuthUser {
  const o = requireObject(raw, "AuthUser");
  return {
    user_id: requireString(o.user_id, "AuthUser.user_id"),
    email: requireString(o.email, "AuthUser.email"),
    display_name: requireString(o.display_name ?? o.email, "AuthUser.display_name"),
    organization_id:
      o.organization_id === null || o.organization_id === undefined
        ? null
        : requireString(o.organization_id, "AuthUser.organization_id"),
    role:
      o.role === null || o.role === undefined
        ? null
        : requireString(o.role, "AuthUser.role"),
  };
}

export function parseAuthTokenResponse(raw: unknown): AuthTokenResponse {
  const o = requireObject(raw, "AuthTokenResponse");
  const user = parseAuthUser(o);
  let access_token: string | null = null;
  if (o.access_token === null || o.access_token === undefined) {
    access_token = null;
  } else {
    access_token = requireString(o.access_token, "AuthTokenResponse.access_token");
  }
  return {
    ...user,
    access_token,
    token_type: typeof o.token_type === "string" ? o.token_type : "bearer",
  };
}

export function parseVersionInfo(raw: unknown): VersionInfo {
  const o = requireObject(raw, "VersionInfo");
  return {
    version: requireString(o.version, "VersionInfo.version"),
    git_revision: optionalString(o.git_revision, "VersionInfo.git_revision") ?? null,
    migration_revision:
      optionalString(o.migration_revision, "VersionInfo.migration_revision") ?? null,
    auth_required: Boolean(o.auth_required),
    ai_enabled: Boolean(o.ai_enabled),
    secrets_included: Boolean(o.secrets_included),
  };
}

/* ---------- Study catalog ---------- */

export type StudyListItem = {
  study_id: string;
  study_key: string;
  title: string | null;
  sponsor: string | null;
  product: string | null;
  dose: string | null;
  lifecycle: string;
  status: string;
  readiness: string | null;
  readiness_label: string | null;
  document_count: number;
  state_version?: number | null;
  organization_id?: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type StudyListResponse = {
  studies: StudyListItem[];
  total: number;
  offset: number;
  limit: number;
  organization_id: string;
};

export function parseStudyListItem(raw: unknown, path = "StudyListItem"): StudyListItem {
  const o = requireObject(raw, path);
  return {
    study_id: requireString(o.study_id, `${path}.study_id`),
    study_key: requireString(o.study_key, `${path}.study_key`),
    title: optionalString(o.title, `${path}.title`) ?? null,
    sponsor: optionalString(o.sponsor, `${path}.sponsor`) ?? null,
    product: optionalString(o.product, `${path}.product`) ?? null,
    dose: optionalString(o.dose, `${path}.dose`) ?? null,
    lifecycle: requireString(o.lifecycle ?? "DRAFT", `${path}.lifecycle`),
    status: requireString(o.status ?? "ACTIVE", `${path}.status`),
    readiness: optionalString(o.readiness, `${path}.readiness`) ?? null,
    readiness_label: optionalString(o.readiness_label, `${path}.readiness_label`) ?? null,
    document_count:
      typeof o.document_count === "number" && Number.isFinite(o.document_count)
        ? o.document_count
        : 0,
    state_version: optionalNumber(o.state_version, `${path}.state_version`),
    organization_id: optionalString(o.organization_id, `${path}.organization_id`) ?? null,
    created_at: optionalString(o.created_at, `${path}.created_at`) ?? null,
    updated_at: optionalString(o.updated_at, `${path}.updated_at`) ?? null,
  };
}

export function parseStudyListResponse(raw: unknown): StudyListResponse {
  const o = requireObject(raw, "StudyListResponse");
  const studies = requireArray(o.studies, "StudyListResponse.studies").map((item, i) =>
    parseStudyListItem(item, `StudyListResponse.studies[${i}]`),
  );
  if (typeof o.total !== "number") {
    throw new ContractError(`expected number, got ${describe(o.total)}`, "StudyListResponse.total");
  }
  return {
    studies,
    total: o.total,
    offset: typeof o.offset === "number" ? o.offset : 0,
    limit: typeof o.limit === "number" ? o.limit : studies.length,
    organization_id: requireString(
      o.organization_id ?? "",
      "StudyListResponse.organization_id",
    ),
  };
}

/* ---------- Workspace summary ---------- */

export type CanonicalFact = {
  field: string;
  value: unknown;
  canonical_value?: unknown;
  status: string;
  source: string | null;
  evidence_id: string | null;
  affected_sections: unknown[];
  [key: string]: unknown;
};

export type WorkspaceSummary = {
  study_id: string;
  header: Record<string, unknown>;
  nav: Array<Record<string, unknown>>;
  summary_cards: Record<string, unknown>;
  readiness: Record<string, unknown>;
  conflicts: unknown[];
  decisions: Record<string, unknown> | unknown[];
  canonical_facts: CanonicalFact[];
  [key: string]: unknown;
};

export function parseCanonicalFact(raw: unknown, path = "CanonicalFact"): CanonicalFact {
  const o = requireObject(raw, path);
  const field = requireString(o.field ?? o.field_path, `${path}.field`);
  return {
    ...o,
    field,
    value: o.value,
    canonical_value: o.canonical_value !== undefined ? o.canonical_value : o.value,
    status: requireString(o.status ?? "UNKNOWN", `${path}.status`),
    source:
      o.source === null || o.source === undefined
        ? null
        : requireString(String(o.source), `${path}.source`),
    evidence_id:
      o.evidence_id === null || o.evidence_id === undefined
        ? null
        : String(o.evidence_id),
    affected_sections: Array.isArray(o.affected_sections) ? o.affected_sections : [],
  };
}

export function parseCanonicalFacts(raw: unknown): CanonicalFact[] {
  if (isObject(raw) && Array.isArray(raw.canonical_facts)) {
    return parseCanonicalFacts(raw.canonical_facts);
  }
  return requireArray(raw, "CanonicalFacts").map((item, i) =>
    parseCanonicalFact(item, `CanonicalFacts[${i}]`),
  );
}

export function parseWorkspaceSummary(raw: unknown): WorkspaceSummary {
  const o = requireObject(raw, "WorkspaceSummary");
  const study_id = requireString(o.study_id, "WorkspaceSummary.study_id");
  const factsRaw = o.canonical_facts;
  const canonical_facts = Array.isArray(factsRaw)
    ? factsRaw.map((item, i) => parseCanonicalFact(item, `WorkspaceSummary.canonical_facts[${i}]`))
    : [];
  return {
    ...o,
    study_id,
    header: asRecord(o.header),
    nav: Array.isArray(o.nav) ? o.nav.map((x) => asRecord(x)) : [],
    summary_cards: asRecord(o.summary_cards),
    readiness: asRecord(o.readiness),
    conflicts: Array.isArray(o.conflicts) ? o.conflicts : [],
    decisions: (o.decisions as Record<string, unknown> | unknown[]) ?? {},
    canonical_facts,
  };
}

/* ---------- Writer progress ---------- */

export type WriterProgressStep = {
  id: string;
  label: string;
  status: string;
  tab: string;
};

export type WriterProgress = {
  study_id: string;
  steps: WriterProgressStep[];
  primary_next_action: Record<string, unknown>;
  secondary_issues: Array<Record<string, unknown>>;
  blockers: Array<Record<string, unknown>>;
  package_checklist: Array<Record<string, unknown>>;
  counts: Record<string, unknown>;
  versions: Record<string, unknown>;
  preflight: Record<string, unknown>;
  [key: string]: unknown;
};

export function parseWriterProgress(raw: unknown): WriterProgress {
  const o = requireObject(raw, "WriterProgress");
  const steps = requireArray(o.steps, "WriterProgress.steps").map((item, i) => {
    const s = requireObject(item, `WriterProgress.steps[${i}]`);
    return {
      id: requireString(s.id, `WriterProgress.steps[${i}].id`),
      label: requireString(s.label, `WriterProgress.steps[${i}].label`),
      status: requireString(s.status, `WriterProgress.steps[${i}].status`),
      tab: requireString(s.tab, `WriterProgress.steps[${i}].tab`),
    };
  });
  return {
    ...o,
    study_id: requireString(o.study_id ?? "", "WriterProgress.study_id"),
    steps,
    primary_next_action: asRecord(o.primary_next_action),
    secondary_issues: Array.isArray(o.secondary_issues)
      ? o.secondary_issues.map((x) => asRecord(x))
      : [],
    blockers: Array.isArray(o.blockers) ? o.blockers.map((x) => asRecord(x)) : [],
    package_checklist: Array.isArray(o.package_checklist)
      ? o.package_checklist.map((x) => asRecord(x))
      : [],
    counts: asRecord(o.counts),
    versions: asRecord(o.versions),
    preflight: asRecord(o.preflight),
  };
}

/* ---------- Decisions ---------- */

export type DecisionRow = {
  id?: string;
  decision_id?: string;
  status?: string;
  domain?: string;
  [key: string]: unknown;
};

export type DecisionsResponse = {
  study_id: string | null;
  decisions: DecisionRow[];
  open_conflicts?: unknown[];
  [key: string]: unknown;
};

export function parseDecisionsResponse(raw: unknown): DecisionsResponse {
  const o = requireObject(raw, "DecisionsResponse");
  const decisionsRaw = o.decisions;
  if (!Array.isArray(decisionsRaw)) {
    throw new ContractError(
      `expected decisions array, got ${describe(decisionsRaw)}`,
      "DecisionsResponse.decisions",
    );
  }
  return {
    ...o,
    study_id:
      o.study_id === null || o.study_id === undefined
        ? null
        : requireString(String(o.study_id), "DecisionsResponse.study_id"),
    decisions: decisionsRaw.map((item, i) => {
      const d = requireObject(item, `DecisionsResponse.decisions[${i}]`);
      return { ...d };
    }),
    open_conflicts: Array.isArray(o.open_conflicts) ? o.open_conflicts : [],
  };
}

/* ---------- Sample size ---------- */

export type SampleSizePanel = {
  section?: string;
  study_id: string;
  status: string;
  blocking_reasons: string[];
  calculated_n?: number | null;
  latest_calculation_id?: string | null;
  [key: string]: unknown;
};

export function parseSampleSizePanel(raw: unknown): SampleSizePanel {
  const o = requireObject(raw, "SampleSizePanel");
  return {
    ...o,
    section: typeof o.section === "string" ? o.section : undefined,
    study_id: requireString(o.study_id, "SampleSizePanel.study_id"),
    status: requireString(o.status ?? "NO_CALCULATION", "SampleSizePanel.status"),
    blocking_reasons: Array.isArray(o.blocking_reasons)
      ? o.blocking_reasons.map((x) => String(x))
      : [],
    calculated_n: optionalNumber(o.calculated_n, "SampleSizePanel.calculated_n"),
    latest_calculation_id:
      o.latest_calculation_id === null || o.latest_calculation_id === undefined
        ? null
        : String(o.latest_calculation_id),
  };
}

/* ---------- Statistics (critical contract) ---------- */

export type StatisticsPanel = {
  study_id?: string;
  plan_id?: string | null;
  status?: string;
  blocking_reasons?: string[];
  is_approved?: boolean;
  scenarios?: unknown[];
  recommendation_summary?: string | null;
  version?: number | string | null;
  parameters?: unknown[];
  [key: string]: unknown;
};

/**
 * Exact Writer statistics GET contract:
 * `{ study_id, latest, panel, plans }` — `panel` may be absent; guard before use.
 */
export type StatisticsResponse = {
  study_id: string;
  latest: Record<string, unknown> | null;
  panel?: StatisticsPanel;
  plans: Array<Record<string, unknown>>;
};

export function isStatisticsPanel(value: unknown): value is StatisticsPanel {
  return isObject(value);
}

export function parseStatisticsPanel(raw: unknown, path = "StatisticsPanel"): StatisticsPanel {
  const o = requireObject(raw, path);
  return {
    ...o,
    study_id: typeof o.study_id === "string" ? o.study_id : undefined,
    plan_id:
      o.plan_id === null || o.plan_id === undefined
        ? o.plan_id === null
          ? null
          : undefined
        : String(o.plan_id),
    status: typeof o.status === "string" ? o.status : undefined,
    blocking_reasons: Array.isArray(o.blocking_reasons)
      ? o.blocking_reasons.map((x) => String(x))
      : undefined,
    is_approved: typeof o.is_approved === "boolean" ? o.is_approved : undefined,
    scenarios: Array.isArray(o.scenarios) ? o.scenarios : undefined,
    recommendation_summary:
      o.recommendation_summary === null || typeof o.recommendation_summary === "string"
        ? (o.recommendation_summary as string | null)
        : undefined,
  };
}

export function parseStatisticsResponse(raw: unknown): StatisticsResponse {
  const o = requireObject(raw, "StatisticsResponse");
  const study_id = requireString(o.study_id, "StatisticsResponse.study_id");
  const plans = requireArray(o.plans, "StatisticsResponse.plans").map((item, i) => {
    requireObject(item, `StatisticsResponse.plans[${i}]`);
    return item as Record<string, unknown>;
  });

  let latest: Record<string, unknown> | null = null;
  if (o.latest === null || o.latest === undefined) {
    latest = null;
  } else {
    latest = requireObject(o.latest, "StatisticsResponse.latest");
  }

  // panel may be missing — do not invent; only parse when present
  let panel: StatisticsPanel | undefined;
  if (o.panel !== undefined && o.panel !== null) {
    panel = parseStatisticsPanel(o.panel, "StatisticsResponse.panel");
  }

  return { study_id, latest, panel, plans };
}

/** Safe accessor — returns undefined when panel was omitted by the API. */
export function getStatisticsPanel(response: StatisticsResponse): StatisticsPanel | undefined {
  return response.panel;
}

/* ---------- Protocol preview ---------- */

export type ProtocolPreview = {
  toc?: Array<Record<string, unknown>>;
  sections?: Array<Record<string, unknown>>;
  tables?: Array<Record<string, unknown>>;
  protocol_id?: string;
  version?: number | string;
  status?: string;
  snapshot_id?: string | null;
  [key: string]: unknown;
};

export function parseProtocolPreview(raw: unknown): ProtocolPreview {
  const o = requireObject(raw, "ProtocolPreview");
  return {
    ...o,
    toc: Array.isArray(o.toc) ? o.toc.map((x) => asRecord(x)) : undefined,
    sections: Array.isArray(o.sections) ? o.sections.map((x) => asRecord(x)) : undefined,
    tables: Array.isArray(o.tables) ? o.tables.map((x) => asRecord(x)) : undefined,
    protocol_id: typeof o.protocol_id === "string" ? o.protocol_id : undefined,
    version:
      typeof o.version === "string" || typeof o.version === "number" ? o.version : undefined,
    status: typeof o.status === "string" ? o.status : undefined,
    snapshot_id:
      o.snapshot_id === null || o.snapshot_id === undefined
        ? (o.snapshot_id as null | undefined)
        : String(o.snapshot_id),
  };
}

/* ---------- Preflight ---------- */

export type PreflightCheck = {
  category: string;
  code: string;
  severity: string;
  message: string;
  ok: boolean;
  [key: string]: unknown;
};

export type PreflightResponse = {
  study_id: string;
  categories: string[];
  checks: PreflightCheck[];
  critical_blockers: PreflightCheck[];
  can_finalize: boolean;
  can_generate_docx: boolean;
  readiness?: string;
  readiness_label?: string;
  message?: string;
  stale_dependencies?: Record<string, unknown>;
  [key: string]: unknown;
};

function parsePreflightCheck(raw: unknown, path: string): PreflightCheck {
  const o = requireObject(raw, path);
  return {
    ...o,
    category: requireString(o.category ?? "UNKNOWN", `${path}.category`),
    code: requireString(o.code ?? "UNKNOWN", `${path}.code`),
    severity: requireString(o.severity ?? "INFO", `${path}.severity`),
    message: requireString(o.message ?? o.label ?? "", `${path}.message`),
    ok: Boolean(o.ok),
  };
}

export function parsePreflightResponse(raw: unknown): PreflightResponse {
  const o = requireObject(raw, "PreflightResponse");
  const checks = requireArray(o.checks, "PreflightResponse.checks").map((item, i) =>
    parsePreflightCheck(item, `PreflightResponse.checks[${i}]`),
  );
  const blockersRaw = Array.isArray(o.critical_blockers) ? o.critical_blockers : [];
  return {
    ...o,
    study_id: requireString(o.study_id, "PreflightResponse.study_id"),
    categories: Array.isArray(o.categories) ? o.categories.map((x) => String(x)) : [],
    checks,
    critical_blockers: blockersRaw.map((item, i) =>
      parsePreflightCheck(item, `PreflightResponse.critical_blockers[${i}]`),
    ),
    can_finalize: Boolean(o.can_finalize),
    can_generate_docx: Boolean(o.can_generate_docx),
    readiness: typeof o.readiness === "string" ? o.readiness : undefined,
    readiness_label: typeof o.readiness_label === "string" ? o.readiness_label : undefined,
    message: typeof o.message === "string" ? o.message : undefined,
    stale_dependencies: isObject(o.stale_dependencies) ? o.stale_dependencies : undefined,
  };
}

/* ---------- Artifacts ---------- */

export type ProtocolArtifact = {
  artifact_id: string;
  protocol_id?: string | null;
  study_id?: string;
  filename?: string;
  mime_type?: string;
  size?: number | null;
  generated_at?: string | null;
  [key: string]: unknown;
};

export type ArtifactsResponse = {
  study_id?: string;
  artifacts: ProtocolArtifact[];
};

export function parseArtifactsResponse(raw: unknown): ArtifactsResponse {
  const o = requireObject(raw, "ArtifactsResponse");
  const artifacts = requireArray(o.artifacts, "ArtifactsResponse.artifacts").map((item, i) => {
    const a = requireObject(item, `ArtifactsResponse.artifacts[${i}]`);
    return {
      ...a,
      artifact_id: requireString(a.artifact_id, `ArtifactsResponse.artifacts[${i}].artifact_id`),
      protocol_id:
        a.protocol_id === null || a.protocol_id === undefined
          ? null
          : String(a.protocol_id),
      study_id: typeof a.study_id === "string" ? a.study_id : undefined,
      filename: typeof a.filename === "string" ? a.filename : undefined,
      mime_type: typeof a.mime_type === "string" ? a.mime_type : undefined,
      size: optionalNumber(a.size, `ArtifactsResponse.artifacts[${i}].size`),
      generated_at: optionalString(a.generated_at, `ArtifactsResponse.artifacts[${i}].generated_at`),
    };
  });
  return {
    study_id: typeof o.study_id === "string" ? o.study_id : undefined,
    artifacts,
  };
}

/* ---------- Workflow ---------- */

export type WorkflowResponse = {
  workflow_id: string;
  steps?: unknown[];
  readiness?: Record<string, unknown>;
  preflight?: Record<string, unknown>;
  persisted?: boolean;
  [key: string]: unknown;
};

export function parseWorkflowResponse(raw: unknown): WorkflowResponse {
  const o = requireObject(raw, "WorkflowResponse");
  return {
    ...o,
    workflow_id: requireString(o.workflow_id, "WorkflowResponse.workflow_id"),
    steps: Array.isArray(o.steps) ? o.steps : undefined,
    readiness: isObject(o.readiness) ? o.readiness : undefined,
    preflight: isObject(o.preflight) ? o.preflight : undefined,
    persisted: typeof o.persisted === "boolean" ? o.persisted : undefined,
  };
}

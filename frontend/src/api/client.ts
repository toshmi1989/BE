import {
  parseArtifactsResponse,
  parseAuthTokenResponse,
  parseAuthUser,
  parseDecisionsResponse,
  parsePreflightResponse,
  parseProtocolPreview,
  parseSampleSizePanel,
  parseStatisticsResponse,
  parseStudyListResponse,
  parseVersionInfo,
  parseWorkflowResponse,
  parseWorkspaceSummary,
  parseWriterProgress,
  type ArtifactsResponse,
  type AuthTokenResponse,
  type AuthUser,
  type DecisionsResponse,
  type PreflightResponse,
  type ProtocolPreview,
  type SampleSizePanel,
  type StatisticsResponse,
  type StudyListItem,
  type StudyListResponse,
  type VersionInfo,
  type WorkflowResponse,
  type WorkspaceSummary,
  type WriterProgress,
} from "./contracts";

export type {
  ArtifactsResponse,
  AuthTokenResponse,
  AuthUser,
  DecisionsResponse,
  PreflightResponse,
  ProtocolPreview,
  SampleSizePanel,
  StatisticsResponse,
  StudyListItem,
  StudyListResponse,
  VersionInfo,
  WorkflowResponse,
  WorkspaceSummary,
  WriterProgress,
};

export {
  ContractError,
  getStatisticsPanel,
  parseStatisticsResponse,
  type StatisticsPanel,
} from "./contracts";

export function resolveApiBase(): string {
  const explicit = import.meta.env.VITE_API_BASE_URL;
  if (explicit != null && String(explicit).trim() !== "") {
    return String(explicit).replace(/\/$/, "");
  }
  if (import.meta.env.DEV) return "http://localhost:8000";
  return String(import.meta.env.BASE_URL || "/").replace(/\/$/, "");
}

const API_BASE = resolveApiBase();

const AUTH_TOKEN_KEY = "be_auth_token";

let authTokenMemory: string | null = null;

function readStoredToken(): string | null {
  try {
    if (typeof sessionStorage === "undefined") return null;
    const v = sessionStorage.getItem(AUTH_TOKEN_KEY);
    return v && v.trim() ? v : null;
  } catch {
    return null;
  }
}

export function getAuthToken(): string | null {
  if (authTokenMemory) return authTokenMemory;
  authTokenMemory = readStoredToken();
  return authTokenMemory;
}

export function setAuthToken(token: string | null): void {
  authTokenMemory = token && token.trim() ? token : null;
  try {
    if (typeof sessionStorage === "undefined") return;
    if (authTokenMemory) sessionStorage.setItem(AUTH_TOKEN_KEY, authTokenMemory);
    else sessionStorage.removeItem(AUTH_TOKEN_KEY);
  } catch {
    /* ignore storage errors (private mode / SSR) */
  }
}

export function clearAuthToken(): void {
  setAuthToken(null);
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: string;
  readonly code: string | null;
  /** Human-readable detail when the API returns JSON `detail` / `message`. */
  readonly userMessage: string;

  constructor(status: number, body: string, code: string | null = null) {
    const userMessage = extractErrorMessage(body) || body || `HTTP ${status}`;
    super(userMessage);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.code = code;
    this.userMessage = userMessage;
  }
}

function extractErrorMessage(body: string): string | null {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown; code?: unknown; message?: unknown };
    if (typeof parsed.message === "string" && parsed.message.trim()) return parsed.message;
    if (typeof parsed.detail === "string" && parsed.detail.trim()) return parsed.detail;
    if (parsed.detail && typeof parsed.detail === "object" && !Array.isArray(parsed.detail)) {
      const d = parsed.detail as { code?: unknown; message?: unknown; detail?: unknown };
      if (typeof d.message === "string" && d.message.trim()) return d.message;
      if (typeof d.detail === "string" && d.detail.trim()) return d.detail;
    }
    if (Array.isArray(parsed.detail) && parsed.detail.length) {
      const parts = parsed.detail.map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return JSON.stringify(item);
      });
      return parts.join("; ");
    }
  } catch {
    /* not JSON */
  }
  return null;
}

function extractErrorCode(body: string): string | null {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown; code?: unknown };
    if (typeof parsed.code === "string") return parsed.code;
    if (parsed.detail && typeof parsed.detail === "object" && !Array.isArray(parsed.detail)) {
      const d = parsed.detail as { code?: unknown };
      if (typeof d.code === "string") return d.code;
    }
  } catch {
    /* not JSON */
  }
  return null;
}

/** Prefer ApiError.userMessage; fall back to Error.message. */
export function formatApiError(err: unknown, fallback = "Request failed"): string {
  if (err instanceof ApiError) return err.userMessage;
  if (err instanceof Error && err.message.trim()) return err.message;
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? {});
  if (!headers.has("Content-Type") && !(init?.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAuthToken();
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });

  if (!response.ok) {
    const body = await response.text();
    if (response.status === 401) {
      clearAuthToken();
    }
    // 403: preserve token (forbidden ≠ unauthenticated)
    throw new ApiError(response.status, body, extractErrorCode(body));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export type HealthPayload = {
  status: string;
  service: string;
  version: string;
  schema_version: string;
  rules_catalog_version: string;
  ai_enabled: boolean;
  external_ai_enabled: boolean;
};

export type Provenance = {
  status: string;
  origin: string;
  confidence: number | null;
  source_ids: string[];
};

export type ProjectSummary = {
  id: string;
  name: string;
  status: string;
  schema_version: string;
  description: string | null;
  entity_version: number;
};

export type ClientInput = {
  id: string;
  requested_product_name: string | null;
  inn: string | null;
  dosage: string | null;
  dosage_form: string | null;
  route: string | null;
  requested_subject_count: number | null;
  provenance: Provenance;
};

export type Design = {
  id: string;
  type: string;
  periods: number | null;
  sequences: unknown[];
  food_condition: string | null;
  decision_status: string;
  rationale: string | null;
  provenance: Provenance;
};

export type Food = {
  id: string;
  condition: string;
  meal_type: string | null;
  water_volume_ml: number | null;
  decision_status: string;
  provenance: Provenance;
};

export type Eligibility = {
  inclusion: Array<{ id: string; number: number; text: string }>;
  non_inclusion: Array<{ id: string; number: number; text: string }>;
  exclusion: Array<{ id: string; number: number; text: string }>;
};

export type Subjects = {
  id: string;
  target_evaluable_n: number | null;
  planned_randomized_n: number | null;
  reserve_n: number | null;
  planned_screened_n: number | null;
  provenance: Provenance;
};

export type ProjectDetail = ProjectSummary & {
  study: { id: string; title: string | null; protocol_number: string | null; provenance: Provenance } | null;
  sponsor: { id: string; name: string; organization_id: string | null; provenance: Provenance } | null;
  organizations: Array<{ id: string; name: string; role: string; provenance: Provenance }>;
  product: { id: string; trade_name: string | null; inn: string | null; dosage: string | null; provenance: Provenance } | null;
  reference_product: {
    id: string;
    trade_name: string | null;
    purchased_status: string;
    provenance: Provenance;
  } | null;
  sources: Array<{ id: string; type: string; title: string; provenance: Provenance }>;
  versions: Array<{ id: string; version_number: number; label: string | null }>;
  client_input: ClientInput | null;
  design: Design | null;
  food: Food | null;
  eligibility: Eligibility | null;
  subjects: Subjects | null;
  analytes: Array<{
    id: string;
    name: string;
    type: string;
    tmax_min: number | null;
    tmax_max: number | null;
    half_life_min: number | null;
    half_life_max: number | null;
    provenance: Provenance;
  }>;
  washout: { calculated_minimum: number | null; selected_value: number | null; unit: string; status?: string } | null;
  observation: {
    calculated_minimum: number | null;
    selected_duration: number | null;
    final_sampling_time: number | null;
  } | null;
  sampling: {
    id: string;
    manual_override: boolean;
    total_points_per_period: number | null;
    final_observation_h: number | null;
    validation_issues: Array<{ severity: string; code: string; message: string }>;
    points: Array<{
      id: string;
      time_h: number;
      reason: string;
      window_before_min: number | null;
      window_after_min: number | null;
      provenance: Provenance;
    }>;
  } | null;
  blood_volume: {
    total_volume_ml: number;
    volume_per_subject_ml: number;
    pk_volume_ml: number;
  } | null;
  cv_studies?: Array<{
    id: string;
    parameter: string;
    cv_value: number;
    n_total: number | null;
    n_be_analysis: number | null;
    source_id: string;
    provenance: Provenance;
  }>;
  cv_selection?: {
    selected_cv: number | null;
    selection_method: string;
    rationale: string | null;
    provenance: Provenance;
  } | null;
  statistical_config?: {
    alpha: number;
    power: number;
    be_lower: number;
    be_upper: number;
    rule_id: string | null;
  } | null;
  sample_size?: {
    evaluable_n: number | null;
    randomized_n: number | null;
    screened_n: number | null;
    method: string;
    algorithm_version: string;
    selected_cv: number | null;
    provenance: Provenance;
  } | null;
};

export type DesignRecommendResult = {
  recommended_design: { type: string; periods?: number | null; food_condition?: string | null } | null;
  rationale: string;
  confidence: number | null;
  status: string;
  origin: string;
  persisted_design: Design | null;
};

export function fetchHealth(): Promise<HealthPayload> {
  return request<HealthPayload>("/api/health");
}

/** Phase 28 — auth + version + study catalog */
export async function getVersion(): Promise<VersionInfo> {
  const raw = await request<unknown>("/api/version");
  return parseVersionInfo(raw);
}

export async function login(body: {
  email: string;
  password: string;
  organization_id?: string;
}): Promise<AuthTokenResponse> {
  const raw = await request<unknown>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
  const parsed = parseAuthTokenResponse(raw);
  if (!parsed.access_token) {
    throw new ApiError(500, "Login response missing access_token", "MISSING_TOKEN");
  }
  setAuthToken(parsed.access_token);
  return parsed;
}

export async function register(body: {
  email: string;
  password: string;
  display_name: string;
  organization_name: string;
  organization_slug?: string;
  role?: string;
}): Promise<AuthTokenResponse> {
  const raw = await request<unknown>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(body),
  });
  const parsed = parseAuthTokenResponse(raw);
  if (parsed.access_token) setAuthToken(parsed.access_token);
  return parsed;
}

export async function getMe(): Promise<AuthUser> {
  const raw = await request<unknown>("/api/auth/me");
  return parseAuthUser(raw);
}

export async function logout(): Promise<void> {
  clearAuthToken();
}

export async function listStudies(params?: {
  q?: string;
  lifecycle?: string;
  readiness?: string;
  offset?: number;
  limit?: number;
  sort?: string;
}): Promise<StudyListResponse> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set("q", params.q);
  if (params?.lifecycle) qs.set("lifecycle", params.lifecycle);
  if (params?.readiness) qs.set("readiness", params.readiness);
  if (params?.offset != null) qs.set("offset", String(params.offset));
  if (params?.limit != null) qs.set("limit", String(params.limit));
  if (params?.sort) qs.set("sort", params.sort);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const raw = await request<unknown>(`/api/studies${suffix}`);
  return parseStudyListResponse(raw);
}

export function listProjects(): Promise<ProjectSummary[]> {
  return request<ProjectSummary[]>("/api/projects");
}

export function createProject(name: string, description?: string): Promise<ProjectDetail> {
  return request<ProjectDetail>("/api/projects", {
    method: "POST",
    body: JSON.stringify({ name, description: description || null }),
  });
}

export function getProject(id: string): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/api/projects/${id}`);
}

export function saveClientInput(
  projectId: string,
  body: Record<string, unknown>,
  exists: boolean,
): Promise<ClientInput> {
  return request<ClientInput>(`/api/projects/${projectId}/client-input`, {
    method: exists ? "PATCH" : "POST",
    body: JSON.stringify(body),
  });
}

export function saveDesign(
  projectId: string,
  body: Record<string, unknown>,
  exists: boolean,
): Promise<Design> {
  return request<Design>(`/api/projects/${projectId}/design`, {
    method: exists ? "PATCH" : "POST",
    body: JSON.stringify(body),
  });
}

export function recommendDesign(
  projectId: string,
  body: Record<string, unknown>,
): Promise<DesignRecommendResult> {
  return request<DesignRecommendResult>(`/api/projects/${projectId}/design/recommend`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function saveFood(
  projectId: string,
  body: Record<string, unknown>,
  exists: boolean,
): Promise<Food> {
  return request<Food>(`/api/projects/${projectId}/food`, {
    method: exists ? "PATCH" : "POST",
    body: JSON.stringify(body),
  });
}

export function replaceEligibility(
  projectId: string,
  body: Eligibility,
): Promise<Eligibility> {
  return request<Eligibility>(`/api/projects/${projectId}/eligibility`, {
    method: "PUT",
    body: JSON.stringify({
      inclusion: body.inclusion.map((c) => ({ number: c.number, text: c.text })),
      non_inclusion: body.non_inclusion.map((c) => ({ number: c.number, text: c.text })),
      exclusion: body.exclusion.map((c) => ({ number: c.number, text: c.text })),
    }),
  });
}

export function saveSubjects(
  projectId: string,
  body: Record<string, unknown>,
  exists: boolean,
): Promise<Subjects> {
  return request<Subjects>(`/api/projects/${projectId}/subjects`, {
    method: exists ? "PATCH" : "POST",
    body: JSON.stringify(body),
  });
}

export function getDesignReference(): Promise<{
  design_types: string[];
  food_conditions: string[];
  meal_types: string[];
  templates: Record<string, Record<string, unknown>>;
}> {
  return request("/api/reference-data/design");
}

export function createAnalyte(projectId: string, body: Record<string, unknown>) {
  return request(`/api/projects/${projectId}/analytes`, { method: "POST", body: JSON.stringify(body) });
}

export function calculateWashout(projectId: string, body: Record<string, unknown>) {
  return request(`/api/projects/${projectId}/washout/calculate`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function calculateObservation(projectId: string, body: Record<string, unknown>) {
  return request(`/api/projects/${projectId}/observation/calculate`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function recommendSampling(projectId: string) {
  return request(`/api/projects/${projectId}/sampling/recommend`, {
    method: "POST",
    body: JSON.stringify({ persist: true }),
  });
}

export function validateSampling(projectId: string) {
  return request<{ issues: Array<{ severity: string; code: string; message: string }>; blocking: boolean }>(
    `/api/projects/${projectId}/sampling/validate`,
    { method: "POST", body: "{}" },
  );
}

export function calculateBloodVolume(projectId: string, body: Record<string, unknown>) {
  return request(`/api/projects/${projectId}/blood-volume/calculate`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function createCvStudy(projectId: string, body: Record<string, unknown>) {
  return request(`/api/projects/${projectId}/statistics/cv`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function selectCv(projectId: string, body: Record<string, unknown>) {
  return request(`/api/projects/${projectId}/statistics/cv/select`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function calculateSampleSize(projectId: string, body: Record<string, unknown>) {
  return request(`/api/projects/${projectId}/statistics/sample-size`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getStatisticsConfig(projectId: string) {
  return request(`/api/projects/${projectId}/statistics/config`);
}

export function validateStatistics(projectId: string) {
  return request<{ issues: Array<{ severity: string; code: string; message: string }>; blocking: boolean }>(
    `/api/projects/${projectId}/statistics/validate`,
    { method: "POST", body: "{}" },
  );
}

export function runProjectValidation(projectId: string) {
  return request<{
    summary: {
      critical: number;
      errors: number;
      warnings: number;
      info: number;
      blocking: boolean;
      total: number;
    };
    issues: Array<{ id: string; severity: string; message: string; status: string }>;
  }>(`/api/projects/${projectId}/validate`, { method: "POST", body: "{}" });
}

export function getValidationSummary(projectId: string) {
  return request<{
    critical: number;
    errors: number;
    warnings: number;
    info: number;
    blocking: boolean;
    total: number;
  }>(`/api/projects/${projectId}/validation/summary`);
}

export function createResearchCase(projectId: string) {
  return request(`/api/projects/${projectId}/research-case`, {
    method: "POST",
    body: JSON.stringify({ status: "NEW" }),
  });
}

export function getResearchCase(projectId: string) {
  return request(`/api/projects/${projectId}/research-case`);
}

export function listResearchTasks(projectId: string) {
  return request<Array<{ id: string; task_type: string; status: string }>>(
    `/api/projects/${projectId}/research-case/tasks`,
  );
}

export function listResearchEvidence(projectId: string) {
  return request<Array<{ id: string; evidence_type: string; verification_status: string }>>(
    `/api/projects/${projectId}/research-case/evidence`,
  );
}

export function listResearchConflicts(projectId: string) {
  return request<Array<{ id: string; field_name: string; severity: string }>>(
    `/api/projects/${projectId}/research-case/conflicts`,
  );
}

export function upsertResearchProfile(projectId: string, body: Record<string, unknown>) {
  return request(`/api/projects/${projectId}/research-profile`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function generateResearchTasks(projectId: string) {
  return request<Array<{ id: string; task_type: string; status: string; depends_on_tasks: string[] }>>(
    `/api/projects/${projectId}/research-case/tasks/generate`,
    { method: "POST", body: "{}" },
  );
}

export function listDocuments(projectId: string) {
  return request<Array<{ id: string; filename: string; status: string; checksum: string }>>(
    `/api/projects/${projectId}/documents`,
  );
}

export async function uploadDocument(projectId: string, file: File, sourceType = "OTHER") {
  const form = new FormData();
  form.append("file", file);
  form.append("source_type", sourceType);
  const headers = new Headers();
  const token = getAuthToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}/api/projects/${projectId}/documents`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!response.ok) {
    const body = await response.text();
    if (response.status === 401) clearAuthToken();
    throw new ApiError(response.status, body, extractErrorCode(body));
  }
  return response.json();
}

export function ingestDocument(projectId: string, documentId: string) {
  return request(`/api/projects/${projectId}/documents/${documentId}/ingest`, {
    method: "POST",
    body: "{}",
  });
}

export function researchSearch(projectId: string, query: string) {
  return request<Array<{ snippet: string; page: number; document_id: string }>>(
    `/api/projects/${projectId}/research/search`,
    { method: "POST", body: JSON.stringify({ query }) },
  );
}

export function createManualEvidence(projectId: string, body: Record<string, unknown>) {
  return request(`/api/projects/${projectId}/research/evidence`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function researchCompleteness(projectId: string) {
  return request<{ score: number; missing_evidence: string[]; conflicts: number }>(
    `/api/projects/${projectId}/research/completeness`,
    { method: "POST", body: "{}" },
  );
}

export type AIProposedClaim = {
  claim_id: string | null;
  evidence_id: string | null;
  field_name: string;
  value: string;
  normalized_value: Record<string, unknown> | null;
  unit: string | null;
  source_id: string;
  document_id: string;
  page: number | string;
  chunk_id: string;
  evidence_text: string;
  confidence: number;
  status: string;
  origin: string;
  model?: string | null;
};

export function aiStatus() {
  return request<{
    enabled: boolean;
    provider: string;
    model: string | null;
    available: boolean;
    detail?: string | null;
  }>("/api/ai/status");
}

export type AiSettingsView = {
  enabled: boolean;
  provider: string;
  model: string;
  base_url: string;
  api_key_configured: boolean;
  api_key_masked: string | null;
  runtime_override: boolean;
  updated_at: string | null;
  assistive_only: boolean;
  cannot_approve_decisions: boolean;
  default_cloud_model: string;
  status?: {
    enabled: boolean;
    provider: string;
    model: string | null;
    available: boolean;
    detail?: string | null;
  };
  saved?: boolean;
};

const AI_KEY_STORAGE = "be_ai_api_key";

export function getStoredAiApiKey(): string | null {
  try {
    return sessionStorage.getItem(AI_KEY_STORAGE);
  } catch {
    return null;
  }
}

export function setStoredAiApiKey(key: string | null): void {
  try {
    if (!key) sessionStorage.removeItem(AI_KEY_STORAGE);
    else sessionStorage.setItem(AI_KEY_STORAGE, key);
  } catch {
    /* ignore */
  }
}

export function clearStoredAiApiKey(): void {
  setStoredAiApiKey(null);
}

export function getAiSettings() {
  return request<AiSettingsView>("/api/ai/settings");
}

export function updateAiSettings(body: {
  enabled?: boolean;
  api_key?: string;
  clear_api_key?: boolean;
  provider?: string;
  model?: string;
  base_url?: string;
}) {
  return request<AiSettingsView>("/api/ai/settings", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function aiExtract(
  projectId: string,
  body: {
    task_type: string;
    query?: string;
    document_ids?: string[];
    limit_chunks?: number;
    force_mock?: boolean;
  },
) {
  return request<{
    run: { id: string; status: string; prompt_version: string; provider: string; model: string | null };
    claims: AIProposedClaim[];
    conflicts_detected: number;
  }>(`/api/projects/${projectId}/ai/extract`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listAiProposed(projectId: string) {
  return request<AIProposedClaim[]>(`/api/projects/${projectId}/ai/proposed`);
}

export function reviewAiClaim(
  projectId: string,
  claimId: string,
  body: {
    action: "verify" | "reject" | "edit_verify";
    edited_value?: string;
    edited_normalized_value?: Record<string, unknown>;
    analyte_id?: string;
  },
) {
  return request(`/api/projects/${projectId}/ai/claims/${claimId}/review`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type ProtocolPreviewNode = {
  section_code: string;
  title: string;
  status: string;
  generation_status: string;
  content_blocks: Array<Record<string, unknown>>;
  source_ids: string[];
  warnings: string[];
  children: ProtocolPreviewNode[];
};

export function buildProtocol(projectId: string) {
  return request<{
    id: string;
    status: string;
    template_version: string;
    generator_version: string;
    sections: unknown[];
    tables: Array<{ table_key: string; display_number: number | null; title: string }>;
    build_report: {
      unresolved_fields: string[];
      blocking_issues: unknown[];
      warnings: string[];
      generated_sections: string[];
      source_count: number;
    };
  }>(`/api/projects/${projectId}/protocol/build`, {
    method: "POST",
    body: "{}",
  });
}

export function getProtocolPreview(projectId: string) {
  return request<{
    protocol_id: string;
    status: string;
    tree: ProtocolPreviewNode[];
    tables: Array<{
      table_key: string;
      title: string;
      display_number: number | null;
      columns: string[];
      rows: unknown[][];
    }>;
    unresolved_fields: string[];
    blocking_issues: unknown[];
    warnings: string[];
  }>(`/api/projects/${projectId}/protocol/preview`);
}

export function getProtocolBuildReport(projectId: string) {
  return request<{
    generated_sections: string[];
    unresolved_fields: string[];
    blocking_issues: unknown[];
    warnings: string[];
    source_count: number;
    calculated_values: unknown[];
  }>(`/api/projects/${projectId}/protocol/build-report`);
}

export function buildDocx(projectId: string, mode: "DRAFT" | "REVIEW" | "FINAL" = "DRAFT") {
  return request<{
    id: string;
    status: string;
    mode: string;
    filename: string | null;
    checksum: string | null;
    template_version: string | null;
    protocol_version: string | null;
    generator_version: string | null;
    validation_report: Record<string, unknown> | null;
    blocking_reasons: string[];
  }>(`/api/projects/${projectId}/protocol/docx/build`, {
    method: "POST",
    body: JSON.stringify({ mode, ensure_protocol: true }),
  });
}

export function getDocxStatus(projectId: string) {
  return request<{
    latest: {
      id: string;
      status: string;
      mode: string;
      filename: string | null;
      template_version: string | null;
      generator_version: string | null;
      blocking_reasons: string[];
    } | null;
    template_version: string;
    generator_version: string;
    profile_version: string;
  }>(`/api/projects/${projectId}/protocol/docx/status`);
}

export function getDocxValidation(projectId: string) {
  return request<{
    document_id: string | null;
    status: string;
    validation: Record<string, unknown>;
    blocking_reasons: string[];
  }>(`/api/projects/${projectId}/protocol/docx/validation`);
}

export function downloadDocxUrl(projectId: string) {
  return `${API_BASE}/api/projects/${projectId}/protocol/docx/download`;
}

export type ExpertDecision = {
  id: string;
  project_id: string;
  decision_type: string;
  target_entity_type: string;
  proposed_value: Record<string, unknown>;
  final_value: Record<string, unknown> | null;
  rationale: string;
  status: string;
  decided_by: string | null;
};

export type KnowledgeGap = {
  id: string;
  project_id: string | null;
  domain: string;
  question: string;
  description: string | null;
  importance: string;
  blocking: boolean;
  status: string;
};

export function seedKnowledgeRules(projectId?: string) {
  const q = projectId ? `?project_id=${projectId}` : "";
  return request<Record<string, unknown>[]>(`/api/knowledge-rules/seed${q}`, { method: "POST" });
}

export function listExpertDecisions(projectId: string) {
  return request<ExpertDecision[]>(`/api/expert-decisions?project_id=${projectId}`);
}

export function approveExpertDecision(id: string, decidedBy = "ui-expert") {
  return request<ExpertDecision>(`/api/expert-decisions/${id}/approve`, {
    method: "POST",
    body: JSON.stringify({ decided_by: decidedBy }),
  });
}

export function rejectExpertDecision(id: string, decidedBy = "ui-expert", rationale?: string) {
  return request<ExpertDecision>(`/api/expert-decisions/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ decided_by: decidedBy, rationale }),
  });
}

export function listKnowledgeGaps(projectId: string, status?: string) {
  const q = status ? `&status=${status}` : "";
  return request<KnowledgeGap[]>(`/api/knowledge-gaps?project_id=${projectId}${q}`);
}

export function resolveKnowledgeGap(id: string, resolution: string, resolvedBy = "ui-expert") {
  return request<KnowledgeGap>(`/api/knowledge-gaps/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolution, resolved_by: resolvedBy }),
  });
}

export function proposeDesignKnowledge(projectId: string, body: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>(`/api/projects/${projectId}/design/propose`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function createExpertDecision(body: Record<string, unknown>) {
  return request<ExpertDecision>(`/api/expert-decisions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getProcedureSchedule(projectId: string) {
  return request<Record<string, unknown>>(`/api/projects/${projectId}/procedure-schedule`);
}

export function proposeBioanalysis(projectId: string, body: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>(`/api/projects/${projectId}/bioanalysis/propose`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function proposeSafetyPlan(projectId: string, body: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>(`/api/projects/${projectId}/safety-plan/propose`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getContentMatrix(projectId: string) {
  return request<{ count: number; rows: Array<Record<string, unknown>>; version: string }>(
    `/api/projects/${projectId}/content-matrix`,
  );
}

export function resolveProjectContent(projectId: string, body: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>(`/api/projects/${projectId}/content/resolve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Phase 13.1 — Regulatory Evidence (approve does not mutate Study) */
export function getRegulatoryEvidenceMeta() {
  return request<Record<string, unknown>>(`/api/regulatory-evidence/meta`);
}

export function getRegulatoryManifest() {
  return request<Record<string, unknown>>(`/api/regulatory-evidence/manifest`);
}

export function getRegulatoryCoverage() {
  return request<Record<string, unknown>>(`/api/regulatory-evidence/coverage`);
}

export function getRegulatoryReviewQueue() {
  return request<{ queue_id: string; items: Array<Record<string, unknown>> }>(
    `/api/regulatory-evidence/review-queue`,
  );
}

export function runRegulatoryEvidencePipeline(body: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>(`/api/regulatory-evidence/pipeline/run`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function regulatoryReviewAction(
  itemId: string,
  body: { claim_id: string; action: string; rule_code?: string; reviewer?: string },
) {
  return request<Record<string, unknown>>(`/api/regulatory-evidence/review-queue/${itemId}/action`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listRegulatorySources(projectId?: string) {
  const q = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
  return request<Record<string, unknown>>(`/api/regulatory-evidence/sources${q}`);
}

export function getRegulatorySlots() {
  return request<{ slots: Array<Record<string, unknown>>; gaps: Array<Record<string, unknown>> }>(
    `/api/regulatory-evidence/slots`,
  );
}

export function getRegulatoryClaim(claimId: string) {
  return request<Record<string, unknown>>(`/api/regulatory-evidence/claims/${claimId}`);
}

export function verifyRegulatoryClaim(claimId: string, body: { reviewer: string; notes?: string }) {
  return request<Record<string, unknown>>(`/api/regulatory-evidence/claims/${claimId}/verify`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function rejectRegulatoryClaim(claimId: string, body: { reviewer: string; notes?: string }) {
  return request<Record<string, unknown>>(`/api/regulatory-evidence/claims/${claimId}/reject`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function runDecision85Pipeline(body: {
  verify_first_batch?: boolean;
  reviewer?: string;
  project_id?: string;
} = {}) {
  return request<Record<string, unknown>>(`/api/regulatory-evidence/decision85/pipeline`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function importDecision85() {
  return request<Record<string, unknown>>(`/api/regulatory-evidence/decision85/import`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function listDecision85Claims() {
  return request<{
    claims: Array<Record<string, unknown>>;
    verified: Array<Record<string, unknown>>;
    proposed: Array<Record<string, unknown>>;
  }>(`/api/regulatory-evidence/decision85/claims`);
}

/** Phase 14 — Study Input Package (extraction never mutates Study) */
export function loadStudyInputRealFixture() {
  return request<Record<string, unknown>>(`/api/study-input/fixtures/updcb-real/load`, {
    method: "POST",
    body: "{}",
  });
}

export function getStudyInputPackage(packageId: string) {
  return request<Record<string, unknown>>(`/api/study-input/packages/${packageId}`);
}

export function getStudyInputCoverage(packageId: string) {
  return request<Record<string, unknown>>(`/api/study-input/packages/${packageId}/coverage`);
}

export function getStudyInputConflicts(packageId: string) {
  return request<Array<Record<string, unknown>>>(`/api/study-input/packages/${packageId}/conflicts`);
}

export function getStudyInputCandidates(packageId: string) {
  return request<Array<Record<string, unknown>>>(`/api/study-input/packages/${packageId}/candidates`);
}

export function getStudyInputReadiness(packageId: string) {
  return request<Record<string, unknown>>(`/api/study-input/packages/${packageId}/readiness`);
}

export function getStudyInputMissing(packageId: string) {
  return request<{
    knowledge_gaps: Array<Record<string, unknown>>;
    research_tasks: Array<Record<string, unknown>>;
  }>(`/api/study-input/packages/${packageId}/missing`);
}

export function reviewStudyInputCandidate(
  packageId: string,
  candidateId: string,
  body: { action: "VERIFY" | "REJECT"; reviewer: string; notes?: string },
) {
  return request<Record<string, unknown>>(
    `/api/study-input/packages/${packageId}/candidates/${candidateId}/review`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

/** Phase 15 — Decision Center (recommendations never mutate Study) */
export function recomputeDecisionCenterGolden() {
  return request<Record<string, unknown>>(`/api/decision-center/fixtures/updcb-real/recompute`, {
    method: "POST",
    body: "{}",
  });
}

export async function listStudyDecisions(studyId: string): Promise<DecisionsResponse> {
  const raw = await request<unknown>(`/api/decision-center/studies/${studyId}/decisions`);
  return parseDecisionsResponse(raw);
}

export function getDecisionEvidence(studyId: string, decisionId: string) {
  return request<Record<string, unknown>>(
    `/api/decision-center/studies/${studyId}/decisions/${decisionId}/evidence`,
  );
}

export function getDecisionDependencies(studyId: string, decisionId: string) {
  return request<Record<string, unknown>>(
    `/api/decision-center/studies/${studyId}/decisions/${decisionId}/dependencies`,
  );
}

export function getDecisionBlockers(studyId: string, decisionId: string) {
  return request<Record<string, unknown>>(
    `/api/decision-center/studies/${studyId}/decisions/${decisionId}/blockers`,
  );
}

export function getDecisionApplicability(studyId: string, decisionId: string) {
  return request<Record<string, unknown>>(
    `/api/decision-center/studies/${studyId}/decisions/${decisionId}/applicability`,
  );
}

export function keepCurrentDecisionValue(
  studyId: string,
  decisionId: string,
  body: { reviewer: string; rationale: string; current_fact_evidence_id?: string },
) {
  return request<Record<string, unknown>>(
    `/api/decision-center/studies/${studyId}/decisions/${decisionId}/keep-current`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function approveStudyDecision(
  studyId: string,
  decisionId: string,
  body: { reviewer: string; rationale: string; selected_option?: string; comment?: string },
) {
  return request<Record<string, unknown>>(
    `/api/decision-center/studies/${studyId}/decisions/${decisionId}/approve`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function rejectStudyDecision(
  studyId: string,
  decisionId: string,
  body: { reviewer: string; rationale: string },
) {
  return request<Record<string, unknown>>(
    `/api/decision-center/studies/${studyId}/decisions/${decisionId}/reject`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

/** Phase 15.2 — Research Center */
export function bootstrapResearchCenterGolden() {
  return request<Record<string, unknown>>(`/api/research-center/fixtures/updcb-real/bootstrap`, {
    method: "POST",
    body: "{}",
  });
}

export function listResearchCenterTasks(studyId: string) {
  return request<Record<string, unknown>>(`/api/research-center/studies/${studyId}/research-tasks`);
}

export function runResearchCenterTask(taskId: string, body?: { use_mock_provider?: boolean }) {
  return request<Record<string, unknown>>(`/api/research-center/research-tasks/${taskId}/run`, {
    method: "POST",
    body: JSON.stringify(body || { use_mock_provider: true }),
  });
}

export function getResearchCenterCoverage(studyId: string) {
  return request<Record<string, unknown>>(`/api/research-center/studies/${studyId}/coverage`);
}

export function runResearchCenterRealSearch(
  taskId: string,
  body?: {
    active_substance?: string;
    product?: string;
    dosage_form?: string;
    use_injected_mock_web?: boolean;
  },
) {
  return request<Record<string, unknown>>(
    `/api/research-center/research-tasks/${taskId}/run-real-search`,
    { method: "POST", body: JSON.stringify(body || {}) },
  );
}

export function registerResearchResultSource(
  resultId: string,
  body: { research_task_id: string; fetch_content?: boolean; mock_text?: string },
) {
  return request<Record<string, unknown>>(
    `/api/research-center/research-results/${resultId}/register-source`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

/** Phase 15.4 — Sample Size Engine (calculated ≠ approved; never mutates Study) */
export async function getSampleSizePanel(studyId: string): Promise<SampleSizePanel> {
  const raw = await request<unknown>(`/api/studies/${studyId}/sample-size/panel`);
  return parseSampleSizePanel(raw);
}

export function calculateStudySampleSize(studyId: string, body: Record<string, unknown>) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/sample-size/calculate`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listSampleSizeCalculations(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/sample-size/calculations`);
}

/** Phase 15.5 — Statistics Engine (method plan; recommendation ≠ approval) */
export async function getStudyStatistics(studyId: string): Promise<StatisticsResponse> {
  const raw = await request<unknown>(`/api/studies/${studyId}/statistics`);
  return parseStatisticsResponse(raw);
}

export function recomputeStudyStatistics(studyId: string, body: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/statistics/recompute`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function recomputeStatisticsGolden() {
  return request<Record<string, unknown>>(
    `/api/decision-center/fixtures/updcb-real/statistics/recompute`,
    { method: "POST", body: "{}" },
  );
}

/** Phase 16 — Study Workspace / E2E workflow */
export async function getStudyWorkspace(studyId: string): Promise<WorkspaceSummary> {
  const raw = await request<unknown>(`/api/studies/${studyId}/workspace`);
  return parseWorkspaceSummary(raw);
}

export function getStudyReadiness(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/readiness`);
}

export function getStudyConflicts(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/conflicts`);
}

export async function getStudyPreflight(studyId: string): Promise<PreflightResponse> {
  const raw = await request<unknown>(`/api/studies/${studyId}/preflight`);
  return parsePreflightResponse(raw);
}

export function getStudyAudit(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/audit`);
}

export async function runStudyWorkflow(
  studyId: string,
  body: Record<string, unknown> = {},
): Promise<WorkflowResponse> {
  const raw = await request<unknown>(`/api/studies/${studyId}/workflow/run`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return parseWorkflowResponse(raw);
}

export function getBetaCases() {
  return request<Record<string, unknown>>(`/api/beta/cases`);
}

export function evaluateBetaCase(caseId: string) {
  return request<Record<string, unknown>>(`/api/beta/cases/${caseId}/evaluate`, {
    method: "POST",
    body: "{}",
  });
}

export function getWriterReview(studyId: string, field?: string) {
  const q = field ? `?field=${encodeURIComponent(field)}` : "";
  return request<Record<string, unknown>>(`/api/beta/studies/${studyId}/writer-review${q}`);
}

/** Phase 26 — Writer workspace APIs (no Legacy required) */
export function createWorkspaceStudy(body: {
  study_key?: string;
  title?: string;
  sponsor?: string;
  product?: string;
  dose?: string;
  is_demo?: boolean;
}) {
  return request<{
    study_key: string;
    title?: string | null;
    sponsor?: string | null;
    product?: string | null;
    dose?: string | null;
    is_demo: boolean;
    next: string;
    legacy_required: boolean;
  }>(`/api/studies/create`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listWorkspaceDocuments(studyId: string) {
  return request<{ study_id: string; documents: Array<Record<string, unknown>> }>(
    `/api/studies/${studyId}/documents`,
  );
}

export async function uploadWorkspaceDocument(
  studyId: string,
  file: File,
  documentType = "OTHER",
) {
  const form = new FormData();
  form.append("file", file);
  form.append("document_type", documentType);
  const headers = new Headers();
  const token = getAuthToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_BASE}/api/studies/${studyId}/documents/upload`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!response.ok) {
    const body = await response.text();
    if (response.status === 401) clearAuthToken();
    throw new ApiError(response.status, body, extractErrorCode(body));
  }
  return response.json() as Promise<Record<string, unknown>>;
}

export function reviewCanonicalFact(
  studyId: string,
  body: {
    field: string;
    old_value?: unknown;
    new_value?: unknown;
    reason: string;
    actor?: string;
    action?: "REVIEW" | "EDIT_PROPOSAL";
  },
) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/canonical-facts/review`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function requestDecisionEvidence(
  studyId: string,
  body: { decision_id?: string; question?: string; reason: string; actor?: string },
) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/decisions/request-evidence`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function postExpertDecision(
  studyId: string,
  body: {
    question: string;
    selected_option: string;
    rationale: string;
    evidence_refs?: string[];
    decision_id?: string;
    status?: string;
  },
) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/decisions/expert`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function modifyStudyDecision(
  studyId: string,
  decisionId: string,
  body: { reviewer: string; rationale: string; selected_option: string },
) {
  return request<Record<string, unknown>>(
    `/api/decision-center/studies/${studyId}/decisions/${decisionId}/modify`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function getWorkspaceProtocolPreview(studyId: string): Promise<ProtocolPreview> {
  const raw = await request<unknown>(`/api/studies/${studyId}/protocol/preview`);
  return parseProtocolPreview(raw);
}

export function generateWorkspaceDocx(studyId: string, confirmWarnings = false) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/protocol/generate-docx`, {
    method: "POST",
    body: JSON.stringify({ confirm_warnings: confirmWarnings }),
  });
}

export function listProtocolDrafts(studyId: string) {
  return request<{ drafts: Array<Record<string, unknown>> }>(
    `/api/studies/${studyId}/protocol-drafts`,
  );
}

export function approveSampleSizeCalculation(
  calculationId: string,
  body: { reviewer: string; decision: string; comment?: string; project_to_study?: boolean },
) {
  return request<Record<string, unknown>>(`/api/sample-size/calculations/${calculationId}/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function approveStatisticsPlan(
  planId: string,
  body: { reviewer: string; comment?: string },
) {
  return request<Record<string, unknown>>(`/api/statistics/${planId}/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function resolveApiBasePublic(): string {
  return API_BASE;
}

/** Phase 27 — guided writer workflow */
export async function getWriterProgress(studyId: string): Promise<WriterProgress> {
  const raw = await request<unknown>(`/api/studies/${studyId}/writer-progress`);
  return parseWriterProgress(raw);
}

export function getCanonicalFactDetail(studyId: string, field: string) {
  const enc = encodeURIComponent(field);
  return request<Record<string, unknown>>(`/api/studies/${studyId}/canonical-facts/${enc}/detail`);
}

export function classifyWorkspaceDocument(
  studyId: string,
  documentId: string,
  documentType: string,
  actor = "writer",
) {
  return request<Record<string, unknown>>(
    `/api/studies/${studyId}/documents/${documentId}/classify`,
    { method: "POST", body: JSON.stringify({ document_type: documentType, actor }) },
  );
}

export async function listWorkspaceArtifacts(studyId: string): Promise<ArtifactsResponse> {
  const raw = await request<unknown>(`/api/studies/${studyId}/protocol/artifacts`);
  return parseArtifactsResponse(raw);
}

export function downloadWorkspaceArtifactUrl(studyId: string, artifactId: string) {
  return `${API_BASE}/api/studies/${studyId}/protocol/artifacts/${artifactId}/download`;
}

export function listWorkspaceSnapshots(studyId: string) {
  return request<{ snapshots: Array<Record<string, unknown>> }>(
    `/api/studies/${studyId}/snapshots`,
  );
}


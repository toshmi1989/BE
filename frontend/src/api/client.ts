export function resolveApiBase(): string {
  const explicit = import.meta.env.VITE_API_BASE_URL;
  if (explicit != null && String(explicit).trim() !== "") {
    return String(explicit).replace(/\/$/, "");
  }
  if (import.meta.env.DEV) return "http://localhost:8000";
  return String(import.meta.env.BASE_URL || "/").replace(/\/$/, "");
}

const API_BASE = resolveApiBase();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`HTTP ${response.status}: ${body}`);
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
  const response = await fetch(
    `${API_BASE}/api/projects/${projectId}/documents`,
    { method: "POST", body: form },
  );
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${await response.text()}`);
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

export function listStudyDecisions(studyId: string) {
  return request<Record<string, unknown>>(`/api/decision-center/studies/${studyId}/decisions`);
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
export function getSampleSizePanel(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/sample-size/panel`);
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
export function getStudyStatistics(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/statistics`);
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
export function getStudyWorkspace(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/workspace`);
}

export function getStudyReadiness(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/readiness`);
}

export function getStudyConflicts(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/conflicts`);
}

export function getStudyPreflight(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/preflight`);
}

export function getStudyAudit(studyId: string) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/audit`);
}

export function runStudyWorkflow(studyId: string, body: Record<string, unknown> = {}) {
  return request<Record<string, unknown>>(`/api/studies/${studyId}/workflow/run`, {
    method: "POST",
    body: JSON.stringify(body),
  });
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


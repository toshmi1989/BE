import { useEffect, useState } from "react";
import {
  calculateBloodVolume,
  calculateObservation,
  calculateSampleSize,
  calculateWashout,
  createAnalyte,
  createCvStudy,
  createProject,
  createResearchCase,
  fetchHealth,
  generateResearchTasks,
  getDesignReference,
  getProject,
  getResearchCase,
  getStatisticsConfig,
  getValidationSummary,
  listDocuments,
  listProjects,
  listResearchConflicts,
  listResearchEvidence,
  listResearchTasks,
  recommendDesign,
  recommendSampling,
  replaceEligibility,
  researchCompleteness,
  runProjectValidation,
  saveClientInput,
  saveDesign,
  saveFood,
  saveSubjects,
  selectCv,
  upsertResearchProfile,
  validateSampling,
  validateStatistics,
  aiStatus,
  aiExtract,
  listAiProposed,
  reviewAiClaim,
  buildProtocol,
  getProtocolPreview,
  getProtocolBuildReport,
  buildDocx,
  getDocxStatus,
  getDocxValidation,
  downloadDocxUrl,
  seedKnowledgeRules,
  listExpertDecisions,
  listKnowledgeGaps,
  approveExpertDecision,
  rejectExpertDecision,
  resolveKnowledgeGap,
  proposeDesignKnowledge,
  createExpertDecision,
  getProcedureSchedule,
  proposeBioanalysis,
  proposeSafetyPlan,
  getContentMatrix,
  resolveProjectContent,
  getRegulatoryManifest,
  getRegulatoryCoverage,
  getRegulatoryReviewQueue,
  runRegulatoryEvidencePipeline,
  regulatoryReviewAction,
  loadStudyInputRealFixture,
  getStudyInputCoverage,
  getStudyInputConflicts,
  getStudyInputCandidates,
  getStudyInputReadiness,
  getStudyInputMissing,
  reviewStudyInputCandidate,
  recomputeDecisionCenterGolden,
  listStudyDecisions,
  bootstrapResearchCenterGolden,
  listResearchCenterTasks,
  runResearchCenterTask,
  runResearchCenterRealSearch,
  getResearchCenterCoverage,
  getSampleSizePanel,
  calculateStudySampleSize,
  recomputeStatisticsGolden,
  type DesignRecommendResult,
  type HealthPayload,
  type ProjectDetail,
  type ProjectSummary,
  type AIProposedClaim,
  type ProtocolPreviewNode,
  type ExpertDecision,
  type KnowledgeGap,
} from "../api/client";

function ProvenanceBadge({ status }: { status: string }) {
  return <span className="badge">{status}</span>;
}

/**
 * Thin UI over project API — no domain calculations / protocol text.
 */
export function Dashboard() {
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [selected, setSelected] = useState<ProjectDetail | null>(null);
  const [name, setName] = useState("Новый проект БЭ");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [recommend, setRecommend] = useState<DesignRecommendResult | null>(null);
  const [designTemplates, setDesignTemplates] = useState<Record<string, Record<string, unknown>>>({});
  const [validationSummary, setValidationSummary] = useState<{
    critical: number;
    errors: number;
    warnings: number;
    info: number;
    blocking: boolean;
    total: number;
  } | null>(null);
  const [researchMeta, setResearchMeta] = useState<{
    status: string;
    tasks: number;
    evidence: number;
    conflicts: number;
    documents: number;
    score: number | null;
  } | null>(null);
  const [expertDecisions, setExpertDecisions] = useState<ExpertDecision[]>([]);
  const [knowledgeGaps, setKnowledgeGaps] = useState<KnowledgeGap[]>([]);
  const [designProposal, setDesignProposal] = useState<Record<string, unknown> | null>(null);
  const [contentMeta, setContentMeta] = useState<{
    scheduleCount: number | null;
    matrixCount: number | null;
    bioStatus: string | null;
    safetyGaps: number | null;
    resolveNote: string | null;
  } | null>(null);
  const [regulatoryMeta, setRegulatoryMeta] = useState<{
    packageStatus: string;
    sourcesMissing: number;
    claims: number;
    verified: number;
    proposed: number;
    gaps: number;
    reviewPending: number;
    note: string;
  } | null>(null);
  const [studyInputMeta, setStudyInputMeta] = useState<{
    packageId: string;
    status: string;
    docs: string[];
    coverage: Array<{ domain: string; state: string }>;
    conflicts: Array<{ field: string; values: string[] }>;
    gaps: number;
    tasks: number;
    readyGreen: boolean;
    message: string;
    candidates: number;
  } | null>(null);
  const [decisionCenterMeta, setDecisionCenterMeta] = useState<{
    studyId: string;
    decisions: Array<{
      domain_label: string;
      status: string;
      recommendation_option?: string | null;
      recommendation_status?: string | null;
      approved: boolean;
      blocking: string[];
      nonBlocking: string[];
    }>;
    blocking: string[];
    note: string;
  } | null>(null);
  const [researchCenterMeta, setResearchCenterMeta] = useState<{
    studyId: string;
    tasks: Array<{
      label: string;
      status: string;
      priority: string;
      gap: string;
      claims?: number;
      conflicts?: number;
      query?: string;
      results?: Array<{ title: string; priority: string; url: string }>;
    }>;
    note: string;
  } | null>(null);
  const [sampleSizeMeta, setSampleSizeMeta] = useState<{
    studyId: string;
    currentN: number | null;
    calculatedN: number | null;
    requiredN: number | null;
    status: string;
    discrepancy: boolean;
    controlling: string;
    scenarios: Array<{ parameter: string; required_n: number | null; power?: number | null }>;
    evidence: Array<{ parameter: string; cv: string; verification: string; applicability: string }>;
    blockers: string[];
    note: string;
  } | null>(null);
  const [statisticsMeta, setStatisticsMeta] = useState<{
    studyId: string;
    status: string;
    parameters: Array<{
      parameter: string;
      role: string;
      transform: string;
      model: string | null;
      ci: string | null;
      acceptance: string | null;
    }>;
    warning: string | null;
    blockers: string[];
    note: string;
  } | null>(null);
  const [aiClaims, setAiClaims] = useState<AIProposedClaim[]>([]);
  const [aiTask, setAiTask] = useState("EXTRACT_PK");
  const [aiStatusMeta, setAiStatusMeta] = useState<{
    enabled: boolean;
    provider: string;
    model: string | null;
    available: boolean;
  } | null>(null);
  const [protocolPreview, setProtocolPreview] = useState<{
    status: string;
    tree: ProtocolPreviewNode[];
    unresolved_fields: string[];
    blocking_issues: unknown[];
    warnings: string[];
    tables: Array<{
      table_key: string;
      title: string;
      display_number: number | null;
      columns: string[];
      rows: unknown[][];
    }>;
  } | null>(null);
  const [protocolReport, setProtocolReport] = useState<{
    generated_sections: string[];
    unresolved_fields: string[];
    blocking_issues: unknown[];
    warnings: string[];
    source_count: number;
  } | null>(null);
  const [docxMeta, setDocxMeta] = useState<{
    status: string;
    mode: string;
    template_version: string;
    generator_version: string;
    blocking_reasons: string[];
    filename: string | null;
  } | null>(null);
  const [docxMode, setDocxMode] = useState<"DRAFT" | "REVIEW" | "FINAL">("DRAFT");


  // Local form state (display/edit only — validation happens on backend)
  const [clientForm, setClientForm] = useState({
    requested_product_name: "",
    inn: "",
    dosage: "",
    dosage_form: "",
    route: "",
    requested_subject_count: "",
  });
  const [designType, setDesignType] = useState("CROSSOVER_2X2");
  const [foodCondition, setFoodCondition] = useState("FED");
  const [mealType, setMealType] = useState("HIGH_CALORIE");
  const [subjectsForm, setSubjectsForm] = useState({
    target_evaluable_n: "",
    planned_randomized_n: "",
    reserve_n: "",
    planned_screened_n: "",
  });
  const [inclusionText, setInclusionText] = useState("Healthy volunteers");

  async function refreshList() {
    const rows = await listProjects();
    setProjects(rows);
  }

  function hydrateForms(project: ProjectDetail) {
    setClientForm({
      requested_product_name: project.client_input?.requested_product_name ?? "",
      inn: project.client_input?.inn ?? "",
      dosage: project.client_input?.dosage ?? "",
      dosage_form: project.client_input?.dosage_form ?? "",
      route: project.client_input?.route ?? "",
      requested_subject_count:
        project.client_input?.requested_subject_count != null
          ? String(project.client_input.requested_subject_count)
          : "",
    });
    setDesignType(project.design?.type ?? "CROSSOVER_2X2");
    setFoodCondition(project.food?.condition ?? project.design?.food_condition ?? "FED");
    setMealType(project.food?.meal_type ?? "HIGH_CALORIE");
    setSubjectsForm({
      target_evaluable_n:
        project.subjects?.target_evaluable_n != null ? String(project.subjects.target_evaluable_n) : "",
      planned_randomized_n:
        project.subjects?.planned_randomized_n != null
          ? String(project.subjects.planned_randomized_n)
          : "",
      reserve_n: project.subjects?.reserve_n != null ? String(project.subjects.reserve_n) : "",
      planned_screened_n:
        project.subjects?.planned_screened_n != null
          ? String(project.subjects.planned_screened_n)
          : "",
    });
    setInclusionText(project.eligibility?.inclusion?.[0]?.text ?? "Healthy volunteers");
    setRecommend(null);
    setValidationSummary(null);
    setResearchMeta(null);
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchHealth(), listProjects(), getDesignReference()])
      .then(([h, rows, ref]) => {
        if (!cancelled) {
          setHealth(h);
          setProjects(rows);
          setDesignTemplates(ref.templates);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "API unavailable");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function onCreate() {
    setBusy(true);
    setError(null);
    try {
      const project = await createProject(name.trim() || "Untitled");
      await refreshList();
      setSelected(project);
      hydrateForms(project);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function onOpen(id: string) {
    setBusy(true);
    setError(null);
    try {
      const project = await getProject(id);
      setSelected(project);
      hydrateForms(project);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setBusy(false);
    }
  }

  async function reloadSelected(id: string) {
    const project = await getProject(id);
    setSelected(project);
    hydrateForms(project);
  }

  function optionalInt(value: string): number | null {
    if (value.trim() === "") return null;
    return Number(value);
  }

  async function onSaveClientInput() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await saveClientInput(
        selected.id,
        {
          ...clientForm,
          requested_subject_count: optionalInt(clientForm.requested_subject_count),
          provenance: { origin: "USER", status: "PROPOSED" },
        },
        Boolean(selected.client_input),
      );
      await reloadSelected(selected.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Client input save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveDesign() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const template = designTemplates[designType] ?? {};
      const body = {
        type: designType,
        ...template,
        food_condition: foodCondition,
        decision_status: "PROPOSED",
        provenance: { origin: "USER", status: "PROPOSED" },
      };
      await saveDesign(selected.id, body, Boolean(selected.design));
      await reloadSelected(selected.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Design save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onRecommendDesign() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const result = await recommendDesign(selected.id, {
        dosage_form: clientForm.dosage_form || null,
        route: clientForm.route || null,
        food_condition: foodCondition,
        reference_product_known: Boolean(selected.reference_product),
        persist: false,
      });
      setRecommend(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Recommend failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveFood() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await saveFood(
        selected.id,
        {
          condition: foodCondition,
          meal_type: foodCondition === "FASTING" ? null : mealType,
          provenance: { origin: "USER", status: "PROPOSED" },
          decision_status: "PROPOSED",
        },
        Boolean(selected.food),
      );
      await reloadSelected(selected.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Food save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveEligibility() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await replaceEligibility(selected.id, {
        inclusion: [{ id: "", number: 1, text: inclusionText }],
        non_inclusion: selected.eligibility?.non_inclusion ?? [],
        exclusion: selected.eligibility?.exclusion ?? [],
      });
      await reloadSelected(selected.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Eligibility save failed");
    } finally {
      setBusy(false);
    }
  }

  async function onSaveSubjects() {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      await saveSubjects(
        selected.id,
        {
          target_evaluable_n: optionalInt(subjectsForm.target_evaluable_n),
          planned_randomized_n: optionalInt(subjectsForm.planned_randomized_n),
          reserve_n: optionalInt(subjectsForm.reserve_n),
          planned_screened_n: optionalInt(subjectsForm.planned_screened_n),
          provenance: { origin: "USER", status: "PROPOSED" },
        },
        Boolean(selected.subjects),
      );
      await reloadSelected(selected.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Subjects save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="dashboard">
      <h1>Projects</h1>
      <p className="muted">
        Phase 3: Analytes / PK / Washout / Observation / Sampling / Blood Volume. Calculations on API only.
      </p>

      <div className="status-panel">
        <h2>API</h2>
        {error && <p className="error">{error}</p>}
        {health && (
          <ul>
            <li>Service: {health.service}</li>
            <li>Version: {health.version}</li>
            <li>AI: {health.ai_enabled ? "on" : "off"}</li>
          </ul>
        )}
      </div>

      <div className="status-panel">
        <h2>Create project</h2>
        <div className="row">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Project name"
            disabled={busy}
          />
          <button type="button" onClick={onCreate} disabled={busy}>
            Create
          </button>
        </div>
      </div>

      <div className="status-panel">
        <h2>Project list</h2>
        {projects.length === 0 ? (
          <p className="muted">No projects yet.</p>
        ) : (
          <ul className="project-list">
            {projects.map((p) => (
              <li key={p.id}>
                <button type="button" className="linkish" onClick={() => onOpen(p.id)} disabled={busy}>
                  {p.name}
                </button>
                <span className="muted">
                  {" "}
                  · {p.status} · v{p.entity_version}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {selected && (
        <>
          <div className="status-panel">
            <h2>{selected.name}</h2>
            <p className="muted">id: {selected.id}</p>
          </div>

          <div className="status-panel">
            <h2>Client Input</h2>
            <div className="grid-form">
              {(
                [
                  ["requested_product_name", "Product name"],
                  ["inn", "INN"],
                  ["dosage", "Dosage"],
                  ["dosage_form", "Dosage form"],
                  ["route", "Route"],
                  ["requested_subject_count", "Requested N"],
                ] as const
              ).map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    value={clientForm[key]}
                    onChange={(e) => setClientForm({ ...clientForm, [key]: e.target.value })}
                    disabled={busy}
                  />
                </label>
              ))}
            </div>
            <div className="row">
              <button type="button" onClick={onSaveClientInput} disabled={busy}>
                Save client input
              </button>
              {selected.client_input && (
                <ProvenanceBadge status={selected.client_input.provenance.status} />
              )}
            </div>
          </div>

          <div className="status-panel">
            <h2>Design</h2>
            <div className="row">
              <select
                value={designType}
                onChange={(e) => setDesignType(e.target.value)}
                disabled={busy}
              >
                <option value="CROSSOVER_2X2">CROSSOVER_2X2</option>
                <option value="REPLICATE_2X2X4">REPLICATE_2X2X4</option>
                <option value="PARALLEL">PARALLEL</option>
                <option value="ADAPTIVE">ADAPTIVE</option>
                <option value="CUSTOM">CUSTOM</option>
              </select>
              <button type="button" onClick={onSaveDesign} disabled={busy}>
                Save design
              </button>
              <button type="button" onClick={onRecommendDesign} disabled={busy}>
                Recommend
              </button>
              {selected.design && <ProvenanceBadge status={selected.design.decision_status} />}
            </div>
            {selected.design && (
              <p className="muted">
                Stored: {selected.design.type}, periods={String(selected.design.periods)}, food=
                {selected.design.food_condition ?? "—"}
              </p>
            )}
            {recommend && (
              <p className="muted">
                Recommendation: {recommend.status} / {recommend.recommended_design?.type ?? "none"} —{" "}
                {recommend.rationale}
              </p>
            )}
          </div>

          <div className="status-panel">
            <h2>Food</h2>
            <div className="row">
              <select
                value={foodCondition}
                onChange={(e) => setFoodCondition(e.target.value)}
                disabled={busy}
              >
                <option value="FASTING">FASTING</option>
                <option value="FED">FED</option>
                <option value="FASTING_AND_FED">FASTING_AND_FED</option>
                <option value="UNKNOWN">UNKNOWN</option>
              </select>
              <select value={mealType} onChange={(e) => setMealType(e.target.value)} disabled={busy}>
                <option value="HIGH_CALORIE">HIGH_CALORIE</option>
                <option value="STANDARD">STANDARD</option>
                <option value="LOW_CALORIE">LOW_CALORIE</option>
                <option value="CUSTOM">CUSTOM</option>
              </select>
              <button type="button" onClick={onSaveFood} disabled={busy}>
                Save food
              </button>
              {selected.food && <ProvenanceBadge status={selected.food.decision_status} />}
            </div>
          </div>

          <div className="status-panel">
            <h2>Eligibility</h2>
            <label>
              Inclusion #1 text
              <input
                value={inclusionText}
                onChange={(e) => setInclusionText(e.target.value)}
                disabled={busy}
              />
            </label>
            <div className="row">
              <button type="button" onClick={onSaveEligibility} disabled={busy}>
                Save eligibility
              </button>
            </div>
            {selected.eligibility && (
              <ul>
                <li>Inclusion: {selected.eligibility.inclusion.length}</li>
                <li>Non-inclusion: {selected.eligibility.non_inclusion.length}</li>
                <li>Exclusion: {selected.eligibility.exclusion.length}</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Subjects</h2>
            <div className="grid-form">
              {(
                [
                  ["target_evaluable_n", "Evaluable N"],
                  ["planned_randomized_n", "Randomized N"],
                  ["reserve_n", "Reserve N"],
                  ["planned_screened_n", "Screened N"],
                ] as const
              ).map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    value={subjectsForm[key]}
                    onChange={(e) => setSubjectsForm({ ...subjectsForm, [key]: e.target.value })}
                    disabled={busy}
                    placeholder="empty ≠ 0"
                  />
                </label>
              ))}
            </div>
            <div className="row">
              <button type="button" onClick={onSaveSubjects} disabled={busy}>
                Save subjects
              </button>
              {selected.subjects && (
                <ProvenanceBadge status={selected.subjects.provenance.status} />
              )}
            </div>
          </div>

          <div className="status-panel">
            <h2>Analytes</h2>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    await createAnalyte(selected.id, {
                      name: clientForm.inn || "parent-analyte",
                      type: "PARENT",
                      tmax_min: 2,
                      tmax_max: 3,
                      tmax_unit: "h",
                      half_life_min: 10,
                      half_life_max: 12,
                      half_life_unit: "h",
                      provenance: { origin: "USER", status: "PROPOSED" },
                    });
                    await reloadSelected(selected.id);
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Analyte failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Add parent analyte (2–3 h / t½ 10–12 h)
              </button>
            </div>
            <ul>
              {(selected.analytes ?? []).map((a) => (
                <li key={a.id}>
                  {a.name} ({a.type}) Tmax {a.tmax_min}–{a.tmax_max} · t½ {a.half_life_min}–
                  {a.half_life_max} <ProvenanceBadge status={a.provenance.status} />
                </li>
              ))}
            </ul>
          </div>

          <div className="status-panel">
            <h2>Washout / Observation</h2>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    await calculateWashout(selected.id, {
                      selected_value: 5,
                      selected_unit: "day",
                    });
                    await calculateObservation(selected.id, {
                      selected_duration: 36,
                      selected_unit: "h",
                    });
                    await reloadSelected(selected.id);
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "PK calc failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Calculate washout + observation
              </button>
            </div>
            <p className="muted">
              Washout: {selected.washout?.selected_value ?? "—"} {selected.washout?.unit ?? ""}{" "}
              (min {selected.washout?.calculated_minimum ?? "—"})
            </p>
            <p className="muted">
              Observation: {selected.observation?.selected_duration ?? "—"} h (min{" "}
              {selected.observation?.calculated_minimum ?? "—"})
            </p>
          </div>

          <div className="status-panel">
            <h2>Sampling</h2>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    await recommendSampling(selected.id);
                    await reloadSelected(selected.id);
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Sampling recommend failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Generate recommendation
              </button>
              <button
                type="button"
                disabled={busy || !selected.sampling}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const res = await validateSampling(selected.id);
                    setError(
                      res.blocking
                        ? `Validation blocking: ${res.issues.map((i) => i.code).join(", ")}`
                        : `Validation OK (${res.issues.length} notes)`,
                    );
                    await reloadSelected(selected.id);
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Validate failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Validate
              </button>
            </div>
            {selected.sampling && (
              <>
                <p className="muted">
                  Points/period: {selected.sampling.total_points_per_period} · override={" "}
                  {String(selected.sampling.manual_override)} · final=
                  {selected.sampling.final_observation_h} h
                </p>
                <table className="sampling-table">
                  <thead>
                    <tr>
                      <th>Time (h)</th>
                      <th>Reason</th>
                      <th>Window</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selected.sampling.points.map((p) => (
                      <tr key={p.id}>
                        <td>{p.time_h}</td>
                        <td>{p.reason}</td>
                        <td>
                          −{p.window_before_min ?? 0}/+{p.window_after_min ?? 0} min
                        </td>
                        <td>{p.provenance.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>

          <div className="status-panel">
            <h2>Blood Volume</h2>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    await calculateBloodVolume(selected.id, {
                      blood_volume_per_pk_sample_ml: 5,
                      screening_volume_ml: 15,
                      safety_laboratory_volume_ml: 10,
                    });
                    await reloadSelected(selected.id);
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Blood volume failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Calculate blood volume
              </button>
            </div>
            {selected.blood_volume && (
              <ul>
                <li>PK total: {selected.blood_volume.pk_volume_ml} ml</li>
                <li>Per subject: {selected.blood_volume.volume_per_subject_ml} ml</li>
                <li>Total: {selected.blood_volume.total_volume_ml} ml</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Statistics</h2>
            <p className="muted">CV Studies · CV Pooling · Selected CV · Sample Size · Validation</p>
            <div className="row">
              <button
                type="button"
                disabled={busy || !(selected.analytes ?? []).length}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const analyteId = selected.analytes![0].id;
                    const cv = (await createCvStudy(selected.id, {
                      source_id: "manual-demo",
                      analyte_id: analyteId,
                      parameter: "Cmax",
                      design: designType,
                      condition: foodCondition,
                      n_total: 46,
                      n_be_analysis: 40,
                      cv_value: 25,
                      evidence: [
                        {
                          source_id: "manual-demo",
                          section: "demo",
                          extracted_text: "UI demo CV — not verified",
                          status: "PROPOSED",
                        },
                      ],
                      provenance: { origin: "USER", status: "PROPOSED" },
                    })) as { id: string };
                    await selectCv(selected.id, {
                      selection_method: "SINGLE_STUDY",
                      selected_study_id: cv.id,
                      cv_study_ids: [cv.id],
                    });
                    await getStatisticsConfig(selected.id);
                    await calculateSampleSize(selected.id, {
                      design_type: designType,
                      dropout_pct: 10,
                      reserve_pct: 0,
                    });
                    await reloadSelected(selected.id);
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Statistics failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Demo: CV → select → sample size
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const res = await validateStatistics(selected.id);
                    setError(
                      res.blocking
                        ? `Stats blocking: ${res.issues.map((i) => i.code).join(", ")}`
                        : `Stats OK (${res.issues.length} notes)`,
                    );
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Validate failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Validate
              </button>
            </div>
            <ul>
              <li>CV studies: {(selected.cv_studies ?? []).length}</li>
              <li>
                Selected CV: {selected.cv_selection?.selected_cv ?? "—"}% (
                {selected.cv_selection?.selection_method ?? "—"})
              </li>
              <li>Source method: {selected.sample_size?.method ?? "—"}</li>
              <li>N evaluable: {selected.sample_size?.evaluable_n ?? "—"}</li>
              <li>N randomized: {selected.sample_size?.randomized_n ?? "—"}</li>
              <li>N screened: {selected.sample_size?.screened_n ?? "—"}</li>
              <li>
                Status:{" "}
                {selected.sample_size ? (
                  <ProvenanceBadge status={selected.sample_size.provenance.status} />
                ) : (
                  "—"
                )}
              </li>
            </ul>
          </div>

          <div className="status-panel">
            <h2>Validation Summary</h2>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const run = await runProjectValidation(selected.id);
                    setValidationSummary(run.summary);
                    setError(
                      run.summary.blocking
                        ? `Blocking validation (${run.summary.errors} errors / ${run.summary.critical} critical)`
                        : `Validation OK — ${run.summary.total} issues`,
                    );
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Validation failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Run validation
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    setValidationSummary(await getValidationSummary(selected.id));
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Summary failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Refresh summary
              </button>
            </div>
            {validationSummary && (
              <ul>
                <li>CRITICAL {validationSummary.critical}</li>
                <li>ERROR {validationSummary.errors}</li>
                <li>WARNING {validationSummary.warnings}</li>
                <li>INFO {validationSummary.info}</li>
                <li>Blocking: {String(validationSummary.blocking)}</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Expert decisions</h2>
            <p className="muted">
              Proposed values require explicit Approve / Reject. Approve updates the decision
              record only — it does not apply values to Study / Canonical.
            </p>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    await seedKnowledgeRules(selected.id);
                    setExpertDecisions(await listExpertDecisions(selected.id));
                    setKnowledgeGaps(await listKnowledgeGaps(selected.id));
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Knowledge load failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Seed rules + load
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const prop = await proposeDesignKnowledge(selected.id, {
                      variability_indication: "NOT_HIGH",
                    });
                    setDesignProposal(prop);
                    const dec = await createExpertDecision({
                      project_id: selected.id,
                      decision_type: "DESIGN",
                      target_entity_type: "Design",
                      proposed_value: { design: prop.proposed_design },
                      rationale: Array.isArray(prop.reasons)
                        ? (prop.reasons as string[]).join("; ")
                        : "Design proposal",
                    });
                    setExpertDecisions(await listExpertDecisions(selected.id));
                    setError(`Decision ${dec.id.slice(0, 8)}… proposed`);
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Propose failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Propose design
              </button>
            </div>
            {designProposal && (
              <ul>
                <li>Proposed: {String(designProposal.proposed_design ?? "—")}</li>
                <li>Status: {String(designProposal.status ?? "PROPOSED")}</li>
                <li>
                  Expert required: {String(designProposal.requires_expert_confirmation ?? true)}
                </li>
              </ul>
            )}
            {expertDecisions.map((d) => (
              <div key={d.id} style={{ marginTop: 8, borderTop: "1px solid #ddd", paddingTop: 8 }}>
                <div>
                  [{d.status}] {d.decision_type} → {JSON.stringify(d.proposed_value)}
                </div>
                <div className="muted">Why: {d.rationale}</div>
                {d.status === "PROPOSED" && (
                  <div className="row">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          await approveExpertDecision(d.id);
                          setExpertDecisions(await listExpertDecisions(selected.id));
                        } catch (err: unknown) {
                          setError(err instanceof Error ? err.message : "Approve failed");
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Approve (decision only)
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          await rejectExpertDecision(d.id);
                          setExpertDecisions(await listExpertDecisions(selected.id));
                        } catch (err: unknown) {
                          setError(err instanceof Error ? err.message : "Reject failed");
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="status-panel">
            <h2>Knowledge gaps</h2>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    setKnowledgeGaps(await listKnowledgeGaps(selected.id));
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Gaps load failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Refresh gaps
              </button>
            </div>
            {knowledgeGaps
              .filter((g) => g.status === "OPEN")
              .map((g) => (
                <div key={g.id} style={{ marginTop: 8, borderTop: "1px solid #ddd", paddingTop: 8 }}>
                  <div>
                    [{g.importance}] {g.blocking ? "BLOCKING · " : ""}
                    {g.question}
                  </div>
                  <div className="muted">
                    Domain: {g.domain} · Blocking: {g.blocking ? "YES" : "NO"}
                  </div>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await resolveKnowledgeGap(g.id, "Resolved from UI review");
                        setKnowledgeGaps(await listKnowledgeGaps(selected.id));
                      } catch (err: unknown) {
                        setError(err instanceof Error ? err.message : "Resolve failed");
                      } finally {
                        setBusy(false);
                      }
                    }}
                  >
                    Resolve
                  </button>
                </div>
              ))}
          </div>

          <div className="status-panel">
            <h2>Procedure Schedule / Bioanalysis / Safety / Content Matrix</h2>
            <p className="muted">
              Content foundation — proposals do not write Canonical Study. Status / gaps only.
            </p>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const [sched, matrix, bio, safety, resolved] = await Promise.all([
                      getProcedureSchedule(selected.id),
                      getContentMatrix(selected.id),
                      proposeBioanalysis(selected.id),
                      proposeSafetyPlan(selected.id),
                      resolveProjectContent(selected.id),
                    ]);
                    setContentMeta({
                      scheduleCount: Number(sched.count ?? 0),
                      matrixCount: matrix.count,
                      bioStatus: String((bio.plan as { status?: string })?.status ?? bio.status ?? "—"),
                      safetyGaps: Array.isArray(safety.knowledge_gaps)
                        ? safety.knowledge_gaps.length
                        : 0,
                      resolveNote: String(resolved.note ?? "resolved"),
                    });
                    setKnowledgeGaps(await listKnowledgeGaps(selected.id));
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Content foundation failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Load content foundation
              </button>
            </div>
            {contentMeta && (
              <ul>
                <li>Procedure schedule events/procs: {contentMeta.scheduleCount ?? "—"}</li>
                <li>Content matrix rows: {contentMeta.matrixCount ?? "—"}</li>
                <li>Bioanalysis proposal status: {contentMeta.bioStatus ?? "—"}</li>
                <li>Safety knowledge gaps: {contentMeta.safetyGaps ?? "—"}</li>
                <li>{contentMeta.resolveNote}</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Research Foundation</h2>
            <p className="muted">
              Client Input · Tasks · Documents · Search · Evidence · Conflicts (no LLM / web search)
            </p>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    await createResearchCase(selected.id);
                    await upsertResearchProfile(selected.id, {
                      sync_from_client_input: true,
                      regulatory_jurisdiction: "EAEU",
                    });
                    await generateResearchTasks(selected.id);
                    const [rc, tasks, evidence, conflicts, docs, completeness] = await Promise.all([
                      getResearchCase(selected.id),
                      listResearchTasks(selected.id),
                      listResearchEvidence(selected.id),
                      listResearchConflicts(selected.id),
                      listDocuments(selected.id),
                      researchCompleteness(selected.id),
                    ]);
                    setResearchMeta({
                      status: (rc as { status: string }).status,
                      tasks: tasks.length,
                      evidence: evidence.length,
                      conflicts: conflicts.length,
                      documents: docs.length,
                      score: completeness.score,
                    });
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Research foundation failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Profile → tasks → completeness
              </button>
            </div>
            {researchMeta && (
              <ul>
                <li>Research Case: {researchMeta.status}</li>
                <li>Tasks: {researchMeta.tasks}</li>
                <li>Documents: {researchMeta.documents}</li>
                <li>Evidence: {researchMeta.evidence}</li>
                <li>Conflicts: {researchMeta.conflicts}</li>
                <li>Completeness: {researchMeta.score ?? "—"}%</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Regulatory Evidence</h2>
            <p className="muted">
              Source · page · extract · claim · confidence · status. Approve does not change Study.
              Interview ≠ regulation.
            </p>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const [manifest, pipe, queue] = await Promise.all([
                      getRegulatoryManifest(),
                      runRegulatoryEvidencePipeline({ include_interview: true }),
                      getRegulatoryReviewQueue(),
                    ]);
                    const cov = (pipe.coverage || (await getRegulatoryCoverage())) as Record<
                      string,
                      unknown
                    >;
                    setRegulatoryMeta({
                      packageStatus: String(manifest.package_status || cov.package_status || "—"),
                      sourcesMissing: Number(cov.sources_missing ?? 0),
                      claims: Array.isArray(pipe.claims) ? pipe.claims.length : Number(cov.proposed_claims ?? 0),
                      verified: Number(cov.verified_claims ?? 0),
                      proposed: Number(cov.proposed_claims ?? 0),
                      gaps: Array.isArray(pipe.knowledge_gaps) ? pipe.knowledge_gaps.length : 0,
                      reviewPending: (queue.items || []).filter((i) => i.status === "PENDING").length,
                      note: "Study not mutated; KnowledgeRules remain PROPOSED unless explicitly verified",
                    });
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Regulatory evidence load failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Load pack → coverage → queue
              </button>
              <button
                type="button"
                disabled={busy || !regulatoryMeta}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const queue = await getRegulatoryReviewQueue();
                    const first = (queue.items || []).find((i) => i.status === "PENDING");
                    if (!first) {
                      setError("No PENDING review items");
                      return;
                    }
                    const res = await regulatoryReviewAction(String(first.item_id), {
                      claim_id: String(first.claim_id || ""),
                      action: "approve",
                      reviewer: "ui-reviewer",
                    });
                    if (res.study_mutated) {
                      setError("Unexpected Study mutation on approve");
                    } else {
                      setRegulatoryMeta((prev) =>
                        prev
                          ? {
                              ...prev,
                              note: String(res.message || "Approved — Study unchanged"),
                              reviewPending: Math.max(0, prev.reviewPending - 1),
                            }
                          : prev,
                      );
                    }
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Review action failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Approve first pending (no Study change)
              </button>
              <button
                type="button"
                disabled={busy || !regulatoryMeta}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const queue = await getRegulatoryReviewQueue();
                    const first = (queue.items || []).find((i) => i.status === "PENDING");
                    if (!first) {
                      setError("No PENDING review items");
                      return;
                    }
                    await regulatoryReviewAction(String(first.item_id), {
                      claim_id: String(first.claim_id || ""),
                      action: "reject",
                    });
                    setRegulatoryMeta((prev) =>
                      prev
                        ? { ...prev, reviewPending: Math.max(0, prev.reviewPending - 1), note: "Rejected" }
                        : prev,
                    );
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Reject failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Reject first pending
              </button>
            </div>
            {regulatoryMeta && (
              <ul>
                <li>Package: {regulatoryMeta.packageStatus}</li>
                <li>Missing official sources: {regulatoryMeta.sourcesMissing}</li>
                <li>Claims: {regulatoryMeta.claims}</li>
                <li>Verified claims: {regulatoryMeta.verified}</li>
                <li>Proposed / unverified: {regulatoryMeta.proposed}</li>
                <li>Knowledge gaps: {regulatoryMeta.gaps}</li>
                <li>Review pending: {regulatoryMeta.reviewPending}</li>
                <li>{regulatoryMeta.note}</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Study Input Package</h2>
            <p className="muted">
              Writer documents → classify → extract → candidates → conflicts → review. Never mutates Study.
            </p>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const pkg = await loadStudyInputRealFixture();
                    const packageId = String(pkg.package_id);
                    const [cov, conflicts, missing, readiness, candidates] = await Promise.all([
                      getStudyInputCoverage(packageId),
                      getStudyInputConflicts(packageId),
                      getStudyInputMissing(packageId),
                      getStudyInputReadiness(packageId),
                      getStudyInputCandidates(packageId),
                    ]);
                    const domains = (cov.domains || {}) as Record<string, { state?: string }>;
                    setStudyInputMeta({
                      packageId,
                      status: String(pkg.status || ""),
                      docs: ((pkg.documents as Array<Record<string, unknown>>) || []).map((d) =>
                        String(d.document_type),
                      ),
                      coverage: Object.entries(domains).map(([domain, v]) => ({
                        domain,
                        state: String(v.state || "MISSING"),
                      })),
                      conflicts: (conflicts || []).map((c) => ({
                        field: String(c.field_path || ""),
                        values: (c.values as string[]) || [],
                      })),
                      gaps: (missing.knowledge_gaps || []).length,
                      tasks: (missing.research_tasks || []).length,
                      readyGreen: Boolean(readiness.ready_green),
                      message: String(readiness.message || ""),
                      candidates: candidates.length,
                    });
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Study input load failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Load UPDCB real package
              </button>
              <button
                type="button"
                disabled={busy || !studyInputMeta}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const cands = await getStudyInputCandidates(studyInputMeta!.packageId);
                    const first = cands.find((c) => c.status === "PROPOSED");
                    if (!first) {
                      setError("No PROPOSED candidates");
                      return;
                    }
                    const res = await reviewStudyInputCandidate(
                      studyInputMeta!.packageId,
                      String(first.id),
                      { action: "VERIFY", reviewer: "ui-reviewer" },
                    );
                    if (res.study_mutated) {
                      setError("Unexpected Study mutation on verify");
                    } else {
                      setStudyInputMeta((prev) =>
                        prev
                          ? {
                              ...prev,
                              message: `Verified ${String(first.field_path)} — Study unchanged`,
                            }
                          : prev,
                      );
                    }
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Candidate review failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Verify first candidate (no Study change)
              </button>
            </div>
            {studyInputMeta && (
              <ul>
                <li>
                  Status: {studyInputMeta.status}
                  {studyInputMeta.readyGreen ? " ✓ ready" : " — not green (conflicts/gaps)"}
                </li>
                <li>Documents: {studyInputMeta.docs.join(", ")}</li>
                <li>Candidates: {studyInputMeta.candidates}</li>
                <li>
                  Coverage:{" "}
                  {studyInputMeta.coverage
                    .map((c) => `${c.domain}=${c.state}`)
                    .slice(0, 8)
                    .join("; ")}
                </li>
                {studyInputMeta.conflicts.length > 0 ? (
                  <li style={{ color: "#a40" }}>
                    Conflicts:{" "}
                    {studyInputMeta.conflicts
                      .map((c) => `${c.field}: ${c.values.join(" vs ")}`)
                      .join("; ")}
                  </li>
                ) : (
                  <li>Conflicts: none</li>
                )}
                <li>
                  Gaps: {studyInputMeta.gaps} · Research tasks: {studyInputMeta.tasks}
                </li>
                <li>{studyInputMeta.message}</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Decision Center</h2>
            <p className="muted">
              Evidence-based recommendations for design/food/washout/sampling/analyte. Recommended ≠
              approved. Dependency-aware blockers only. Never mutates Study.
            </p>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const res = await recomputeDecisionCenterGolden();
                    const studyId = String(res.study_id);
                    const listed = await listStudyDecisions(studyId);
                    const decisions = (listed.decisions || res.decisions || []) as Array<
                      Record<string, unknown>
                    >;
                    setDecisionCenterMeta({
                      studyId,
                      decisions: decisions.map((d) => {
                        const display = (d.display || {}) as Record<string, unknown>;
                        const rec = (d.recommendation || {}) as Record<string, unknown>;
                        const reasons = (d.blocking_reasons as Array<Record<string, unknown>>) || [];
                        const nonBlock = (d.non_blocking_issues as Array<Record<string, unknown>>) || [];
                        const whyBlock =
                          (display.blocking_why as string[]) ||
                          reasons.map((r) => String(r.blocking_reason_code || r.field_path || ""));
                        const whyNon =
                          (display.non_blocking_why as string[]) ||
                          nonBlock.map((r) => String(r.blocking_reason_code || r.field_path || ""));
                        return {
                          domain_label: String(d.domain_label || d.domain || ""),
                          status: String(d.status || ""),
                          recommendation_option: String(
                            display.recommendation_option || rec.option_label || "",
                          ),
                          recommendation_status: String(rec.status || ""),
                          approved: Boolean(display.approved),
                          blocking: whyBlock.filter(Boolean),
                          nonBlocking: whyNon.filter(Boolean),
                        };
                      }),
                      blocking: (res.blocking_conflicts as string[]) || [],
                      note:
                        res.study_mutated === true
                          ? "ERROR: Study mutated"
                          : "Study not mutated; recommendations are not approvals",
                    });
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Decision center failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Recompute UPDCB decisions
              </button>
            </div>
            {decisionCenterMeta && (
              <ul>
                <li>Study: {decisionCenterMeta.studyId}</li>
                {decisionCenterMeta.blocking.length > 0 && (
                  <li style={{ color: "#a40" }}>
                    Blocking: {decisionCenterMeta.blocking.join(", ")}
                  </li>
                )}
                {decisionCenterMeta.decisions.map((d) => (
                  <li key={d.domain_label}>
                    <strong>{d.domain_label}</strong>: {d.status}
                    {d.recommendation_option
                      ? ` — ${d.recommendation_option} (${d.recommendation_status})`
                      : ""}
                    {d.approved ? " [Утверждено]" : " [не утверждено]"}
                    {d.blocking.length > 0 && (
                      <ul>
                        <li style={{ color: "#a40" }}>
                          BLOCKING: {d.blocking.join("; ")}
                        </li>
                      </ul>
                    )}
                    {d.nonBlocking.length > 0 && (
                      <ul>
                        <li className="muted">
                          NON-BLOCKING: {d.nonBlocking.join("; ")}
                        </li>
                      </ul>
                    )}
                  </li>
                ))}
                <li>{decisionCenterMeta.note}</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Sample Size</h2>
            <p className="muted">
              Deterministic 2×2 TOST engine. Current protocol N ≠ calculated N. Calculated result is
              not an approved protocol value. Never mutates Study.
            </p>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const studyId = "UPDCB-02-BE-2026";
                    // Attempt authoritative calc without inventing CV — expect BLOCKED if none verified
                    const calc = (await calculateStudySampleSize(studyId, {
                      design: "STANDARD_2X2_CROSSOVER",
                      parameter: "Cmax",
                      expected_ratio: 0.95,
                      expected_ratio_source: "EXPERT_INPUT",
                      alpha: 0.05,
                      alpha_source: "EXPLICIT_CONFIGURATION",
                      power: 0.8,
                      power_source: "EXPERT_INPUT",
                      dropout_percent: 10,
                      dropout_source: "EXPERT_INPUT",
                      inflation_method: "DIVIDE_BY_RETAINMENT_RATE",
                      be_lower: 0.8,
                      be_upper: 1.25,
                      be_limits_source: "EXPLICIT_CONFIGURATION",
                      current_protocol_n: 56,
                      current_protocol_n_source: "SYNOPSIS",
                      created_by: "ui-expert",
                    })) as Record<string, unknown>;
                    const panel = await getSampleSizePanel(studyId);
                    const scenarios = ((panel.scenarios as Array<Record<string, unknown>>) || []).map(
                      (s) => ({
                        parameter: String(s.parameter || ""),
                        required_n: (s.required_n as number | null) ?? null,
                        power: (s.target_power as number | null) ?? null,
                      }),
                    );
                    const evidence = (
                      (panel.available_evidence as Array<Record<string, unknown>>) || []
                    ).map((e) => ({
                      parameter: String(e.parameter || ""),
                      cv: String(e.cv_value ?? ""),
                      verification: String(e.verification_status || ""),
                      applicability: String(e.applicability || ""),
                    }));
                    setSampleSizeMeta({
                      studyId,
                      currentN: (panel.current_protocol_value as number | null) ?? 56,
                      calculatedN: (calc.randomized_n as number | null) ?? null,
                      requiredN: (calc.required_n as number | null) ?? null,
                      status: String(calc.status || panel.status || ""),
                      discrepancy: Boolean(calc.discrepancy || panel.discrepancy),
                      controlling: String(panel.controlling_parameter || "REQUIRES_EXPERT_DECISION"),
                      scenarios,
                      evidence,
                      blockers: (calc.blocking_reasons as string[]) || [],
                      note:
                        panel.calculated_shown_as_approved === true
                          ? "ERROR: calculated shown as approved"
                          : "Calculated N is not approved protocol value; Study not mutated",
                    });
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Sample size failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Review sample size (UPDCB)
              </button>
            </div>
            {sampleSizeMeta && (
              <ul>
                <li>Study: {sampleSizeMeta.studyId}</li>
                <li>Current protocol value: {sampleSizeMeta.currentN ?? "—"} subjects</li>
                <li>
                  Calculated N: {sampleSizeMeta.calculatedN ?? "—"}
                  {sampleSizeMeta.requiredN != null
                    ? ` (evaluable ${sampleSizeMeta.requiredN})`
                    : ""}{" "}
                  — not approved
                </li>
                <li>Status: {sampleSizeMeta.status}</li>
                {sampleSizeMeta.discrepancy && (
                  <li style={{ color: "#a40" }}>⚠ Difference from current protocol</li>
                )}
                <li>Controlling parameter: {sampleSizeMeta.controlling}</li>
                {sampleSizeMeta.evidence.length > 0 && (
                  <li>
                    Available evidence:
                    <ul>
                      {sampleSizeMeta.evidence.map((e) => (
                        <li key={`${e.parameter}-${e.cv}`}>
                          CVintra {e.parameter}: {e.cv}% · {e.verification} · Applicability:{" "}
                          {e.applicability}
                        </li>
                      ))}
                    </ul>
                  </li>
                )}
                {sampleSizeMeta.scenarios.length > 0 && (
                  <li>
                    Scenarios:
                    <ul>
                      {sampleSizeMeta.scenarios.map((s) => (
                        <li key={s.parameter}>
                          {s.parameter}: Required N {s.required_n ?? "—"}
                          {s.power != null ? ` · Power ${Math.round(Number(s.power) * 100)}%` : ""}
                        </li>
                      ))}
                    </ul>
                  </li>
                )}
                {sampleSizeMeta.blockers.length > 0 && (
                  <li style={{ color: "#a40" }}>
                    Blocking: {sampleSizeMeta.blockers.join("; ")}
                  </li>
                )}
                <li>{sampleSizeMeta.note}</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Статистический план</h2>
            <p className="muted">
              Deterministic method plan from study facts. Recommendation ≠ approval. No fabricated
              GMR/CI. Never mutates Study.
            </p>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const res = await recomputeStatisticsGolden();
                    const plan = (res.plan || {}) as Record<string, unknown>;
                    const panel = (res.panel || {}) as Record<string, unknown>;
                    const params = (
                      (panel.parameters as Array<Record<string, unknown>>) || []
                    ).map((p) => ({
                      parameter: String(p.parameter || ""),
                      role: String(p.role_label || ""),
                      transform: String(p.transform_label || ""),
                      model: (p.model_label as string | null) ?? null,
                      ci: (p.ci_label as string | null) ?? null,
                      acceptance: (p.acceptance_label as string | null) ?? null,
                    }));
                    setStatisticsMeta({
                      studyId: String(res.study_id || "UPDCB-02-BE-2026"),
                      status: String(plan.status || panel.status || ""),
                      parameters: params,
                      warning: (panel.warning as string | null) ?? null,
                      blockers: (plan.blocking_reasons as string[]) || [],
                      note:
                        panel.recommendation_shown_as_approved === true
                          ? "ERROR: recommendation shown as approved"
                          : "Recommendation is not approved; Study not mutated",
                    });
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Statistics failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Recompute UPDCB statistics
              </button>
            </div>
            {statisticsMeta && (
              <ul>
                <li>Study: {statisticsMeta.studyId}</li>
                <li>Status: {statisticsMeta.status}</li>
                {statisticsMeta.warning && (
                  <li style={{ color: "#a40" }}>⚠ {statisticsMeta.warning}</li>
                )}
                {statisticsMeta.parameters.map((p) => (
                  <li key={p.parameter}>
                    <strong>{p.parameter}</strong>
                    {p.role ? ` · Role: ${p.role}` : ""}
                    {p.transform ? ` · Transform: ${p.transform}` : ""}
                    {p.model ? ` · Model: ${p.model}` : ""}
                    {p.ci ? ` · CI: ${p.ci}` : ""}
                    {p.acceptance ? ` · Acceptance: ${p.acceptance}` : ""}
                  </li>
                ))}
                {statisticsMeta.blockers.length > 0 && (
                  <li style={{ color: "#a40" }}>
                    Blocking: {statisticsMeta.blockers.join("; ")}
                  </li>
                )}
                <li>{statisticsMeta.note}</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Research Center</h2>
            <p className="muted">
              Исследование: gaps → real/mock search → Source → claims → review. Proposed ≠ Verified.
              Priority ≠ verification. Never mutates Study.
            </p>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const boot = await bootstrapResearchCenterGolden();
                    const studyId = String(boot.study_id);
                    const tasks = (boot.tasks || []) as Array<Record<string, unknown>>;
                    const runSummaries: Array<{
                      label: string;
                      status: string;
                      priority: string;
                      gap: string;
                      claims?: number;
                      conflicts?: number;
                      query?: string;
                      results?: Array<{ title: string; priority: string; url: string }>;
                    }> = [];
                    for (const t of tasks) {
                      let run: Record<string, unknown>;
                      try {
                        run = await runResearchCenterRealSearch(String(t.id), {
                          active_substance: "upadacitinib",
                          product: "РАНВЭК",
                          dosage_form: "tablet",
                        });
                        if (run.status === "RESEARCH_FAILED") {
                          run = await runResearchCenterTask(String(t.id), {
                            use_mock_provider: true,
                          });
                          run = { ...run, query: (run.query as Record<string, unknown>) || {} };
                        }
                      } catch {
                        run = await runResearchCenterTask(String(t.id), {
                          use_mock_provider: true,
                        });
                      }
                      const claims = (run.claims as unknown[]) || [];
                      const conflicts = (run.conflicts as unknown[]) || [];
                      const q = (run.query as Record<string, unknown>) || {};
                      const searchResults = (run.results as Array<Record<string, unknown>>) || [];
                      runSummaries.push({
                        label: String(t.question || t.task_type || ""),
                        status: String((run.task as Record<string, unknown>)?.status || t.status),
                        priority: String(t.priority || ""),
                        gap: String(t.knowledge_gap_code || ""),
                        claims: claims.length,
                        conflicts: conflicts.length,
                        query: String(q.query_text || ""),
                        results: searchResults.slice(0, 5).map((r) => ({
                          title: String(r.title || ""),
                          priority: String(r.priority_class || "OTHER"),
                          url: String(r.url || ""),
                        })),
                      });
                    }
                    await getResearchCenterCoverage(studyId);
                    await listResearchCenterTasks(studyId);
                    setResearchCenterMeta({
                      studyId,
                      tasks: runSummaries,
                      note:
                        boot.study_mutated === true
                          ? "ERROR: Study mutated"
                          : "Study not mutated; search results are never Verified until expert review",
                    });
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Research center failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Найти данные
              </button>
            </div>
            {researchCenterMeta && (
              <ul>
                <li>Исследование: {researchCenterMeta.studyId}</li>
                {researchCenterMeta.tasks.map((t) => (
                  <li key={t.gap || t.label}>
                    <div>
                      ⚠ {t.label}: {t.status}
                      {t.claims != null ? ` · кандидатов: ${t.claims}` : ""}
                      {t.conflicts ? ` · ⚠ расхождений: ${t.conflicts}` : ""}{" "}
                      <span className="muted">[{t.priority}]</span>
                    </div>
                    {t.query ? <div className="muted">Query: {t.query}</div> : null}
                    {t.results && t.results.length > 0 && (
                      <ul>
                        {t.results.map((r) => (
                          <li key={r.url || r.title}>
                            {r.title} · {r.priority} · not Verified
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
                <li>{researchCenterMeta.note}</li>
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>AI Extraction</h2>
            <p className="muted">
              Assistive only — PROPOSED evidence with source grounding. Expert verify before Study apply.
            </p>
            <div className="row">
              <select value={aiTask} onChange={(e) => setAiTask(e.target.value)}>
                <option value="EXTRACT_PK">Extract PK</option>
                <option value="EXTRACT_CV">Extract CV</option>
                <option value="EXTRACT_FOOD">Extract Food</option>
                <option value="EXTRACT_REFERENCE">Extract Reference</option>
                <option value="EXTRACT_ANALYTES">Extract Analytes</option>
                <option value="EXTRACT_DESIGN">Extract Design</option>
              </select>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const st = await aiStatus();
                    setAiStatusMeta(st);
                    const result = await aiExtract(selected.id, {
                      task_type: aiTask,
                      force_mock: !st.enabled || !st.available,
                    });
                    setAiClaims(result.claims.length ? result.claims : await listAiProposed(selected.id));
                    setSelected(await getProject(selected.id));
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "AI extract failed");
                    try {
                      setAiClaims(await listAiProposed(selected.id));
                    } catch {
                      /* ignore */
                    }
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Run
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    setAiStatusMeta(await aiStatus());
                    setAiClaims(await listAiProposed(selected.id));
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Load proposed failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Refresh proposed
              </button>
            </div>
            {aiStatusMeta && (
              <p className="muted">
                AI: {aiStatusMeta.enabled ? "enabled" : "off"} · {aiStatusMeta.provider} ·{" "}
                {aiStatusMeta.model ?? "—"} · available={String(aiStatusMeta.available)}
              </p>
            )}
            {aiClaims.length > 0 && (
              <ul>
                {aiClaims.map((c) => (
                  <li key={c.claim_id ?? `${c.field_name}-${c.evidence_text}`}>
                    <strong>{c.field_name}</strong> {c.value}
                    {c.unit ? ` ${c.unit}` : ""} · page {c.page} · conf {c.confidence} · {c.status}
                    <div className="muted">{c.evidence_text}</div>
                    <div className="row">
                      <button
                        type="button"
                        disabled={busy || !c.claim_id}
                        onClick={async () => {
                          if (!c.claim_id) return;
                          setBusy(true);
                          try {
                            const analyteId = selected.analytes?.[0]?.id;
                            await reviewAiClaim(selected.id, c.claim_id, {
                              action: "verify",
                              analyte_id: analyteId,
                            });
                            setAiClaims(await listAiProposed(selected.id));
                            setSelected(await getProject(selected.id));
                          } catch (err: unknown) {
                            setError(err instanceof Error ? err.message : "Verify failed");
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        Verify
                      </button>
                      <button
                        type="button"
                        disabled={busy || !c.claim_id}
                        onClick={async () => {
                          if (!c.claim_id) return;
                          setBusy(true);
                          try {
                            await reviewAiClaim(selected.id, c.claim_id, { action: "reject" });
                            setAiClaims(await listAiProposed(selected.id));
                          } catch (err: unknown) {
                            setError(err instanceof Error ? err.message : "Reject failed");
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        Reject
                      </button>
                      <button
                        type="button"
                        disabled={busy || !c.claim_id}
                        onClick={async () => {
                          if (!c.claim_id) return;
                          const edited = window.prompt("Edit value then verify", c.value);
                          if (edited == null) return;
                          setBusy(true);
                          try {
                            const analyteId = selected.analytes?.[0]?.id;
                            await reviewAiClaim(selected.id, c.claim_id, {
                              action: "edit_verify",
                              edited_value: edited,
                              analyte_id: analyteId,
                            });
                            setAiClaims(await listAiProposed(selected.id));
                            setSelected(await getProject(selected.id));
                          } catch (err: unknown) {
                            setError(err instanceof Error ? err.message : "Edit & Verify failed");
                          } finally {
                            setBusy(false);
                          }
                        }}
                      >
                        Edit & Verify
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="status-panel">
            <h2>Protocol Assembly</h2>
            <p className="muted">
              Structured ProtocolDraft from Study (HTML preview). No DOCX yet.
            </p>
            <div className="row">
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const draft = await buildProtocol(selected.id);
                    const [preview, report] = await Promise.all([
                      getProtocolPreview(selected.id),
                      getProtocolBuildReport(selected.id),
                    ]);
                    setProtocolPreview({
                      status: preview.status || draft.status,
                      tree: preview.tree,
                      unresolved_fields: preview.unresolved_fields,
                      blocking_issues: preview.blocking_issues,
                      warnings: preview.warnings,
                      tables: preview.tables,
                    });
                    setProtocolReport({
                      generated_sections: report.generated_sections,
                      unresolved_fields: report.unresolved_fields,
                      blocking_issues: report.blocking_issues as unknown[],
                      warnings: report.warnings,
                      source_count: report.source_count,
                    });
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "Protocol build failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Build protocol
              </button>
            </div>
            {protocolReport && (
              <ul>
                <li>Status: {protocolPreview?.status ?? "—"}</li>
                <li>Sections: {protocolReport.generated_sections.length}</li>
                <li>Unresolved: {protocolReport.unresolved_fields.length}</li>
                <li>Blocking issues: {protocolReport.blocking_issues.length}</li>
                <li>Sources: {protocolReport.source_count}</li>
              </ul>
            )}
            {protocolPreview && (
              <div className="protocol-preview">
                {protocolPreview.unresolved_fields.length > 0 && (
                  <p className="muted">
                    Unresolved: {protocolPreview.unresolved_fields.slice(0, 8).join(", ")}
                    {protocolPreview.unresolved_fields.length > 8 ? "…" : ""}
                  </p>
                )}
                <ProtocolTree nodes={protocolPreview.tree} />
                {protocolPreview.tables.length > 0 && (
                  <div>
                    <h3>Tables</h3>
                    {protocolPreview.tables.map((t) => (
                      <div key={t.table_key}>
                        <strong>
                          Таблица {t.display_number}: {t.title}
                        </strong>
                        <span className="muted"> ({t.table_key})</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="status-panel">
            <h2>DOCX Generation</h2>
            <p className="muted">
              Render ProtocolDraft into Word using the immutable template. No business calculations in renderer.
            </p>
            <div className="row">
              <select
                value={docxMode}
                onChange={(e) => setDocxMode(e.target.value as "DRAFT" | "REVIEW" | "FINAL")}
              >
                <option value="DRAFT">DRAFT</option>
                <option value="REVIEW">REVIEW</option>
                <option value="FINAL">FINAL</option>
              </select>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const built = await buildDocx(selected.id, docxMode);
                    const st = await getDocxStatus(selected.id);
                    setDocxMeta({
                      status: built.status,
                      mode: built.mode,
                      template_version: st.template_version,
                      generator_version: st.generator_version,
                      blocking_reasons: built.blocking_reasons || [],
                      filename: built.filename,
                    });
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "DOCX build failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Build DOCX
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const v = await getDocxValidation(selected.id);
                    const st = await getDocxStatus(selected.id);
                    setDocxMeta({
                      status: v.status,
                      mode: st.latest?.mode || docxMode,
                      template_version: st.template_version,
                      generator_version: st.generator_version,
                      blocking_reasons: v.blocking_reasons || [],
                      filename: st.latest?.filename || null,
                    });
                  } catch (err: unknown) {
                    setError(err instanceof Error ? err.message : "DOCX validate failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Validate
              </button>
              <a
                href={downloadDocxUrl(selected.id)}
                target="_blank"
                rel="noreferrer"
              >
                Download
              </a>
            </div>
            {docxMeta && (
              <ul>
                <li>Status: {docxMeta.status}</li>
                <li>Mode: {docxMeta.mode}</li>
                <li>Template: {docxMeta.template_version}</li>
                <li>Generator: {docxMeta.generator_version}</li>
                <li>File: {docxMeta.filename ?? "—"}</li>
                {docxMeta.blocking_reasons.length > 0 && (
                  <li>Blocking: {docxMeta.blocking_reasons.slice(0, 5).join("; ")}</li>
                )}
              </ul>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function ProtocolTree({ nodes }: { nodes: ProtocolPreviewNode[] }) {
  return (
    <ul>
      {nodes.map((n) => (
        <li key={n.section_code}>
          <strong>
            {n.section_code === "SYNOPSIS" ? "Synopsis" : n.section_code}. {n.title}
          </strong>{" "}
          <span className="badge">{n.status}</span>
          {n.warnings?.length > 0 && <span className="muted"> · warn</span>}
          {n.source_ids?.length > 0 && <span className="muted"> · src:{n.source_ids.length}</span>}
          {n.content_blocks?.map((b, idx) => {
            const type = String(b.type || "");
            if (type === "TEXT" && b.text) {
              return (
                <p key={idx} className="muted">
                  {String(b.text)}
                </p>
              );
            }
            if (type === "TABLE") {
              return (
                <p key={idx} className="muted">
                  [Table {String(b.table_key)}
                  {b.table_number != null ? ` #${String(b.table_number)}` : ""}]
                </p>
              );
            }
            if ((type === "LIST" || type === "NUMBERED_LIST") && Array.isArray(b.items)) {
              return (
                <ul key={idx}>
                  {(b.items as unknown[]).map((it, i) => (
                    <li key={i}>{String(it)}</li>
                  ))}
                </ul>
              );
            }
            if (type === "REFERENCE") {
              return (
                <p key={idx} className="muted">
                  → {String(b.display_text || b.target_id)}
                </p>
              );
            }
            return null;
          })}
          {n.children?.length > 0 && <ProtocolTree nodes={n.children} />}
        </li>
      ))}
    </ul>
  );
}

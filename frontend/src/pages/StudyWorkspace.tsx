import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getStudyWorkspace,
  getStudyConflicts,
  getStudyPreflight,
  getStudyReadiness,
  getStudyAudit,
  runStudyWorkflow,
  recomputeDecisionCenterGolden,
  bootstrapResearchCenterGolden,
  getSampleSizePanel,
  recomputeStatisticsGolden,
  getWriterReview,
  getBetaCases,
  createWorkspaceStudy,
  listWorkspaceDocuments,
  uploadWorkspaceDocument,
  classifyWorkspaceDocument,
  reviewCanonicalFact,
  listStudyDecisions,
  getWorkspaceProtocolPreview,
  generateWorkspaceDocx,
  listProtocolDrafts,
  getStudyStatistics,
  approveSampleSizeCalculation,
  approveStatisticsPlan,
  getWriterProgress,
  getCanonicalFactDetail,
  listWorkspaceArtifacts,
  downloadWorkspaceArtifactUrl,
  listWorkspaceSnapshots,
  formatApiError,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { DecisionForm } from "../components/DecisionForm";
import { DecisionPanel } from "../components/DecisionPanel";
import { StudyList } from "../components/StudyList";
import { Dashboard } from "./Dashboard";
import { ControlledBetaDashboard } from "./ControlledBetaDashboard";
import { computeNextAction, fromBackendPrimary, normalizeTab, type NavId } from "../nextAction";
import {
  ANALYZE_STAGES,
  DEMO_STUDY_ID,
  docStatusLabel,
  humanLabel,
  isDemoStudy,
  stepStatusLabel,
} from "../writerLabels";
import { canPermission } from "../workspace/permissions";
import {
  clearOpError,
  initialOpState,
  setOpBusy,
  setOpError,
  type OpKey,
} from "../workspace/opState";
import {
  ALL_SLICES,
  type RefreshSlice,
} from "../workspace/refreshSlices";
import {
  collectWorkflowStepErrors,
  formatWorkflowStepErrors,
} from "../workspace/workflowSteps";

const PRIMARY_NAV: Array<{ id: NavId; label: string }> = [
  { id: "overview", label: "Обзор" },
  { id: "documents", label: "Документы" },
  { id: "data", label: "Данные" },
  { id: "decisions", label: "Решения" },
  { id: "evidence", label: "Evidence" },
  { id: "sample-size", label: "Sample Size" },
  { id: "statistics", label: "Statistics" },
  { id: "protocol", label: "Протокол" },
  { id: "preflight", label: "Проверка" },
  { id: "history", label: "История" },
];

const DOC_TYPES = [
  { value: "CHECKLIST", label: "Checklist" },
  { value: "SYNOPSIS", label: "Synopsis/Design" },
  { value: "SMPC", label: "SmPC" },
  { value: "OTHER", label: "Other" },
];

type WizardStep = 1 | 2 | 3 | 4 | 5;

function statusClass(code: string | undefined): string {
  if (!code) return "status-gray";
  const u = code.toUpperCase();
  if (u === "READY" || u === "APPROVED" || u === "ACCEPTED" || u === "UPLOADED" || u === "COMPLETED" || u === "PRESENT") {
    return "status-green";
  }
  if (u === "BLOCKED" || u === "CRITICAL" || u === "ERROR" || u === "MISSING") return "status-red";
  if (u.includes("WARN") || u.includes("REVIEW") || u.includes("PENDING") || u.includes("PROCESS") || u === "IN_PROGRESS" || u === "READY") {
    return "status-yellow";
  }
  return "status-gray";
}

function stepStatusClass(status: string): string {
  const u = status.toUpperCase();
  if (u === "COMPLETED") return "status-green";
  if (u === "BLOCKED") return "status-red";
  if (u === "IN_PROGRESS" || u === "READY") return "status-yellow";
  return "status-gray";
}

function EmptyState(props: {
  title: string;
  why: string;
  next: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="empty-state">
      <h3>{props.title}</h3>
      <p>{props.why}</p>
      <p className="muted">Что сделать дальше: {props.next}</p>
      {props.onAction && props.actionLabel ? (
        <button type="button" onClick={props.onAction}>
          {props.actionLabel}
        </button>
      ) : null}
    </div>
  );
}

function BlockerCard(props: {
  what: string;
  why: string;
  where: string;
  actionLabel: string;
  severity?: string;
  onResolve: () => void;
}) {
  return (
    <div className="blocker-card">
      <span className={`status-pill ${statusClass(props.severity || "CRITICAL")}`}>
        {humanLabel(props.severity || "CRITICAL")}
      </span>
      <div>
        <strong>{props.what}</strong>
        <p className="muted small">Почему: {props.why}</p>
        <p className="muted small">Где: {props.where}</p>
        <button type="button" onClick={props.onResolve}>
          {props.actionLabel}
        </button>
      </div>
    </div>
  );
}

export function StudyWorkspace() {
  const { authRequired, user } = useAuth();
  const canApproveDecisions = canPermission({
    authRequired,
    role: user?.role,
    permission: "approve_decisions",
  });
  const reviewer = user?.email || user?.display_name || "writer";

  const [tab, setTab] = useState<NavId>("overview");
  const [advancedPane, setAdvancedPane] = useState<"menu" | "beta" | "legacy">("menu");
  const [ops, setOps] = useState(initialOpState);
  const [analyzeBusy, setAnalyzeBusy] = useState(false);
  const [analyzeStage, setAnalyzeStage] = useState(0);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [workflowStepErrors, setWorkflowStepErrors] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<Record<string, unknown> | null>(null);
  const [writerProgress, setWriterProgress] = useState<Record<string, unknown> | null>(null);
  const [conflicts, setConflicts] = useState<Array<Record<string, unknown>>>([]);
  const [preflight, setPreflight] = useState<Record<string, unknown> | null>(null);
  const [audit, setAudit] = useState<Array<Record<string, unknown>>>([]);
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [betaCases, setBetaCases] = useState<Array<Record<string, unknown>>>([]);
  const [documents, setDocuments] = useState<Array<Record<string, unknown>>>([]);
  const [decisions, setDecisions] = useState<Array<Record<string, unknown>>>([]);
  const [samplePanel, setSamplePanel] = useState<Record<string, unknown> | null>(null);
  const [statsPanel, setStatsPanel] = useState<Record<string, unknown> | null>(null);
  const [protocolPreview, setProtocolPreview] = useState<Record<string, unknown> | null>(null);
  const [protocolDrafts, setProtocolDrafts] = useState<Array<Record<string, unknown>>>([]);
  const [snapshots, setSnapshots] = useState<Array<Record<string, unknown>>>([]);
  const [artifacts, setArtifacts] = useState<Array<Record<string, unknown>>>([]);
  const [docxResult, setDocxResult] = useState<Record<string, unknown> | null>(null);
  const [showDocxConfirm, setShowDocxConfirm] = useState(false);
  const [showNewStudy, setShowNewStudy] = useState(false);
  const [wizardStep, setWizardStep] = useState<WizardStep>(1);
  const [newMeta, setNewMeta] = useState({ title: "", sponsor: "", product: "", dose: "" });
  const [studyId, setStudyId] = useState<string>("");
  const [isDemo, setIsDemo] = useState(false);
  const [uploadType, setUploadType] = useState("CHECKLIST");
  const [editDraft, setEditDraft] = useState<{ field: string; value: string; reason: string } | null>(null);
  const [fieldDrawer, setFieldDrawer] = useState<string | null>(null);
  const [fieldDetail, setFieldDetail] = useState<Record<string, unknown> | null>(null);
  const [previewField, setPreviewField] = useState<string | null>(null);
  const [decisionOutcome, setDecisionOutcome] = useState<Record<string, unknown> | null>(null);
  const [reviewFormOpen, setReviewFormOpen] = useState(false);
  const [reviewDraft, setReviewDraft] = useState<{ rationale: string }>({ rationale: "writer review" });
  const [dataSearch, setDataSearch] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const packageRef = useRef<HTMLInputElement>(null);

  const activeStudy = studyId || (workspace ? String(((workspace.header || {}) as Record<string, unknown>).study_id || "") : "");

  function goTab(next: NavId | string) {
    setTab(normalizeTab(next));
    setAdvancedPane("menu");
  }

  function withOp(key: OpKey, run: () => Promise<void>) {
    setOps((prev) => setOpBusy(prev, key, true));
    return run()
      .catch((err: unknown) => {
        const msg = formatApiError(err);
        setOps((prev) => setOpError(prev, key, msg));
        // Unhandled transport/parser failures also surface globally once
        if (/ContractError|Failed to fetch|NetworkError|Unexpected token|JSON/i.test(msg)) {
          setGlobalError(msg);
        }
      })
      .finally(() => {
        setOps((prev) => ({ ...prev, [key]: { ...prev[key], busy: false } }));
      });
  }

  const refreshSlices = useCallback(
    async (slices: RefreshSlice[], sid = activeStudy) => {
      if (!sid) return;
      const want = new Set(slices);

      if (want.has("core")) {
        const [ws, conf, ready, pf] = await Promise.all([
          getStudyWorkspace(sid),
          getStudyConflicts(sid),
          getStudyReadiness(sid),
          getStudyPreflight(sid),
        ]);
        setWorkspace({ ...ws, readiness_detail: ready } as Record<string, unknown>);
        setConflicts((conf.conflicts as Array<Record<string, unknown>>) || []);
        setPreflight(pf as Record<string, unknown>);
        setStudyId(sid);
        setIsDemo(isDemoStudy(sid) && isDemo);
      }

      if (want.has("documents")) {
        try {
          const docs = await listWorkspaceDocuments(sid);
          setDocuments(docs.documents || []);
        } catch {
          setDocuments([]);
        }
      }

      if (want.has("decisions")) {
        try {
          const d = await listStudyDecisions(sid);
          setDecisions((d.decisions as Array<Record<string, unknown>>) || []);
        } catch {
          setDecisions([]);
        }
        if (!want.has("core")) {
          try {
            const conf = await getStudyConflicts(sid);
            setConflicts((conf.conflicts as Array<Record<string, unknown>>) || []);
          } catch {
            /* keep */
          }
        }
      }

      if (want.has("engines")) {
        try {
          setSamplePanel((await getSampleSizePanel(sid)) as Record<string, unknown>);
        } catch {
          setSamplePanel(null);
        }
        try {
          const stats = await getStudyStatistics(sid);
          setStatsPanel(stats.panel ? ({ ...stats.panel } as Record<string, unknown>) : null);
        } catch {
          setStatsPanel(null);
        }
      }

      if (want.has("protocol")) {
        try {
          const drafts = await listProtocolDrafts(sid);
          setProtocolDrafts(drafts.drafts || []);
        } catch {
          setProtocolDrafts([]);
        }
        try {
          const arts = await listWorkspaceArtifacts(sid);
          setArtifacts((arts.artifacts || []) as Array<Record<string, unknown>>);
        } catch {
          setArtifacts([]);
        }
      }

      if (want.has("history")) {
        try {
          const aud = await getStudyAudit(sid);
          setAudit((aud.timeline as Array<Record<string, unknown>>) || []);
        } catch {
          setAudit([]);
        }
        try {
          const snaps = await listWorkspaceSnapshots(sid);
          setSnapshots(snaps.snapshots || []);
        } catch {
          setSnapshots([]);
        }
      }

      if (want.has("progress")) {
        try {
          setWriterProgress((await getWriterProgress(sid)) as Record<string, unknown>);
        } catch {
          setWriterProgress(null);
        }
      }
    },
    [activeStudy, isDemo],
  );

  function consumeWorkflowResponse(out: Record<string, unknown>) {
    if (out.workspace && typeof out.workspace === "object") {
      setWorkspace(out.workspace as Record<string, unknown>);
    }
    if (out.readiness && typeof out.readiness === "object") {
      setWorkspace((prev) =>
        prev
          ? { ...prev, readiness_detail: out.readiness as Record<string, unknown> }
          : prev,
      );
    }
    if (out.preflight && typeof out.preflight === "object") {
      setPreflight(out.preflight as Record<string, unknown>);
    }
    const stepErrs = collectWorkflowStepErrors(out.steps);
    if (stepErrs.length) {
      setWorkflowStepErrors(formatWorkflowStepErrors(stepErrs));
      setOps((prev) => setOpError(prev, "workflow", formatWorkflowStepErrors(stepErrs)));
    } else {
      setWorkflowStepErrors(null);
    }
  }

  useEffect(() => {
    if (!analyzeBusy) {
      setAnalyzeStage(0);
      return;
    }
    let idx = 0;
    setAnalyzeStage(0);
    const timer = window.setInterval(() => {
      idx = Math.min(idx + 1, ANALYZE_STAGES.length - 1);
      setAnalyzeStage(idx);
    }, 700);
    return () => window.clearInterval(timer);
  }, [analyzeBusy]);

  async function openStudy(key: string) {
    setStudyId(key);
    setShowNewStudy(false);
    setGlobalError(null);
    try {
      await refreshSlices(ALL_SLICES, key);
      goTab("overview");
    } catch (err: unknown) {
      setGlobalError(formatApiError(err, "Не удалось открыть исследование"));
    }
  }

  function backToCatalog() {
    setStudyId("");
    setWorkspace(null);
    setWriterProgress(null);
    setConflicts([]);
    setPreflight(null);
    setAudit([]);
    setDocuments([]);
    setDecisions([]);
    setSamplePanel(null);
    setStatsPanel(null);
    setProtocolPreview(null);
    setProtocolDrafts([]);
    setSnapshots([]);
    setArtifacts([]);
    setDocxResult(null);
    setShowNewStudy(false);
    setWizardStep(1);
    setIsDemo(false);
  }

  async function openFieldDrawer(field: string) {
    if (!activeStudy) return;
    setFieldDrawer(field);
    setFieldDetail(null);
    try {
      setFieldDetail(await getCanonicalFactDetail(activeStudy, field));
    } catch (err: unknown) {
      setGlobalError(formatApiError(err, "Не удалось загрузить детали поля"));
    }
  }

  async function runDemoWorkflow() {
    await withOp("workflow", async () => {
      const out = (await runStudyWorkflow(DEMO_STUDY_ID, {
        use_golden_fixture: true,
        created_by: "ui-medical-writer",
      })) as Record<string, unknown>;
      try {
        await recomputeDecisionCenterGolden();
      } catch {
        /* optional */
      }
      try {
        await bootstrapResearchCenterGolden();
      } catch {
        /* optional */
      }
      try {
        await getSampleSizePanel(DEMO_STUDY_ID);
      } catch {
        /* optional */
      }
      try {
        await recomputeStatisticsGolden();
      } catch {
        /* optional */
      }
      setIsDemo(true);
      setStudyId(DEMO_STUDY_ID);
      consumeWorkflowResponse(out);
      if (out.study_mutated === true) {
        setOps((prev) => setOpError(prev, "workflow", "Demo workflow: study mutated (unexpected)"));
      } else {
        setNotice("Demo workflow завершён. Конфликты требуют экспертного решения.");
      }
      await refreshSlices(["core", "documents", "decisions", "engines", "protocol", "history", "progress"], DEMO_STUDY_ID);
      goTab("overview");
    });
  }

  async function analyzePackage() {
    if (!activeStudy) {
      setOps((prev) => setOpError(prev, "workflow", "Сначала создайте исследование или загрузите документы"));
      return;
    }
    setAnalyzeBusy(true);
    await withOp("workflow", async () => {
      const out = (await runStudyWorkflow(activeStudy, {
        use_golden_fixture: isDemo,
        created_by: "ui-medical-writer",
      })) as Record<string, unknown>;
      consumeWorkflowResponse(out);
      setNotice("Анализ пакета завершён.");
      await refreshSlices(["core", "documents", "decisions", "engines", "progress", "history"], activeStudy);
      if (wizardStep === 3) setWizardStep(4);
    }).finally(() => setAnalyzeBusy(false));
  }

  async function buildDraft() {
    if (!activeStudy) return;
    await withOp("protocol", async () => {
      const out = (await runStudyWorkflow(activeStudy, {
        use_golden_fixture: isDemo,
        prepare_protocol_draft: true,
        created_by: "ui-medical-writer",
      })) as Record<string, unknown>;
      consumeWorkflowResponse(out);
      setNotice("Черновик протокола подготовлен.");
      await refreshSlices(["protocol", "progress", "core"], activeStudy);
    });
  }

  async function createStudyAndAdvance() {
    await withOp("workflow", async () => {
      const created = await createWorkspaceStudy({
        title: newMeta.title || undefined,
        sponsor: newMeta.sponsor || undefined,
        product: newMeta.product || undefined,
        dose: newMeta.dose || undefined,
        is_demo: false,
      });
      setStudyId(created.study_key);
      setIsDemo(false);
      await refreshSlices(ALL_SLICES, created.study_key);
      setWizardStep(2);
      setNotice("Исследование создано. Загрузите пакет документов.");
    });
  }

  async function onUploadFiles(files: FileList | null, asPackage: boolean) {
    if (!files?.length) return;
    if (!activeStudy) {
      setOps((prev) => setOpError(prev, "upload", "Сначала создайте исследование (+ New Study)"));
      return;
    }
    await withOp("upload", async () => {
      const types = asPackage ? ["CHECKLIST", "SYNOPSIS", "SMPC", "OTHER"] : [uploadType];
      let i = 0;
      for (const file of Array.from(files)) {
        const dtype = asPackage ? types[Math.min(i, types.length - 1)] : uploadType;
        await uploadWorkspaceDocument(activeStudy, file, dtype);
        i += 1;
      }
      await refreshSlices(["documents", "progress", "core"], activeStudy);
      setNotice(`Загружено файлов: ${files.length}`);
    }).finally(() => {
      if (fileRef.current) fileRef.current.value = "";
      if (packageRef.current) packageRef.current.value = "";
    });
  }

  async function onClassifyDocument(documentId: string, documentType: string) {
    if (!activeStudy) return;
    await withOp("classify", async () => {
      await classifyWorkspaceDocument(activeStudy, documentId, documentType);
      await refreshSlices(["documents", "progress"], activeStudy);
      setNotice("Классификация обновлена.");
    });
  }

  async function runPreflight() {
    if (!activeStudy) return;
    await withOp("preflight", async () => {
      setPreflight(await getStudyPreflight(activeStudy));
      await refreshSlices(["core", "progress"], activeStudy);
      goTab("preflight");
    });
  }

  async function loadPreview() {
    if (!activeStudy) return;
    await withOp("protocol", async () => {
      const prev = await getWorkspaceProtocolPreview(activeStudy);
      setProtocolPreview(prev as Record<string, unknown>);
      setPreviewField(null);
      setFieldDetail(null);
    });
  }

  async function confirmGenerateDocx() {
    if (!activeStudy) return;
    await withOp("docx", async () => {
      const art = await generateWorkspaceDocx(activeStudy, false);
      setDocxResult(art);
      setShowDocxConfirm(false);
      await refreshSlices(["protocol", "history", "progress"], activeStudy);
      setNotice("DOCX сгенерирован.");
    });
  }

  const header = (workspace?.header || {}) as Record<string, unknown>;
  const cards = (workspace?.summary_cards || {}) as Record<string, unknown>;
  const facts = (workspace?.canonical_facts || []) as Array<Record<string, unknown>>;
  const readiness = (workspace?.readiness || workspace?.readiness_detail || {}) as Record<string, unknown>;
  const progressSteps = (writerProgress?.steps as Array<Record<string, unknown>>) || [];
  const progressBlockers = (writerProgress?.blockers as Array<Record<string, unknown>>) || [];
  const secondaryIssues = (writerProgress?.secondary_issues as Array<Record<string, unknown>>) || [];
  const packageChecklist =
    (writerProgress?.package_checklist as Array<Record<string, unknown>>) ||
    [];
  const progressCounts = (writerProgress?.counts as Record<string, unknown>) || {};
  const progressVersions = (writerProgress?.versions as Record<string, unknown>) || {};
  const progressPreflight = (writerProgress?.preflight as Record<string, unknown>) || {};

  const nextAction = useMemo(() => {
    const fromBackend = fromBackendPrimary(
      writerProgress?.primary_next_action as Record<string, unknown> | undefined,
    );
    if (fromBackend) return fromBackend;
    return computeNextAction({
      loaded: Boolean(workspace),
      docCount: Number(cards.documents ?? documents.length ?? 0),
      criticalConflicts: Number(
        cards.critical_conflicts ?? conflicts.filter((c) => String(c.severity) === "CRITICAL").length,
      ),
      pendingDecisions: Number(
        cards.pending_decisions ??
          decisions.filter(
            (d) => !["APPROVED", "REJECTED", "KEEP_CURRENT"].includes(String(d.status || "").toUpperCase()),
          ).length,
      ),
      sampleSizeStatus: String(cards.sample_size_status || samplePanel?.status || "NONE"),
      statisticsStatus: String(cards.statistics_status || statsPanel?.status || "NONE"),
      protocolStatus: String(cards.protocol_status || "NONE"),
      canFinalize: Boolean(readiness.can_finalize ?? preflight?.can_finalize ?? progressPreflight.can_finalize),
      canDocx: Boolean(preflight?.can_generate_docx ?? progressPreflight.can_generate_docx),
      factsCount: facts.length,
    });
  }, [
    writerProgress,
    workspace,
    cards,
    documents,
    conflicts,
    decisions,
    samplePanel,
    statsPanel,
    readiness,
    preflight,
    progressPreflight,
    facts.length,
  ]);

  const canGenerateDocx = Boolean(preflight?.can_generate_docx ?? progressPreflight.can_generate_docx);
  const hasCriticalBlockers = progressBlockers.some((b) => String(b.severity).toUpperCase() === "CRITICAL");

  const ssBlocked =
    !samplePanel ||
    String(samplePanel.status) === "NO_CALCULATION" ||
    samplePanel.calculated_n == null ||
    String(samplePanel.status || "").toUpperCase().includes("BLOCK");
  const ssApproved = ["APPROVED", "ACCEPTED"].includes(String(samplePanel?.status || "").toUpperCase());

  const statsBlockingReasons = ((statsPanel?.blocking_reasons as string[]) || []).filter(Boolean);
  const primaryBeMissing =
    !statsPanel ||
    String(statsPanel.status) === "NO_PLAN" ||
    statsBlockingReasons.some(
      (b) => String(b).toUpperCase().includes("PRIMARY") || String(b).toUpperCase().includes("REQUIRES_EXPERT"),
    );

  function renderProgressRail() {
    if (!activeStudy || !progressSteps.length) return null;
    return (
      <nav className="progress-rail" aria-label="Writer workflow progress">
        {progressSteps.map((step) => {
          const st = String(step.status || "NOT_STARTED");
          return (
            <button
              key={String(step.id)}
              type="button"
              className={`progress-step ${stepStatusClass(st)}`}
              onClick={() => goTab(String(step.tab || step.id))}
              title={String(step.label)}
            >
              <span className="progress-step-label">{String(step.label)}</span>
              <span className={`status-pill ${stepStatusClass(st)}`}>{stepStatusLabel(st)}</span>
            </button>
          );
        })}
      </nav>
    );
  }

  function renderWizard() {
    if (!showNewStudy) return null;
    return (
      <section className="panel wizard-panel">
        <h2>Новое исследование</h2>
        <ol className="wizard-steps">
          {[
            "Базовая информация",
            "Документы",
            "Анализ",
            "Сводка",
            "Workspace",
          ].map((label, i) => (
            <li key={label} className={wizardStep === i + 1 ? "active" : wizardStep > i + 1 ? "done" : ""}>
              {i + 1}. {label}
            </li>
          ))}
        </ol>

        {wizardStep === 1 && (
          <div>
            <p className="muted">Шаг 1 — базовые метаданные исследования.</p>
            <div className="form-grid">
              <label>
                Title
                <input value={newMeta.title} onChange={(e) => setNewMeta({ ...newMeta, title: e.target.value })} />
              </label>
              <label>
                Sponsor
                <input value={newMeta.sponsor} onChange={(e) => setNewMeta({ ...newMeta, sponsor: e.target.value })} />
              </label>
              <label>
                Product
                <input value={newMeta.product} onChange={(e) => setNewMeta({ ...newMeta, product: e.target.value })} />
              </label>
              <label>
                Dose
                <input value={newMeta.dose} onChange={(e) => setNewMeta({ ...newMeta, dose: e.target.value })} />
              </label>
            </div>
            <div className="header-actions">
              <button type="button" disabled={ops.workflow.busy} onClick={createStudyAndAdvance}>
                Далее →
              </button>
              <button type="button" className="secondary" onClick={() => setShowNewStudy(false)}>
                Отмена
              </button>
            </div>
          </div>
        )}

        {wizardStep === 2 && (
          <div>
            <p className="muted">Шаг 2 — загрузите Checklist, Synopsis/Design и SmPC.</p>
            <div className="header-actions doc-actions">
              <select value={uploadType} onChange={(e) => setUploadType(e.target.value)} aria-label="Document type">
                {DOC_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              <button type="button" disabled={ops.upload.busy || !activeStudy} onClick={() => fileRef.current?.click()}>
                + Upload document
              </button>
              <button type="button" disabled={ops.upload.busy || !activeStudy} onClick={() => packageRef.current?.click()}>
                Upload package
              </button>
            </div>
            <div className="checklist-row">
              {packageChecklist.map((item) => (
                <span
                  key={String(item.type)}
                  className={`status-pill ${statusClass(String(item.state))}`}
                >
                  {String(item.label)}: {stepStatusLabel(item.state)}
                </span>
              ))}
            </div>
            <div className="header-actions">
              <button type="button" disabled={!documents.length} onClick={() => setWizardStep(3)}>
                Далее →
              </button>
              <button type="button" className="secondary" onClick={() => setWizardStep(1)}>
                ← Назад
              </button>
            </div>
          </div>
        )}

        {wizardStep === 3 && (
          <div>
            <p className="muted">Шаг 3 — анализ пакета исследования.</p>
            <button type="button" disabled={ops.workflow.busy || !activeStudy} onClick={analyzePackage}>
              Analyze study package
            </button>
            {analyzeBusy && (
              <ul className="wizard-analyze-stages">
                {ANALYZE_STAGES.map((stage, i) => (
                  <li key={stage} className={i <= analyzeStage ? "active" : ""}>
                    {stage}
                  </li>
                ))}
              </ul>
            )}
            <div className="header-actions">
              <button
                type="button"
                disabled={!Number(progressCounts.facts ?? facts.length)}
                onClick={() => setWizardStep(4)}
              >
                Далее →
              </button>
              <button type="button" className="secondary" onClick={() => setWizardStep(2)}>
                ← Назад
              </button>
            </div>
          </div>
        )}

        {wizardStep === 4 && (
          <div>
            <p className="muted">Шаг 4 — сводка после анализа.</p>
            <div className="card-grid">
              <div className="summary-card">
                <div className="muted">Документы</div>
                <strong>{String(progressCounts.documents ?? documents.length)}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Facts</div>
                <strong>{String(progressCounts.facts ?? facts.length)}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Конфликты</div>
                <strong>{String(progressCounts.conflicts_open ?? conflicts.length)}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Решения (pending)</div>
                <strong>{String(progressCounts.pending_decisions ?? 0)}</strong>
              </div>
            </div>
            <div className="header-actions">
              <button type="button" onClick={() => setWizardStep(5)}>
                Далее →
              </button>
              <button type="button" className="secondary" onClick={() => setWizardStep(3)}>
                ← Назад
              </button>
            </div>
          </div>
        )}

        {wizardStep === 5 && (
          <div>
            <p className="muted">Шаг 5 — продолжите работу в workspace.</p>
            <button
              type="button"
              onClick={() => {
                setShowNewStudy(false);
                setWizardStep(1);
                goTab("overview");
              }}
            >
              Continue to Workspace
            </button>
          </div>
        )}
      </section>
    );
  }

  function renderFieldDrawer() {
    if (!fieldDrawer) return null;
    const src = (fieldDetail?.source || {}) as Record<string, unknown>;
    const ev = (fieldDetail?.evidence || {}) as Record<string, unknown>;
    const dec = (fieldDetail?.decision || {}) as Record<string, unknown>;
    const affected = (fieldDetail?.affected_protocol_sections as string[]) || [];
    return (
      <aside className="field-drawer">
        <div className="field-drawer-header">
          <h3>{fieldDrawer}</h3>
          <button type="button" className="secondary" onClick={() => setFieldDrawer(null)}>
            Закрыть
          </button>
        </div>
        {!fieldDetail ? (
          <p className="muted">Загрузка…</p>
        ) : (
          <>
            <section>
              <h4>FIELD</h4>
              <p>
                <strong>{String(fieldDetail.current_value ?? "—")}</strong>
              </p>
              <p className="muted small">Status: {humanLabel(fieldDetail.status)}</p>
            </section>
            <section>
              <h4>SOURCE</h4>
              <p>{humanLabel(src.document)}</p>
              <p className="muted small">{String(src.page_section || "—")}</p>
              <p className="small">{String(src.excerpt || "—")}</p>
            </section>
            <section>
              <h4>EVIDENCE</h4>
              <p>{String(ev.claim || "—")}</p>
              <p className="muted small">
                Confidence: {ev.confidence == null ? "—" : String(ev.confidence)} ·{" "}
                {humanLabel(ev.verification)}
              </p>
            </section>
            <section>
              <h4>DECISION</h4>
              <p>{humanLabel(dec.status || "—")}</p>
              {dec.current ? (
                <p className="small">{String((dec.current as Record<string, unknown>).question || "")}</p>
              ) : null}
            </section>
            <section>
              <h4>AFFECTED PROTOCOL SECTIONS</h4>
              <ul>
                {affected.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </section>
            <div className="header-actions">
              <button
                type="button"
                className="linkish"
                onClick={() => setReviewFormOpen(true)}
              >
                Review
              </button>
              {reviewFormOpen && (
                <DecisionForm
                  action="review"
                  title={`Review: ${fieldDrawer}`}
                  draft={reviewDraft}
                  onDraftChange={(v) => setReviewDraft({ rationale: v.rationale })}
                  busy={ops.decision.busy}
                  error={ops.decision.error}
                  onCancel={() => setReviewFormOpen(false)}
                  onSubmit={async (values) => {
                    if (!activeStudy || !fieldDrawer || !fieldDetail) return;
                    await withOp("decision", async () => {
                      await reviewCanonicalFact(activeStudy, {
                        field: fieldDrawer,
                        old_value: fieldDetail.current_value,
                        new_value: fieldDetail.current_value,
                        reason: values.rationale,
                        action: "REVIEW",
                      });
                      setNotice(`Review записан для ${fieldDrawer}`);
                      setReviewFormOpen(false);
                      await refreshSlices(["core", "history", "progress"]);
                      await openFieldDrawer(fieldDrawer);
                    });
                  }}
                />
              )}
              <button
                type="button"
                className="linkish"
                onClick={() =>
                  setEditDraft({
                    field: fieldDrawer,
                    value: fieldDetail.current_value == null ? "" : String(fieldDetail.current_value),
                    reason: "",
                  })
                }
              >
                Edit proposal
              </button>
            </div>
          </>
        )}
      </aside>
    );
  }

  const bindings = (protocolPreview?.field_bindings || {}) as Record<string, Record<string, unknown>>;
  const previewSections = (protocolPreview?.sections as Array<Record<string, unknown>>) || [];
  const previewToc =
    (protocolPreview?.toc as Array<Record<string, unknown>>) ||
    previewSections.map((s) => ({ code: s.code, title: s.title }));

  // Study catalog — entry point (no local-only registry)
  if (!activeStudy && !showNewStudy) {
    return (
      <div className="workspace">
        <aside className="workspace-sidebar">
          <div className="workspace-brand">BE Study Workspace</div>
          <p className="muted small">Recommendation ≠ approval · AI assistive only</p>
          <button
            type="button"
            className="btn-primary-nav"
            onClick={() => {
              setShowNewStudy(true);
              setWizardStep(1);
            }}
          >
            + New Study
          </button>
        </aside>
        <div className="workspace-main">
          {globalError && (
            <div className="error-banner" role="alert">
              {globalError}{" "}
              <button type="button" className="linkish" onClick={() => setGlobalError(null)}>
                ✕
              </button>
            </div>
          )}
          {notice && (
            <p className="muted notice-banner">
              {notice}{" "}
              <button type="button" className="linkish" onClick={() => setNotice(null)}>
                ✕
              </button>
            </p>
          )}
          <StudyList
            onOpen={(key) => void openStudy(key)}
            onCreateNew={() => {
              setShowNewStudy(true);
              setWizardStep(1);
            }}
          />
          <section className="panel">
            <h3>Demo</h3>
            <button type="button" className="secondary" disabled={ops.workflow.busy} onClick={runDemoWorkflow}>
              Run demo UPDCB workflow
            </button>
            {ops.workflow.error && (
              <div className="op-error" role="alert">
                {ops.workflow.error}{" "}
                <button type="button" className="linkish" onClick={() => setOps((p) => clearOpError(p, "workflow"))}>
                  ✕
                </button>
              </div>
            )}
          </section>
        </div>
      </div>
    );
  }

  const filteredFacts = dataSearch.trim()
    ? facts.filter((f) => {
        const q = dataSearch.trim().toLowerCase();
        return (
          String(f.field || "").toLowerCase().includes(q) ||
          String(f.canonical_value ?? "").toLowerCase().includes(q) ||
          String(f.source || "").toLowerCase().includes(q)
        );
      })
    : facts;

  return (
    <div className={`workspace ${fieldDrawer ? "with-field-drawer" : ""}`}>
      <aside className="workspace-sidebar">
        <div className="workspace-brand">BE Study Workspace</div>
        <p className="muted small">Recommendation ≠ approval · AI assistive only</p>
        {activeStudy ? (
          <button type="button" className="secondary" onClick={backToCatalog}>
            ← Мои исследования
          </button>
        ) : null}
        <button
          type="button"
          className="btn-primary-nav"
          onClick={() => {
            setShowNewStudy(true);
            setWizardStep(1);
          }}
        >
          + New Study
        </button>
        <nav>
          {PRIMARY_NAV.map((n) => (
            <button
              key={n.id}
              type="button"
              className={tab === n.id ? "nav-item active" : "nav-item"}
              onClick={() => goTab(n.id)}
            >
              {n.label}
            </button>
          ))}
          <div className="nav-divider muted small">Advanced</div>
          <button
            type="button"
            className={tab === "advanced" ? "nav-item active" : "nav-item"}
            onClick={() => {
              goTab("advanced");
              setAdvancedPane("menu");
            }}
          >
            Advanced / Legacy
          </button>
        </nav>
      </aside>

      <div className="workspace-main">
        <header className="study-header">
          <div>
            <div className="study-badges">
              {!activeStudy ? (
                <span className="status-pill status-gray">Нет исследования</span>
              ) : isDemo ? (
                <span className="status-pill status-yellow">Demo / test study</span>
              ) : (
                <span className="status-pill status-green">Real study</span>
              )}
            </div>
            <h1>{String(header.title || header.study_id || activeStudy || "Study Workspace")}</h1>
            <p className="muted">
              Sponsor: {String(header.sponsor || newMeta.sponsor || "—")} · Product:{" "}
              {String(header.product || newMeta.product || "—")} · Dose:{" "}
              {String(header.dose || newMeta.dose || "—")}
            </p>
          </div>
          <div className="header-actions">
            <span className={`status-pill ${statusClass(String(header.readiness_code || ""))}`}>
              {humanLabel(header.overall_readiness || "Not loaded")}
            </span>
            {activeStudy ? (
              <button type="button" disabled={ops.workflow.busy} onClick={analyzePackage}>
                Analyze study package
              </button>
            ) : (
              <button
                type="button"
                disabled={ops.workflow.busy}
                className="btn-primary-nav"
                onClick={() => {
                  setShowNewStudy(true);
                  setWizardStep(1);
                }}
              >
                + New Study
              </button>
            )}
            {activeStudy ? (
              <button type="button" disabled={ops.workflow.busy} onClick={() => void refreshSlices(ALL_SLICES)}>
                Refresh
              </button>
            ) : null}
          </div>
        </header>

        {renderProgressRail()}
        {renderWizard()}

        {globalError && (
          <div className="error-banner" role="alert">
            {globalError}{" "}
            <button type="button" className="linkish" onClick={() => setGlobalError(null)}>
              ✕
            </button>
          </div>
        )}
        {workflowStepErrors && (
          <div className="op-error" role="alert">
            Workflow step errors: {workflowStepErrors}{" "}
            <button type="button" className="linkish" onClick={() => setWorkflowStepErrors(null)}>
              ✕
            </button>
          </div>
        )}
        {notice && (
          <p className="muted notice-banner">
            {notice}{" "}
            <button type="button" className="linkish" onClick={() => setNotice(null)}>
              ✕
            </button>
          </p>
        )}

        {analyzeBusy && tab !== "advanced" && (
          <section className="panel">
            <h3>Анализ пакета…</h3>
            <ul className="wizard-analyze-stages">
              {ANALYZE_STAGES.map((stage, i) => (
                <li key={stage} className={i <= analyzeStage ? "active" : ""}>
                  {stage}
                </li>
              ))}
            </ul>
          </section>
        )}

        {!analyzeBusy && activeStudy && Number(progressCounts.facts ?? facts.length) > 0 && tab === "documents" && (
          <section className="panel analyze-summary">
            <h3>Сводка анализа</h3>
            <div className="card-grid">
              <div className="summary-card">
                <div className="muted">Документы</div>
                <strong>{String(progressCounts.documents ?? documents.length)}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Facts</div>
                <strong>{String(progressCounts.facts ?? facts.length)}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Конфликты</div>
                <strong>{String(progressCounts.conflicts_open ?? 0)}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Knowledge gaps</div>
                <strong>{String(cards.knowledge_gaps ?? "—")}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Рекомендации</div>
                <strong>{String(cards.pending_decisions ?? progressCounts.pending_decisions ?? 0)}</strong>
              </div>
            </div>
          </section>
        )}

        {tab === "overview" && (
          <section className="panel">
            <div
              className={`next-action next-action-${nextAction.severity}`}
              role="button"
              tabIndex={0}
              onClick={() => goTab(nextAction.tab)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") goTab(nextAction.tab);
              }}
            >
              <div className="muted small">СЛЕДУЮЩЕЕ ДЕЙСТВИЕ</div>
              <strong>{nextAction.label}</strong>
              <span className="muted small">
                {" "}
                → {PRIMARY_NAV.find((n) => n.id === nextAction.tab)?.label || nextAction.tab}
              </span>
            </div>

            {secondaryIssues.length > 0 && (
              <div className="secondary-issues">
                <h3 className="small muted">Дополнительные вопросы</h3>
                <ul>
                  {secondaryIssues.map((issue, i) => (
                    <li key={i}>
                      <button type="button" className="linkish" onClick={() => goTab(String(issue.tab))}>
                        {String(issue.label)}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {progressBlockers.length > 0 && (
              <div>
                <h3>Блокеры</h3>
                {progressBlockers.map((b) => (
                  <BlockerCard
                    key={String(b.code)}
                    what={String(b.what || b.code)}
                    why={String(b.why || "—")}
                    where={String(b.where || "—")}
                    actionLabel={String(b.action_label || "Resolve")}
                    severity={String(b.severity)}
                    onResolve={() => goTab(String(b.tab || "overview"))}
                  />
                ))}
              </div>
            )}

            <h2>Обзор</h2>
            {!workspace && (
              <EmptyState
                title="Исследование не загружено"
                why="Нет активного study в workspace."
                next="Создайте новое исследование через + New Study."
                actionLabel="+ New Study"
                onAction={() => {
                  setShowNewStudy(true);
                  setWizardStep(1);
                }}
              />
            )}
            {workspace && (
              <>
                <div className="card-grid">
                  {(
                    [
                      ["Документы", progressCounts.documents ?? cards.documents ?? documents.length],
                      ["Критические конфликты", progressCounts.conflicts_critical ?? cards.critical_conflicts],
                      ["Knowledge gaps", cards.knowledge_gaps],
                      ["Pending decisions", progressCounts.pending_decisions ?? cards.pending_decisions],
                      ["Sample size", humanLabel(cards.sample_size_status || progressVersions.sample_size_status)],
                      ["Statistics", humanLabel(cards.statistics_status || progressVersions.statistics_status)],
                      ["Protocol", humanLabel(cards.protocol_status)],
                    ] as Array<[string, unknown]>
                  ).map(([label, value]) => (
                    <div key={label} className="summary-card">
                      <div className="muted">{label}</div>
                      <strong>{value == null ? "—" : String(value)}</strong>
                    </div>
                  ))}
                </div>
                <p>
                  Lifecycle: <strong>{humanLabel(readiness.lifecycle)}</strong> · FINAL allowed:{" "}
                  {String(readiness.can_finalize ?? progressPreflight.can_finalize ?? false)}
                </p>
              </>
            )}
          </section>
        )}

        {tab === "documents" && (
          <section className="panel">
            <h2>Документы</h2>
            <p className="muted">Загрузите Checklist, Synopsis/Design и SmPC. Типы: .docx, .pdf, .txt, .html/.mhtml</p>
            <div className="header-actions doc-actions">
              <select value={uploadType} onChange={(e) => setUploadType(e.target.value)} aria-label="Document type">
                {DOC_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
              <button type="button" disabled={ops.upload.busy || !activeStudy} onClick={() => fileRef.current?.click()}>
                + Upload document
              </button>
              <button type="button" disabled={ops.upload.busy || !activeStudy} onClick={() => packageRef.current?.click()}>
                Upload package
              </button>
              <button type="button" disabled={ops.workflow.busy || !activeStudy} onClick={analyzePackage}>
                Analyze study package
              </button>
              <input
                ref={fileRef}
                type="file"
                hidden
                accept=".docx,.pdf,.txt,.html,.htm,.mhtml"
                onChange={(e) => onUploadFiles(e.target.files, false)}
              />
              <input
                ref={packageRef}
                type="file"
                hidden
                multiple
                accept=".docx,.pdf,.txt,.html,.htm,.mhtml"
                onChange={(e) => onUploadFiles(e.target.files, true)}
              />
            </div>
            <div className="checklist-row">
              {packageChecklist.map((c) => (
                <span key={String(c.type)} className={`status-pill ${statusClass(String(c.state))}`}>
                  {String(c.label)}: {stepStatusLabel(c.state)}
                </span>
              ))}
            </div>
            {!documents.length ? (
              <EmptyState
                title="Нет документов"
                why="Пакет источников ещё не загружен."
                next="Загрузите Checklist, Synopsis/Design и SmPC."
              />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Version</th>
                    <th>Classification</th>
                    <th>Ingestion</th>
                    <th>Extraction</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((d) => (
                    <tr key={String(d.document_id)}>
                      <td>{String(d.filename)}</td>
                      <td>
                        <select
                          value={String(d.document_type || d.type || "OTHER")}
                          onChange={(e) => onClassifyDocument(String(d.document_id), e.target.value)}
                          aria-label="Document classification"
                        >
                          {DOC_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>
                              {t.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>
                        <span className={`status-pill ${statusClass(String(d.status))}`}>
                          {docStatusLabel(d.status)}
                        </span>
                      </td>
                      <td>{String(d.version ?? 1)}</td>
                      <td>{humanLabel(d.classification || d.classification_status)}</td>
                      <td>{humanLabel(d.ingestion || d.ingestion_status)}</td>
                      <td>{humanLabel(d.extraction || d.extraction_status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        )}

        {tab === "data" && (
          <section className="panel">
            <h2>Данные исследования (Canonical)</h2>
            <p className="muted">
              Текущее значение исследования — не regulatory requirement. Edit proposal не переписывает verified SoT
              молча.
            </p>
            {facts.length > 0 && (
              <label>
                Поиск по загруженным facts
                <input
                  value={dataSearch}
                  onChange={(e) => setDataSearch(e.target.value)}
                  placeholder="field / value / source"
                />
              </label>
            )}
            {!facts.length ? (
              <EmptyState
                title="Нет извлечённых данных"
                why="Пакет ещё не проанализирован или extraction пуст."
                next="Загрузите документы и нажмите Analyze study package."
                actionLabel="Analyze study package"
                onAction={analyzePackage}
              />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Field</th>
                    <th>Value</th>
                    <th>Status</th>
                    <th>Source</th>
                    <th>Evidence</th>
                    <th>Affected sections</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFacts.map((f) => (
                    <tr
                      key={String(f.field)}
                      className={fieldDrawer === String(f.field) ? "row-selected" : ""}
                      onClick={() => openFieldDrawer(String(f.field))}
                    >
                      <td>{String(f.field)}</td>
                      <td>{f.canonical_value == null ? "—" : String(f.canonical_value)}</td>
                      <td>{humanLabel(f.status)}</td>
                      <td>{humanLabel(f.source)}</td>
                      <td className="muted small">{String(f.evidence_id || f.evidence || "—")}</td>
                      <td className="muted small">
                        {Array.isArray(f.affected_sections)
                          ? (f.affected_sections as unknown[]).join(", ")
                          : String(f.affected_sections || "—")}
                      </td>
                      <td onClick={(e) => e.stopPropagation()}>
                        <button type="button" className="linkish" onClick={() => openFieldDrawer(String(f.field))}>
                          Review
                        </button>{" "}
                        <button
                          type="button"
                          className="linkish"
                          onClick={() =>
                            setEditDraft({
                              field: String(f.field),
                              value: f.canonical_value == null ? "" : String(f.canonical_value),
                              reason: "",
                            })
                          }
                        >
                          Edit proposal
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {editDraft && (
              <div className="inline-edit">
                <h3>Edit proposal: {editDraft.field}</h3>
                <p className="muted small">Предложение будет записано как EDIT_PROPOSAL — без silent mutation.</p>
                <label>
                  New value
                  <input
                    value={editDraft.value}
                    onChange={(e) => setEditDraft({ ...editDraft, value: e.target.value })}
                  />
                </label>
                <label>
                  Reason (обязательно)
                  <input
                    value={editDraft.reason}
                    onChange={(e) => setEditDraft({ ...editDraft, reason: e.target.value })}
                  />
                </label>
                <div className="header-actions">
                  <button
                    type="button"
                    disabled={!editDraft.reason.trim()}
                    onClick={async () => {
                      const old = facts.find((x) => String(x.field) === editDraft.field)?.canonical_value;
                      try {
                        await reviewCanonicalFact(activeStudy, {
                          field: editDraft.field,
                          old_value: old,
                          new_value: editDraft.value,
                          reason: editDraft.reason,
                          action: "EDIT_PROPOSAL",
                        });
                        setEditDraft(null);
                        setNotice(`Edit proposal записан для ${editDraft.field} (без silent mutation)`);
                        await refreshSlices(["core", "history", "progress"]);
                        if (fieldDrawer === editDraft.field) await openFieldDrawer(editDraft.field);
                      } catch (err: unknown) {
                        setGlobalError(formatApiError(err, "Edit failed"));
                      }
                    }}
                  >
                    Submit proposal
                  </button>
                  <button type="button" className="secondary" onClick={() => setEditDraft(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </section>
        )}

        {tab === "decisions" && activeStudy && (
          <>
            {decisionOutcome && (
              <div className="decision-outcome-banner">
                <strong>{String(decisionOutcome.message || "Decision approved")}</strong>
                {decisionOutcome.snapshot ? (
                  <p>
                    Snapshot v
                    {String(
                      ((decisionOutcome.snapshot as Record<string, unknown>).version as unknown) ||
                        ((decisionOutcome.snapshot as Record<string, unknown>).snapshot_id as unknown) ||
                        "—",
                    )}
                  </p>
                ) : null}
                {Array.isArray(decisionOutcome.affected_protocol_sections) ? (
                  <p>Affected sections: {(decisionOutcome.affected_protocol_sections as string[]).join(", ")}</p>
                ) : null}
                {decisionOutcome.recalculation_required ? <p>Recalculation required: да</p> : null}
                {Array.isArray(decisionOutcome.affects) && (decisionOutcome.affects as string[]).length > 0 ? (
                  <p>This decision affects: {(decisionOutcome.affects as string[]).join(" / ")}</p>
                ) : null}
              </div>
            )}
            <DecisionPanel
              studyId={activeStudy}
              conflicts={conflicts}
              decisions={decisions}
              busy={ops.decision.busy}
              error={ops.decision.error}
              canApprove={canApproveDecisions}
              reviewer={reviewer}
              onAnalyze={analyzePackage}
              onDismissError={() => setOps((prev) => clearOpError(prev, "decision"))}
              onOutcome={setDecisionOutcome}
              onNotice={setNotice}
              onRefresh={async (slices) => {
                await refreshSlices(slices);
              }}
              onTransportError={(msg) => {
                setOps((prev) => setOpError(prev, "decision", msg));
                setGlobalError(msg);
              }}
              runAction={(fn) => withOp("decision", fn)}
            />
          </>
        )}

        {tab === "evidence" && (
          <section className="panel">
            <h2>Evidence</h2>
            <p className="muted">Claims remain PROPOSED until expert verification.</p>
            <button
              type="button"
              disabled={ops.decision.busy || !activeStudy}
              onClick={() => {
                void withOp("decision", async () => {
                  setReview(await getWriterReview(activeStudy));
                });
              }}
            >
              Load evidence bundle
            </button>
            {review ? (
              <pre className="small preview-block">{JSON.stringify(review, null, 2).slice(0, 4000)}</pre>
            ) : (
              <EmptyState
                title="Evidence не загружен"
                why="Нет открытого review bundle для текущего study."
                next="Загрузите пакет и выполните анализ, затем Load evidence bundle."
              />
            )}
          </section>
        )}

        {tab === "sample-size" && (
          <section className="panel">
            <h2>Sample Size</h2>
            {ssBlocked && (
              <>
                <h3>Sample Size unavailable</h3>
                <p className="muted">Причина:</p>
                <ul>
                  {((samplePanel?.blocking_reasons as string[]) || ["MISSING_VERIFIED_CVINTRA"]).map((b) => (
                    <li key={b}>{humanLabel(b)}</li>
                  ))}
                </ul>
                <button type="button" onClick={() => goTab("decisions")}>
                  Resolve dependency
                </button>
                <EmptyState
                  title="Нет sample size"
                  why="Сначала утвердите необходимые design/variability inputs."
                  next="Закройте блокеры в Решениях / Evidence."
                  actionLabel="Resolve dependency"
                  onAction={() => goTab("decisions")}
                />
              </>
            )}
            {!ssBlocked && samplePanel && (
              <>
                <p>Scenario / controlling: {humanLabel(samplePanel.controlling_parameter || samplePanel.scenario)}</p>
                <p>
                  Calculated N (recommendation): <strong>{String(samplePanel.calculated_n)}</strong>
                </p>
                <p>Assumptions: {humanLabel(samplePanel.assumptions || samplePanel.engine)}</p>
                <p>Engine: {humanLabel(samplePanel.engine || samplePanel.method)}</p>
                <p>
                  Status: {humanLabel(samplePanel.status)}{" "}
                  {ssApproved ? "(approved)" : "(not approved — recommendation only)"}
                </p>
                {ops.sampleSize.error && (
                  <div className="op-error" role="alert">
                    {ops.sampleSize.error}{" "}
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => setOps((p) => clearOpError(p, "sampleSize"))}
                    >
                      ✕
                    </button>
                  </div>
                )}
                <pre className="small">{JSON.stringify(samplePanel.scenarios || samplePanel.inputs || [], null, 2).slice(0, 2000)}</pre>
                {!ssApproved && (
                  <div className="header-actions">
                    <button type="button" className="secondary" onClick={() => goTab("data")}>
                      Review inputs
                    </button>
                    <button
                      type="button"
                      disabled={ops.sampleSize.busy || !samplePanel.latest_calculation_id || !canApproveDecisions}
                      onClick={() => {
                        const id = String(samplePanel.latest_calculation_id);
                        void withOp("sampleSize", async () => {
                          await approveSampleSizeCalculation(id, {
                            reviewer,
                            decision: `Approve N=${String(samplePanel.calculated_n)}`,
                            comment: "Approved from workspace",
                            project_to_study: false,
                          });
                          setNotice("Sample size approved.");
                          await refreshSlices(["engines", "progress", "core", "history"]);
                        });
                      }}
                    >
                      Approve
                    </button>
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {tab === "statistics" && (
          <section className="panel">
            <h2>Statistics</h2>
            {primaryBeMissing && (
              <>
                <p>
                  <strong>
                    Выберите основной endpoint анализа биоэквивалентности (PRIMARY BE) в Решениях — автоматический
                    выбор недоступен.
                  </strong>
                </p>
                {statsBlockingReasons.length > 0 && (
                  <ul>
                    {statsBlockingReasons.map((b) => (
                      <li key={b}>{humanLabel(b)}</li>
                    ))}
                  </ul>
                )}
                <button type="button" onClick={() => goTab("decisions")}>
                  Открыть Решения
                </button>
              </>
            )}
            {statsPanel && (
              <>
                <p>Status: {humanLabel(statsPanel.status)}</p>
                {statsPanel.is_approved ? (
                  <div>
                    <h3>APPROVED STATISTICAL PLAN</h3>
                    <p>Version: {String(statsPanel.version ?? progressVersions.statistics_version ?? "—")}</p>
                    <pre className="small preview-block">{JSON.stringify(statsPanel, null, 2).slice(0, 3000)}</pre>
                  </div>
                ) : (
                  <>
                    <p className="muted">Scenarios (не выбираются автоматически):</p>
                    <pre className="small">{JSON.stringify(statsPanel.scenarios || [], null, 2).slice(0, 2500)}</pre>
                    <p>{String(statsPanel.recommendation_summary || "")}</p>
                    {ops.statistics.error && (
                      <div className="op-error" role="alert">
                        {ops.statistics.error}{" "}
                        <button
                          type="button"
                          className="linkish"
                          onClick={() => setOps((p) => clearOpError(p, "statistics"))}
                        >
                          ✕
                        </button>
                      </div>
                    )}
                    <div className="header-actions">
                      <button type="button" className="secondary" onClick={() => goTab("decisions")}>
                        Review
                      </button>
                      <button
                        type="button"
                        disabled={ops.statistics.busy || !canApproveDecisions || !statsPanel.plan_id || Boolean(statsPanel.is_approved) || (Array.isArray(statsPanel.blocking_reasons) && (statsPanel.blocking_reasons as unknown[]).length > 0)}
                        onClick={() => {
                          void withOp("statistics", async () => {
                            await approveStatisticsPlan(String(statsPanel.plan_id), {
                              reviewer,
                              comment: "Approved from workspace",
                            });
                            setNotice("Statistics plan approved.");
                            await refreshSlices(["engines", "progress", "core", "history"]);
                          });
                        }}
                      >
                        Approve
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
            {!statsPanel && primaryBeMissing && (
              <EmptyState
                title="Нет statistics"
                why="PRIMARY BE endpoint не выбран."
                next="Откройте Решения и утвердите PRIMARY BE."
              />
            )}
          </section>
        )}

        {tab === "protocol" && (
          <section className="panel">
            <h2>Протокол</h2>
            <div className="card-grid">
              <div className="summary-card">
                <div className="muted">Draft version</div>
                <strong>{String(progressVersions.protocol_draft ?? protocolDrafts[0]?.version ?? "—")}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Snapshot version</div>
                <strong>{String(progressVersions.snapshot ?? protocolPreview?.snapshot_version ?? "—")}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Decision set</div>
                <strong>{String(progressCounts.pending_decisions ?? "—")} pending</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Sample Size version</div>
                <strong>{String(progressVersions.sample_size_status ?? samplePanel?.status ?? "—")}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Statistics version</div>
                <strong>{String(progressVersions.statistics_version ?? statsPanel?.version ?? "—")}</strong>
              </div>
              <div className="summary-card">
                <div className="muted">Preflight status</div>
                <strong>{humanLabel(preflight?.message || progressPreflight.message || "—")}</strong>
              </div>
            </div>
            <div className="header-actions">
              <button type="button" disabled={ops.protocol.busy || !activeStudy} onClick={buildDraft}>
                Build draft
              </button>
              <button type="button" disabled={ops.protocol.busy || !activeStudy} onClick={loadPreview}>
                Preview
              </button>
              <button type="button" disabled={ops.preflight.busy || !activeStudy} onClick={runPreflight}>
                Run preflight
              </button>
              <button
                type="button"
                disabled={ops.docx.busy || !activeStudy || !canGenerateDocx || hasCriticalBlockers}
                onClick={() => setShowDocxConfirm(true)}
              >
                Generate DOCX
              </button>
            </div>

            {showDocxConfirm && (
              <div className="docx-confirm">
                <h3>Подтверждение генерации DOCX</h3>
                <ul>
                  <li>Protocol v: {String(progressVersions.protocol_draft ?? protocolDrafts[0]?.version ?? "—")}</li>
                  <li>Snapshot v: {String(progressVersions.snapshot ?? "—")}</li>
                  <li>Statistics v: {String(progressVersions.statistics_version ?? "—")}</li>
                  <li>Sample size v: {String(progressVersions.sample_size_status ?? "—")}</li>
                  <li>
                    Preflight:{" "}
                    {canGenerateDocx ? "PASS" : hasCriticalBlockers ? "BLOCKED" : "WARN"}
                  </li>
                </ul>
                <div className="header-actions">
                  <button type="button" disabled={ops.docx.busy} onClick={confirmGenerateDocx}>
                    Confirm generate
                  </button>
                  <button type="button" className="secondary" onClick={() => setShowDocxConfirm(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {!protocolPreview && !docxResult && (
              <EmptyState
                title="Нет протокола"
                why="Черновик появится после решений и подготовки draft."
                next="Проведите необходимые решения и preflight."
              />
            )}

            {protocolPreview && (
              <div className="preview-layout">
                <nav className="preview-toc">
                  <strong>Table of contents</strong>
                  <ul>
                    {previewToc.map((s, i) => (
                      <li key={String(s.code || s.title || i)}>
                        <a href={`#sec-${String(s.code || i)}`}>{String(s.title || s.code)}</a>
                      </li>
                    ))}
                  </ul>
                </nav>
                <div className="preview-sections">
                  {previewSections.map((s, i) => (
                    <article key={String(s.code || i)} id={`sec-${String(s.code || i)}`} className="preview-section">
                      <h4>{String(s.title || s.code)}</h4>
                      <p>{String(s.body || s.content || "")}</p>
                    </article>
                  ))}
                </div>
                <aside className="preview-side">
                  <h4>Source / field info</h4>
                  {Object.entries(bindings).map(([field, meta]) => (
                    <div key={field} className="preview-binding">
                      <span className="muted small">{String(meta.label || field)}</span>
                      <button
                        type="button"
                        className="linkish"
                        onClick={async () => {
                          setPreviewField(field);
                          if (!activeStudy) return;
                          try {
                            setFieldDetail(await getCanonicalFactDetail(activeStudy, field));
                          } catch (err: unknown) {
                            setGlobalError(formatApiError(err, "Field detail failed"));
                          }
                        }}
                      >
                        {meta.value == null ? "—" : String(meta.value)}
                      </button>
                    </div>
                  ))}
                  {previewField && fieldDetail && (
                    <div className="preview-field-detail">
                      <h5>{previewField}</h5>
                      <p>{String(fieldDetail.current_value ?? "—")}</p>
                      <p className="muted small">{String(((fieldDetail.source || {}) as Record<string, unknown>).excerpt || "")}</p>
                    </div>
                  )}
                </aside>
              </div>
            )}

            {(docxResult || artifacts.length > 0) && (
              <div className="docx-result">
                <h3>DOCX</h3>
                {(docxResult ? [docxResult] : artifacts).slice(0, 3).map((art) => {
                  const aid = String(art.artifact_id || art.id || "");
                  return (
                    <div key={aid} className="summary-card">
                      <p>Artifact: {aid || "—"}</p>
                      <p>Version: {String(art.version ?? "—")}</p>
                      <p className="mono">sha256: {String(art.sha256 || art.checksum || "—")}</p>
                      <p>Created: {String(art.created_at || art.created || "—")}</p>
                      {aid && activeStudy ? (
                        <a href={downloadWorkspaceArtifactUrl(activeStudy, aid)} download>
                          Download DOCX
                        </a>
                      ) : null}
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}

        {tab === "preflight" && (
          <section className="panel">
            <h2>Проверка (Final check)</h2>
            <p>
              {humanLabel(preflight?.message || progressPreflight.message || "Run preflight first")} · FINALIZE:{" "}
              {String(preflight?.can_finalize ?? progressPreflight.can_finalize ?? false)} · DOCX:{" "}
              {String(preflight?.can_generate_docx ?? progressPreflight.can_generate_docx ?? false)}
            </p>
            {!preflight && (
              <EmptyState
                title="Preflight не выполнен"
                why="Нет результатов проверки."
                next="Нажмите Run preflight на вкладке Протокол."
                actionLabel="Run preflight"
                onAction={runPreflight}
              />
            )}
            {progressBlockers.length > 0 && (
              <div>
                <h3>Actionable blockers</h3>
                {progressBlockers.map((b) => (
                  <BlockerCard
                    key={String(b.code)}
                    what={String(b.what || b.code)}
                    why={String(b.why || "—")}
                    where={String(b.where || "—")}
                    actionLabel={String(b.action_label || "Resolve")}
                    severity={String(b.severity)}
                    onResolve={() => goTab(String(b.tab || "overview"))}
                  />
                ))}
              </div>
            )}
            <ul className="blocker-list">
              {(
                ((preflight?.critical_blockers as Array<Record<string, unknown>>) ||
                  ((preflight?.checks as Array<Record<string, unknown>>) || []).filter((c) => !c.ok)) as Array<
                  Record<string, unknown>
                >
              ).map((c) => {
                const code = String(c.code || c.message || "");
                let go: NavId = "decisions";
                let goLabel = "Открыть Решения";
                if (/SAMPLE|N_SUBJECT|SAMPLE_SIZE/i.test(code + String(c.message))) {
                  go = "sample-size";
                  goLabel = "Открыть Sample Size";
                } else if (/STAT|PRIMARY_BE|AUC/i.test(code + String(c.message))) {
                  go = "statistics";
                  goLabel = "Открыть Statistics";
                } else if (/EVIDENCE|RESEARCH/i.test(code + String(c.message))) {
                  go = "evidence";
                  goLabel = "Открыть Evidence";
                } else if (/DOC|UPLOAD|PACKAGE/i.test(code + String(c.message))) {
                  go = "documents";
                  goLabel = "Открыть Документы";
                }
                return (
                  <li key={code + String(c.message)}>
                    <BlockerCard
                      what={humanLabel(c.code) || "Blocker"}
                      why={String(c.message || c.why || c.detail || "")}
                      where={goLabel.replace("Открыть ", "")}
                      actionLabel={goLabel}
                      severity={String(c.severity || "CRITICAL")}
                      onResolve={() => goTab(go)}
                    />
                  </li>
                );
              })}
            </ul>
          </section>
        )}

        {tab === "history" && (
          <section className="panel">
            <h2>История</h2>
            {snapshots.length > 0 && (
              <>
                <h3>Snapshots</h3>
                <ul>
                  {snapshots.map((s) => (
                    <li key={String(s.snapshot_id || s.id)}>
                      v{String(s.version ?? "—")} · {String(s.created_at || s.reason || "")}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {!audit.length ? (
              <EmptyState
                title="Нет событий"
                why="Аудит пуст."
                next="Создайте study, загрузите документы или выполните review."
              />
            ) : (
              <ul>
                {audit.map((e) => (
                  <li key={String(e.id)}>
                    {String(e.timestamp)} · {String(e.who)} · {humanLabel(e.event)} · {String(e.what)}
                    {e.reason ? ` · reason: ${String(e.reason)}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {tab === "advanced" && (
          <section className="panel">
            <h2>Advanced / Legacy</h2>
            <p className="muted">Инженерные и beta-инструменты. Не требуются для обычного writer workflow.</p>
            <div className="header-actions">
              <button type="button" onClick={() => setAdvancedPane("beta")}>
                Controlled beta
              </button>
              <button type="button" onClick={() => setAdvancedPane("legacy")}>
                Legacy console
              </button>
              <button
                type="button"
                onClick={async () => {
                  void withOp("workflow", async () => {
                    const r = await getBetaCases();
                    setBetaCases((r.cases as Array<Record<string, unknown>>) || []);
                    setAdvancedPane("beta");
                  });
                }}
              >
                Load beta cases
              </button>
              <button type="button" className="secondary" disabled={ops.workflow.busy} onClick={runDemoWorkflow}>
                Run demo UPDCB workflow
              </button>
            </div>
            {advancedPane === "beta" && (
              <div>
                <h3>Controlled beta</h3>
                <ControlledBetaDashboard />
                <ul>
                  {betaCases.map((c) => (
                    <li key={String(c.case_id)}>
                      <strong>{String(c.case_id)}</strong> [{String(c.origin)}] {String(c.description)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {advancedPane === "legacy" && (
              <div>
                <h3>Legacy console</h3>
                <Dashboard />
              </div>
            )}
          </section>
        )}
      </div>

      {renderFieldDrawer()}

      <input
        ref={fileRef}
        type="file"
        hidden
        accept=".docx,.pdf,.txt,.html,.htm,.mhtml"
        onChange={(e) => onUploadFiles(e.target.files, false)}
      />
      <input
        ref={packageRef}
        type="file"
        hidden
        multiple
        accept=".docx,.pdf,.txt,.html,.htm,.mhtml"
        onChange={(e) => onUploadFiles(e.target.files, true)}
      />
    </div>
  );
}

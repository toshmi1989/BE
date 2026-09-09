/** Pipeline navigation. Five steps: documents → data → gaps → decisions → protocol. */

export type NavId =
  | "overview"
  | "documents"
  | "data"
  | "gaps"
  | "decisions"
  | "protocol"
  | "history"
  | "advanced";

export type NextAction = {
  label: string;
  tab: NavId;
  severity: "info" | "warn" | "critical";
};

/** Older payloads still name engine tabs; they live inside a pipeline step now. */
const TAB_ALIASES: Record<string, NavId> = {
  extraction: "data",
  evidence: "gaps",
  "knowledge-gaps": "gaps",
  research: "gaps",
  "sample-size": "decisions",
  sample_size: "decisions",
  statistics: "decisions",
  preflight: "protocol",
  docx: "protocol",
};

const ALLOWED: NavId[] = [
  "overview",
  "documents",
  "data",
  "gaps",
  "decisions",
  "protocol",
  "history",
  "advanced",
];

export function normalizeTab(tab: unknown): NavId {
  const t = String(tab || "overview");
  const aliased = TAB_ALIASES[t] || t;
  return (ALLOWED.includes(aliased as NavId) ? aliased : "overview") as NavId;
}

/** Fallback when writer-progress API unavailable. */
export function computeNextAction(input: {
  loaded: boolean;
  docCount: number;
  criticalConflicts: number;
  pendingDecisions: number;
  openGaps?: number;
  sampleSizeStatus: string;
  statisticsStatus: string;
  protocolStatus: string;
  canFinalize: boolean;
  canDocx: boolean;
  factsCount: number;
}): NextAction {
  if (!input.loaded || input.docCount === 0) {
    return { label: "Загрузите документы", tab: "documents", severity: "info" };
  }
  if (input.factsCount === 0) {
    return { label: "Анализируйте пакет исследования", tab: "documents", severity: "warn" };
  }
  if (input.criticalConflicts > 0) {
    return { label: "Разрешите критический конфликт", tab: "data", severity: "critical" };
  }
  if (Number(input.openGaps || 0) > 0) {
    return { label: "Закройте пробелы в данных", tab: "gaps", severity: "warn" };
  }
  if (input.pendingDecisions > 0) {
    return { label: "Примите экспертные решения", tab: "decisions", severity: "warn" };
  }
  const ss = (input.sampleSizeStatus || "").toUpperCase();
  if (!ss || ss === "NONE" || ss === "NO_CALCULATION" || ss.includes("BLOCK") || (!ss.includes("APPROV") && !ss.includes("ACCEPT"))) {
    return { label: "Рассчитайте и утвердите Sample Size", tab: "decisions", severity: "warn" };
  }
  const st = (input.statisticsStatus || "").toUpperCase();
  if (!st || st === "NONE" || st === "NO_PLAN" || st.includes("BLOCK") || !st.includes("APPROV")) {
    return { label: "Утвердите статистический план", tab: "decisions", severity: "warn" };
  }
  if (!input.canFinalize) {
    return { label: "Запустите финальную проверку", tab: "protocol", severity: "warn" };
  }
  if (input.canDocx) {
    return { label: "Сгенерируйте DOCX", tab: "protocol", severity: "info" };
  }
  return { label: "Откройте Preview", tab: "protocol", severity: "info" };
}

export function fromBackendPrimary(primary: Record<string, unknown> | null | undefined): NextAction | null {
  if (!primary) return null;
  const label = String(primary.label_ru || primary.label || "").trim();
  if (!label) return null;
  const sev = String(primary.severity || "info");
  return {
    label,
    tab: normalizeTab(primary.tab),
    severity: sev === "critical" ? "critical" : sev === "warn" ? "warn" : "info",
  };
}

/** Five pipeline steps derived from the backend's finer-grained step list. */
export type PipelineStep = {
  id: NavId;
  index: number;
  label: string;
  status: string;
  sources: string[];
};

const PIPELINE: Array<{ id: NavId; label: string; from: string[] }> = [
  { id: "documents", label: "Документы", from: ["documents"] },
  { id: "data", label: "Данные", from: ["extraction"] },
  { id: "gaps", label: "Пробелы", from: [] },
  { id: "decisions", label: "Решения", from: ["decisions", "sample_size", "statistics"] },
  { id: "protocol", label: "Протокол", from: ["protocol", "preflight", "docx"] },
];

const STATUS_RANK: Record<string, number> = {
  BLOCKED: 0,
  IN_PROGRESS: 1,
  READY: 2,
  NOT_STARTED: 3,
  COMPLETED: 4,
};

function worstStatus(statuses: string[]): string {
  if (!statuses.length) return "NOT_STARTED";
  return statuses.reduce((worst, s) => {
    const a = STATUS_RANK[String(worst).toUpperCase()] ?? 3;
    const b = STATUS_RANK[String(s).toUpperCase()] ?? 3;
    return b < a ? s : worst;
  });
}

export function buildPipelineSteps(
  backendSteps: Array<Record<string, unknown>>,
  gaps: { total: number; open: number } | null,
): PipelineStep[] {
  const byId = new Map<string, string>();
  for (const s of backendSteps) {
    byId.set(String(s.id || ""), String(s.status || "NOT_STARTED"));
  }
  return PIPELINE.map((step, i) => {
    let status: string;
    if (step.id === "gaps") {
      if (!gaps) status = byId.get("extraction") === "COMPLETED" ? "READY" : "NOT_STARTED";
      else if (gaps.open > 0) status = "IN_PROGRESS";
      else if (gaps.total > 0) status = "COMPLETED";
      else status = byId.get("extraction") === "COMPLETED" ? "COMPLETED" : "NOT_STARTED";
    } else {
      status = worstStatus(step.from.map((id) => byId.get(id) || "NOT_STARTED"));
    }
    return { id: step.id, index: i + 1, label: step.label, status, sources: step.from };
  });
}

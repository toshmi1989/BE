/** Phase 27 — next action + nav types. Prefer backend primary_next_action when present. */

export type NavId =
  | "overview"
  | "documents"
  | "data"
  | "decisions"
  | "evidence"
  | "sample-size"
  | "statistics"
  | "protocol"
  | "preflight"
  | "history"
  | "advanced";

export type NextAction = {
  label: string;
  tab: NavId;
  severity: "info" | "warn" | "critical";
};

export function normalizeTab(tab: unknown): NavId {
  const t = String(tab || "overview");
  const allowed: NavId[] = [
    "overview",
    "documents",
    "data",
    "decisions",
    "evidence",
    "sample-size",
    "statistics",
    "protocol",
    "preflight",
    "history",
    "advanced",
  ];
  return (allowed.includes(t as NavId) ? t : "overview") as NavId;
}

/** Fallback when writer-progress API unavailable. */
export function computeNextAction(input: {
  loaded: boolean;
  docCount: number;
  criticalConflicts: number;
  pendingDecisions: number;
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
    return { label: "Разрешите критический конфликт", tab: "decisions", severity: "critical" };
  }
  if (input.pendingDecisions > 0) {
    return { label: "Примите экспертные решения", tab: "decisions", severity: "warn" };
  }
  const ss = (input.sampleSizeStatus || "").toUpperCase();
  if (!ss || ss === "NONE" || ss === "NO_CALCULATION" || ss.includes("BLOCK") || !ss.includes("APPROV") && !ss.includes("ACCEPT")) {
    return { label: "Проверьте Sample Size", tab: "sample-size", severity: "warn" };
  }
  const st = (input.statisticsStatus || "").toUpperCase();
  if (!st || st === "NONE" || st === "NO_PLAN" || st.includes("BLOCK") || !st.includes("APPROV")) {
    return { label: "Утвердите Statistics", tab: "statistics", severity: "warn" };
  }
  if (!input.canFinalize) {
    return { label: "Запустите финальную проверку", tab: "preflight", severity: "warn" };
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

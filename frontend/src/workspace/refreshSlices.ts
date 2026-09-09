/** Named workspace refresh slices — replace blanket refreshAll. */

export type RefreshSlice =
  | "core"
  | "documents"
  | "decisions"
  | "gaps"
  | "engines"
  | "protocol"
  | "history"
  | "progress";

export const ALL_SLICES: RefreshSlice[] = [
  "core",
  "documents",
  "decisions",
  "gaps",
  "engines",
  "protocol",
  "history",
  "progress",
];

const AFFECT_ALIASES: Record<string, RefreshSlice[]> = {
  protocol: ["protocol", "progress", "core"],
  "sample size": ["engines", "progress", "core"],
  samplesize: ["engines", "progress", "core"],
  sample_size: ["engines", "progress", "core"],
  statistics: ["engines", "progress", "core"],
  stats: ["engines", "progress", "core"],
  decisions: ["decisions", "gaps", "progress", "core"],
  decision: ["decisions", "gaps", "progress", "core"],
  documents: ["documents", "progress", "core"],
  evidence: ["decisions", "gaps", "progress"],
  gaps: ["gaps", "decisions", "progress"],
  history: ["history"],
  readiness: ["core", "progress"],
  preflight: ["core", "progress"],
};

/** Map decision `affects` payload into authoritative refresh slices. Always includes decisions. */
export function slicesFromAffects(affects: unknown): RefreshSlice[] {
  const out = new Set<RefreshSlice>(["decisions", "progress"]);
  const list = Array.isArray(affects)
    ? affects
    : typeof affects === "string"
      ? [affects]
      : [];
  for (const item of list) {
    const key = String(item || "")
      .trim()
      .toLowerCase()
      .replace(/[-–—]/g, " ");
    const mapped = AFFECT_ALIASES[key] || AFFECT_ALIASES[key.replace(/\s+/g, "_")];
    if (mapped) {
      for (const s of mapped) out.add(s);
    } else if (key) {
      out.add("core");
    }
  }
  return Array.from(out);
}

export function uniqueSlices(...groups: RefreshSlice[][]): RefreshSlice[] {
  const out = new Set<RefreshSlice>();
  for (const g of groups) {
    for (const s of g) out.add(s);
  }
  return Array.from(out);
}

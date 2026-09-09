import { describe, expect, it } from "vitest";
import { buildPipelineSteps, computeNextAction, normalizeTab } from "./nextAction";

describe("normalizeTab", () => {
  it("keeps the five pipeline steps", () => {
    for (const t of ["documents", "data", "gaps", "decisions", "protocol"]) {
      expect(normalizeTab(t)).toBe(t);
    }
  });

  it("routes engine tabs into the step that owns them", () => {
    expect(normalizeTab("sample-size")).toBe("decisions");
    expect(normalizeTab("statistics")).toBe("decisions");
    expect(normalizeTab("preflight")).toBe("protocol");
    expect(normalizeTab("evidence")).toBe("gaps");
  });

  it("falls back to overview for unknown tabs", () => {
    expect(normalizeTab("something-else")).toBe("overview");
  });
});

describe("computeNextAction", () => {
  const base = {
    loaded: true,
    docCount: 2,
    criticalConflicts: 0,
    pendingDecisions: 0,
    sampleSizeStatus: "ACCEPTED",
    statisticsStatus: "APPROVED",
    protocolStatus: "READY",
    canFinalize: true,
    canDocx: true,
    factsCount: 10,
  };

  it("sends the writer to gaps before decisions", () => {
    const action = computeNextAction({ ...base, openGaps: 2, pendingDecisions: 3 });
    expect(action.tab).toBe("gaps");
  });

  it("does not mention gaps once they are closed", () => {
    const action = computeNextAction({ ...base, openGaps: 0, pendingDecisions: 3 });
    expect(action.tab).toBe("decisions");
  });
});

describe("buildPipelineSteps", () => {
  const backend = [
    { id: "documents", status: "COMPLETED" },
    { id: "extraction", status: "COMPLETED" },
    { id: "decisions", status: "IN_PROGRESS" },
    { id: "sample_size", status: "BLOCKED" },
    { id: "statistics", status: "COMPLETED" },
    { id: "protocol", status: "COMPLETED" },
    { id: "preflight", status: "BLOCKED" },
    { id: "docx", status: "BLOCKED" },
  ];

  it("collapses engine steps into five numbered steps", () => {
    const steps = buildPipelineSteps(backend, { total: 3, open: 0 });
    expect(steps.map((s) => s.id)).toEqual([
      "documents",
      "data",
      "gaps",
      "decisions",
      "protocol",
    ]);
    expect(steps.map((s) => s.index)).toEqual([1, 2, 3, 4, 5]);
  });

  it("shows the worst status of the steps it groups", () => {
    const steps = buildPipelineSteps(backend, { total: 3, open: 0 });
    expect(steps.find((s) => s.id === "decisions")?.status).toBe("BLOCKED");
    expect(steps.find((s) => s.id === "protocol")?.status).toBe("BLOCKED");
  });

  it("marks gaps in progress while any remain open", () => {
    const open = buildPipelineSteps(backend, { total: 3, open: 2 });
    expect(open.find((s) => s.id === "gaps")?.status).toBe("IN_PROGRESS");
    const closed = buildPipelineSteps(backend, { total: 3, open: 0 });
    expect(closed.find((s) => s.id === "gaps")?.status).toBe("COMPLETED");
  });
});

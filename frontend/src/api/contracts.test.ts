import { describe, expect, it } from "vitest";
import {
  ContractError,
  getStatisticsPanel,
  parseAuthUser,
  parsePreflightResponse,
  parseStatisticsResponse,
  parseStudyListResponse,
  parseWriterProgress,
} from "./contracts";

describe("parseStatisticsResponse", () => {
  it("parses full { study_id, latest, panel, plans } shape", () => {
    const parsed = parseStatisticsResponse({
      study_id: "STUDY-1",
      latest: { id: "plan-1", status: "DRAFT" },
      panel: {
        study_id: "STUDY-1",
        plan_id: "plan-1",
        status: "DRAFT",
        blocking_reasons: ["PRIMARY_BE_MISSING"],
        is_approved: false,
      },
      plans: [{ id: "plan-1" }],
    });
    expect(parsed.study_id).toBe("STUDY-1");
    expect(parsed.latest?.id).toBe("plan-1");
    expect(parsed.plans).toHaveLength(1);
    expect(parsed.panel?.status).toBe("DRAFT");
    expect(parsed.panel?.blocking_reasons).toEqual(["PRIMARY_BE_MISSING"]);
    expect(getStatisticsPanel(parsed)?.plan_id).toBe("plan-1");
  });

  it("allows missing panel without inventing one", () => {
    const parsed = parseStatisticsResponse({
      study_id: "STUDY-2",
      latest: null,
      plans: [],
    });
    expect(parsed.panel).toBeUndefined();
    expect(getStatisticsPanel(parsed)).toBeUndefined();
    expect(parsed.latest).toBeNull();
  });

  it("throws ContractError when panel is present but not an object", () => {
    expect(() =>
      parseStatisticsResponse({
        study_id: "S",
        latest: null,
        panel: "not-an-object",
        plans: [],
      }),
    ).toThrow(ContractError);
  });

  it("throws when study_id missing", () => {
    expect(() => parseStatisticsResponse({ latest: null, plans: [] })).toThrow(/study_id/);
  });

  it("throws when plans is not an array", () => {
    expect(() =>
      parseStatisticsResponse({ study_id: "S", latest: null, plans: {} }),
    ).toThrow(ContractError);
  });
});

describe("other contract parsers", () => {
  it("parseStudyListResponse", () => {
    const list = parseStudyListResponse({
      studies: [
        {
          study_id: "uuid-1",
          study_key: "KEY-1",
          title: "Demo",
          sponsor: null,
          product: "X",
          dose: null,
          lifecycle: "DRAFT",
          status: "ACTIVE",
          readiness: "NOT_STARTED",
          readiness_label: "Not started",
          document_count: 2,
          created_at: null,
          updated_at: null,
        },
      ],
      total: 1,
      offset: 0,
      limit: 20,
      organization_id: "org-1",
    });
    expect(list.studies[0].study_key).toBe("KEY-1");
    expect(list.total).toBe(1);
  });

  it("parseAuthUser", () => {
    const u = parseAuthUser({
      user_id: "u1",
      email: "a@b.c",
      display_name: "A",
      organization_id: null,
      role: "ADMIN",
    });
    expect(u.email).toBe("a@b.c");
    expect(u.organization_id).toBeNull();
  });

  it("parseWriterProgress requires steps", () => {
    expect(() => parseWriterProgress({ study_id: "S" })).toThrow(ContractError);
    const p = parseWriterProgress({
      study_id: "S",
      steps: [{ id: "documents", label: "Docs", status: "READY", tab: "documents" }],
      primary_next_action: { label: "Upload" },
    });
    expect(p.steps[0].id).toBe("documents");
  });

  it("parsePreflightResponse includes stale_dependencies when present", () => {
    const pf = parsePreflightResponse({
      study_id: "S",
      categories: ["PROTOCOL"],
      checks: [
        {
          category: "PROTOCOL",
          code: "OK",
          severity: "INFO",
          message: "ok",
          ok: true,
        },
      ],
      critical_blockers: [],
      can_finalize: true,
      can_generate_docx: true,
      stale_dependencies: { stale: false, reasons: [] },
    });
    expect(pf.stale_dependencies?.stale).toBe(false);
  });
});

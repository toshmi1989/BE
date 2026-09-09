import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  DecisionForm,
  normalizeDecisionOptions,
  validateDecisionForm,
  type DecisionFormValues,
} from "./DecisionForm";
import { collectWorkflowStepErrors, formatWorkflowStepErrors } from "../workspace/workflowSteps";

describe("normalizeDecisionOptions", () => {
  it("uses code/label and never renders [object Object]", () => {
    const opts = normalizeDecisionOptions([
      "STANDARD_2X2_CROSSOVER",
      { code: "REPLICATE_DESIGN", label: "Replicate design" },
      { value: "PARALLEL", label: "Parallel" },
      { nested: true } as never,
    ]);
    expect(opts.map((o) => o.value)).toEqual([
      "STANDARD_2X2_CROSSOVER",
      "REPLICATE_DESIGN",
      "PARALLEL",
    ]);
    expect(opts.every((o) => !o.label.includes("[object Object]"))).toBe(true);
  });
});

describe("validateDecisionForm", () => {
  it("requires rationale for approve/reject/modify/review", () => {
    expect(validateDecisionForm("approve", { rationale: "", selectedOption: "15" })).toBeTruthy();
    expect(validateDecisionForm("reject", { rationale: "" })).toBeTruthy();
    expect(validateDecisionForm("modify", { rationale: "ok", selectedOption: "" })).toBeTruthy();
    expect(validateDecisionForm("review", { rationale: "" })).toBeTruthy();
    expect(validateDecisionForm("approve", { rationale: "ok", selectedOption: "15" })).toBeNull();
  });

  it("requires evidence reason for request-evidence", () => {
    expect(validateDecisionForm("request-evidence", { rationale: "" })).toBeTruthy();
    expect(
      validateDecisionForm("request-evidence", { rationale: "", evidenceReason: "need SmPC page" }),
    ).toBeNull();
  });
});

describe("DecisionForm draft retention", () => {
  it("shows retained draft and keeps edits via onDraftChange", () => {
    let draft: DecisionFormValues = {
      rationale: "saved rationale",
      selectedOption: "30 мг",
      evidenceRefs: "ev-1",
    };

    const { rerender } = render(
      <DecisionForm
        action="modify"
        options={["15 мг", "30 мг"]}
        draft={draft}
        onDraftChange={(d) => {
          draft = d;
        }}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    );

    const rationale = screen.getByLabelText(/Rationale/i) as HTMLTextAreaElement;
    expect(rationale.value).toBe("saved rationale");

    fireEvent.change(rationale, { target: { value: "updated draft" } });
    expect(draft.rationale).toBe("updated draft");

    rerender(
      <DecisionForm
        action="modify"
        options={["15 мг", "30 мг"]}
        draft={draft}
        onDraftChange={(d) => {
          draft = d;
        }}
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    );

    expect((screen.getByLabelText(/Rationale/i) as HTMLTextAreaElement).value).toBe("updated draft");
  });

  it("blocks submit without required fields", () => {
    const submitted: DecisionFormValues[] = [];
    render(
      <DecisionForm
        action="approve"
        options={["A", "B"]}
        onSubmit={(v) => {
          submitted.push(v);
        }}
        onCancel={() => undefined}
      />,
    );

    fireEvent.submit(screen.getByRole("button", { name: /Утвердить/i }).closest("form")!);
    expect(submitted).toHaveLength(0);
    expect(screen.getByRole("alert").textContent).toMatch(/обязательн/i);
  });

  it("renders code/label option objects without [object Object]", () => {
    render(
      <DecisionForm
        action="approve"
        options={[
          { code: "STANDARD_2X2_CROSSOVER", label: "2×2 crossover" },
          { code: "REPLICATE_DESIGN", label: "Replicate" },
        ]}
        defaultOption="STANDARD_2X2_CROSSOVER"
        onSubmit={() => undefined}
        onCancel={() => undefined}
      />,
    );
    expect(screen.queryByText(/\[object Object\]/i)).toBeNull();
    expect(screen.getByText(/2×2 crossover/i)).toBeTruthy();
    expect(screen.getByText(/Replicate/i)).toBeTruthy();
  });
});

describe("collectWorkflowStepErrors", () => {
  it("collects ERROR steps even when overall HTTP would be 200", () => {
    const errors = collectWorkflowStepErrors([
      { name: "extract", status: "COMPLETED" },
      { name: "classify", status: "ERROR", error: "bad mime" },
      { id: "research", state: "FAILED", message: "timeout" },
      { step: "okish", ok: false, detail: "partial" },
    ]);
    expect(errors).toHaveLength(3);
    expect(formatWorkflowStepErrors(errors)).toContain("classify");
    expect(formatWorkflowStepErrors(errors)).toContain("bad mime");
  });

  it("returns empty for non-arrays", () => {
    expect(collectWorkflowStepErrors(null)).toEqual([]);
    expect(collectWorkflowStepErrors(undefined)).toEqual([]);
  });
});

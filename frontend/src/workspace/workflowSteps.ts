/** Extract per-step ERROR messages from workflow/run responses (HTTP 200 may still contain step errors). */

export type WorkflowStepError = {
  step: string;
  message: string;
  status: string;
};

export function collectWorkflowStepErrors(steps: unknown): WorkflowStepError[] {
  if (!Array.isArray(steps)) return [];
  const errors: WorkflowStepError[] = [];
  for (const raw of steps) {
    if (!raw || typeof raw !== "object") continue;
    const step = raw as Record<string, unknown>;
    const status = String(step.status || step.state || step.result || "").toUpperCase();
    const hasErrorFlag =
      status === "ERROR" ||
      status === "FAILED" ||
      status === "FAILURE" ||
      step.ok === false ||
      Boolean(step.error);
    if (!hasErrorFlag) continue;
    const name = String(step.name || step.step || step.id || step.code || "step");
    const message = String(
      step.error || step.message || step.detail || step.reason || `Step ${name} failed`,
    );
    errors.push({ step: name, message, status: status || "ERROR" });
  }
  return errors;
}

export function formatWorkflowStepErrors(errors: WorkflowStepError[]): string {
  if (!errors.length) return "";
  return errors.map((e) => `${e.step}: ${e.message}`).join(" · ");
}

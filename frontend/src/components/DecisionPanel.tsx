import { useEffect, useState } from "react";
import {
  approveStudyDecision,
  getDecisionApplicability,
  getDecisionBlockers,
  getDecisionDependencies,
  getDecisionEvidence,
  modifyStudyDecision,
  postExpertDecision,
  rejectStudyDecision,
  requestDecisionEvidence,
} from "../api/client";
import {
  DecisionForm,
  type DecisionFormAction,
  type DecisionFormValues,
} from "./DecisionForm";
import { humanLabel } from "../writerLabels";
import { slicesFromAffects, type RefreshSlice } from "../workspace/refreshSlices";

function statusClass(code: string | undefined): string {
  if (!code) return "status-gray";
  const u = code.toUpperCase();
  if (u === "READY" || u === "APPROVED" || u === "ACCEPTED" || u === "UPLOADED" || u === "COMPLETED" || u === "PRESENT" || u === "OPEN") {
    return "status-green";
  }
  if (u === "BLOCKED" || u === "CRITICAL" || u === "ERROR" || u === "MISSING") return "status-red";
  if (u.includes("WARN") || u.includes("REVIEW") || u.includes("PENDING") || u.includes("PROCESS") || u === "IN_PROGRESS") {
    return "status-yellow";
  }
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

type FormTarget =
  | { kind: "conflict"; id: string; action: DecisionFormAction }
  | { kind: "decision"; id: string; action: DecisionFormAction }
  | null;

export type DecisionPanelProps = {
  studyId: string;
  conflicts: Array<Record<string, unknown>>;
  decisions: Array<Record<string, unknown>>;
  busy: boolean;
  error: string | null;
  canApprove: boolean;
  reviewer: string;
  onAnalyze: () => void;
  onDismissError: () => void;
  onOutcome: (outcome: Record<string, unknown>) => void;
  onNotice: (msg: string) => void;
  onRefresh: (slices: RefreshSlice[]) => Promise<void>;
  onTransportError: (msg: string) => void;
  runAction: (fn: () => Promise<void>) => Promise<void>;
};

export function DecisionPanel(props: DecisionPanelProps) {
  const {
    studyId,
    conflicts,
    decisions,
    busy,
    error,
    canApprove,
    reviewer,
    onAnalyze,
    onDismissError,
    onOutcome,
    onNotice,
    onRefresh,
    onTransportError,
    runAction,
  } = props;

  const [formTarget, setFormTarget] = useState<FormTarget>(null);
  const [drafts, setDrafts] = useState<Record<string, DecisionFormValues>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailBusy, setDetailBusy] = useState(false);
  const [evidence, setEvidence] = useState<Record<string, unknown> | null>(null);
  const [dependencies, setDependencies] = useState<Record<string, unknown> | null>(null);
  const [blockers, setBlockers] = useState<Record<string, unknown> | null>(null);
  const [applicability, setApplicability] = useState<Record<string, unknown> | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const selectedDecision = decisions.find(
    (d) => String(d.id || d.decision_id) === selectedId,
  );
  const selectedConflict = conflicts.find((c) => String(c.id || c.field) === selectedId);

  useEffect(() => {
    if (!selectedId || !studyId) return;
    // Only load Decision Center detail for real decision ids
    if (!selectedDecision) {
      setEvidence(null);
      setDependencies(null);
      setBlockers(null);
      setApplicability(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setDetailBusy(true);
      setDetailError(null);
      try {
        const [ev, dep, blk, app] = await Promise.all([
          getDecisionEvidence(studyId, selectedId).catch(() => null),
          getDecisionDependencies(studyId, selectedId).catch(() => null),
          getDecisionBlockers(studyId, selectedId).catch(() => null),
          getDecisionApplicability(studyId, selectedId).catch(() => null),
        ]);
        if (cancelled) return;
        setEvidence(ev);
        setDependencies(dep);
        setBlockers(blk);
        setApplicability(app);
      } catch (err: unknown) {
        if (!cancelled) {
          setDetailError(err instanceof Error ? err.message : "Detail load failed");
        }
      } finally {
        if (!cancelled) setDetailBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId, studyId, selectedDecision]);

  function draftKey(target: NonNullable<FormTarget>) {
    return `${target.kind}:${target.id}:${target.action}`;
  }

  function openForm(target: NonNullable<FormTarget>) {
    if (!canApprove && (target.action === "approve" || target.action === "modify")) {
      onNotice("Недостаточно прав (approve_decisions)");
      return;
    }
    setFormTarget(target);
  }

  async function handleSubmit(values: DecisionFormValues) {
    if (!formTarget) return;
    await runAction(async () => {
      try {
        let out: Record<string, unknown> = {};
        if (formTarget.kind === "conflict") {
          const c = conflicts.find((x) => String(x.id || x.field) === formTarget.id);
          if (!c) return;
          if (formTarget.action === "approve" || formTarget.action === "modify") {
            out = await postExpertDecision(studyId, {
              question: `Resolve ${String(c.field)}`,
              selected_option: values.selectedOption || String(c.value_a),
              rationale: values.rationale,
              evidence_refs: values.evidenceRefs
                ? values.evidenceRefs.split(",").map((s) => s.trim()).filter(Boolean)
                : undefined,
              status: "APPROVED",
            });
            onOutcome(out);
          } else if (formTarget.action === "reject") {
            await requestDecisionEvidence(studyId, {
              question: String(c.field),
              reason: `REJECT: ${values.rationale}`,
            });
            onNotice(`Reject logged for ${String(c.field)} — conflict remains until expert resolve`);
          } else if (formTarget.action === "request-evidence") {
            await requestDecisionEvidence(studyId, {
              question: String(c.field),
              reason: values.evidenceReason || values.rationale,
            });
            onNotice("Evidence requested — no auto-approve");
          }
        } else {
          const did = formTarget.id;
          if (formTarget.action === "approve") {
            out = await approveStudyDecision(studyId, did, {
              reviewer,
              rationale: values.rationale,
              selected_option: values.selectedOption,
            });
            onOutcome({
              message: "Decision approved",
              recalculation_required: true,
              affects: ["Protocol"],
              ...out,
            });
          } else if (formTarget.action === "reject") {
            await rejectStudyDecision(studyId, did, {
              reviewer,
              rationale: values.rationale,
            });
            onNotice("Decision rejected");
          } else if (formTarget.action === "modify") {
            out = await modifyStudyDecision(studyId, did, {
              reviewer,
              selected_option: values.selectedOption || "",
              rationale: values.rationale,
            });
            onOutcome({
              message: "Decision modified",
              recalculation_required: true,
              affects: ["Protocol"],
              ...out,
            });
          } else if (formTarget.action === "request-evidence") {
            await requestDecisionEvidence(studyId, {
              decision_id: did,
              reason: values.evidenceReason || values.rationale,
            });
            onNotice("Evidence requested — no auto-approve");
          }
        }
        const slices = slicesFromAffects(out.affects ?? ["decisions", "Protocol"]);
        setFormTarget(null);
        await onRefresh(slices);
      } catch (err: unknown) {
        onTransportError(err instanceof Error ? err.message : "Decision action failed");
      }
    });
  }

  const formConflict =
    formTarget?.kind === "conflict"
      ? conflicts.find((c) => String(c.id || c.field) === formTarget.id)
      : null;
  const formDecision =
    formTarget?.kind === "decision"
      ? decisions.find((d) => String(d.id || d.decision_id) === formTarget.id)
      : null;

  const formOptions: string[] = [];
  let defaultOption = "";
  if (formConflict) {
    if (formConflict.value_a != null) formOptions.push(String(formConflict.value_a));
    if (formConflict.value_b != null && String(formConflict.value_b) !== String(formConflict.value_a)) {
      formOptions.push(String(formConflict.value_b));
    }
    defaultOption =
      formTarget?.action === "modify"
        ? String(formConflict.value_b || formConflict.value_a || "")
        : String(formConflict.value_a || "");
  } else if (formDecision) {
    const rec = formDecision.recommendation as Record<string, unknown> | undefined;
    const opt = rec?.option != null ? String(rec.option) : "";
    if (opt) formOptions.push(opt);
    const opts = (formDecision.options as unknown[]) || [];
    for (const o of opts) {
      const v = typeof o === "object" && o && "value" in (o as object)
        ? String((o as { value: unknown }).value)
        : String(o);
      if (v && !formOptions.includes(v)) formOptions.push(v);
    }
    defaultOption = opt;
  }

  const decisionBlocked =
    Boolean(blockers?.blocked) ||
    (Array.isArray(blockers?.blocking_reasons) && (blockers!.blocking_reasons as unknown[]).length > 0);

  return (
    <section className="panel">
      <h2>Решения</h2>
      <p className="muted">
        Рекомендация ≠ утверждённое решение. Конфликт дозы (15 vs 30 мг) не разрешается автоматически.
      </p>

      {error && (
        <div className="op-error" role="alert">
          {error}{" "}
          <button type="button" className="linkish" onClick={onDismissError}>
            ✕
          </button>
        </div>
      )}

      {!conflicts.length && !decisions.length ? (
        <EmptyState
          title="Нет решений"
          why="Конфликты и рекомендации появятся после анализа пакета."
          next="Проанализируйте пакет документов."
          actionLabel="Analyze study package"
          onAction={onAnalyze}
        />
      ) : null}

      {conflicts.map((c) => {
        const cid = String(c.id || c.field);
        const open = String(c.status).toUpperCase() === "OPEN";
        return (
          <div
            key={cid}
            className={`decision-card ${selectedId === cid ? "row-selected" : ""}`}
            onClick={() => setSelectedId(cid)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") setSelectedId(cid);
            }}
          >
            <div className="header-actions">
              <span className={`status-pill ${statusClass(String(c.severity))}`}>{humanLabel(c.severity)}</span>
              <span className={`status-pill ${statusClass(String(c.status))}`}>{humanLabel(c.status)}</span>
            </div>
            <h3>QUESTION: Resolve {String(c.field)}?</h3>
            <p>Evidence: {String(c.evidence || c.required_action || "see sources")}</p>
            <p>
              System recommendation:{" "}
              {String(c.recommendation || "Expert decision required — no auto-resolve")}
            </p>
            <p>Status: {humanLabel(c.status)}</p>
            <p className="muted small">
              A: <strong>{String(c.value_a)}</strong> ({String(c.source_a)}) · B:{" "}
              <strong>{String(c.value_b)}</strong> ({String(c.source_b)})
            </p>
            <div className="header-actions" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                disabled={busy || !open || !canApprove}
                onClick={() => openForm({ kind: "conflict", id: cid, action: "approve" })}
              >
                Approve
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => openForm({ kind: "conflict", id: cid, action: "reject" })}
              >
                Reject
              </button>
              <button
                type="button"
                disabled={busy || !canApprove}
                onClick={() => openForm({ kind: "conflict", id: cid, action: "modify" })}
              >
                Modify
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => openForm({ kind: "conflict", id: cid, action: "request-evidence" })}
              >
                Request evidence
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => onNotice(`Source A: ${String(c.source_a)} = ${String(c.value_a)}`)}
              >
                View source A
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => onNotice(`Source B: ${String(c.source_b)} = ${String(c.value_b)}`)}
              >
                View source B
              </button>
            </div>
          </div>
        );
      })}

      {decisions.map((d) => {
        const did = String(d.id || d.decision_id);
        const rec = d.recommendation as Record<string, unknown> | undefined;
        const status = String(d.status || "").toUpperCase();
        const actionable = !["APPROVED", "REJECTED", "KEEP_CURRENT"].includes(status);
        return (
          <div
            key={did}
            className={`decision-card ${selectedId === did ? "row-selected" : ""}`}
            onClick={() => setSelectedId(did)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") setSelectedId(did);
            }}
          >
            <h3>QUESTION: {String(d.question || d.domain || d.id)}</h3>
            <p className="muted">Evidence: см. decision center / sources</p>
            <p>
              System recommendation:{" "}
              {String(rec?.option || rec?.summary || d.recommendation || "—")}
            </p>
            <p>Status: {humanLabel(d.status)}</p>
            <div className="header-actions" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                disabled={busy || !actionable || !canApprove || (decisionBlocked && selectedId === did)}
                onClick={() => openForm({ kind: "decision", id: did, action: "approve" })}
              >
                Approve
              </button>
              <button
                type="button"
                disabled={busy || !actionable}
                onClick={() => openForm({ kind: "decision", id: did, action: "reject" })}
              >
                Reject
              </button>
              <button
                type="button"
                disabled={busy || !actionable || !canApprove}
                onClick={() => openForm({ kind: "decision", id: did, action: "modify" })}
              >
                Modify
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => openForm({ kind: "decision", id: did, action: "request-evidence" })}
              >
                Request evidence
              </button>
            </div>
          </div>
        );
      })}

      {formTarget && (
        <DecisionForm
          action={formTarget.action}
          title={`${formTarget.action} — ${formTarget.id}`}
          options={formOptions}
          defaultOption={defaultOption}
          draft={drafts[draftKey(formTarget)] || null}
          onDraftChange={(v) =>
            setDrafts((prev) => ({ ...prev, [draftKey(formTarget)]: v }))
          }
          busy={busy}
          error={error}
          onCancel={() => setFormTarget(null)}
          onSubmit={handleSubmit}
        />
      )}

      {(selectedDecision || selectedConflict) && (
        <aside className="decision-detail panel">
          <h3>Детали решения</h3>
          {selectedDecision && (
            <>
              <p>
                <strong>Question:</strong> {String(selectedDecision.question || selectedDecision.domain || "—")}
              </p>
              <p>
                <strong>Status:</strong> {humanLabel(selectedDecision.status)}
              </p>
              <p>
                <strong>Recommendation:</strong>{" "}
                {String(
                  (selectedDecision.recommendation as Record<string, unknown> | undefined)?.option ||
                    (selectedDecision.recommendation as Record<string, unknown> | undefined)?.summary ||
                    "—",
                )}
              </p>
              {selectedDecision.current_value != null || selectedDecision.value != null ? (
                <p>
                  <strong>Current value:</strong>{" "}
                  {String(selectedDecision.current_value ?? selectedDecision.value)}
                </p>
              ) : null}
              {Array.isArray(selectedDecision.affected_sections) ? (
                <p>
                  <strong>Affected sections:</strong>{" "}
                  {(selectedDecision.affected_sections as unknown[]).join(", ")}
                </p>
              ) : null}
            </>
          )}
          {selectedConflict && !selectedDecision && (
            <>
              <p>
                <strong>Question:</strong> Resolve {String(selectedConflict.field)}?
              </p>
              <p>
                <strong>Source comparison:</strong> A={String(selectedConflict.value_a)} (
                {String(selectedConflict.source_a)}) vs B={String(selectedConflict.value_b)} (
                {String(selectedConflict.source_b)})
              </p>
              <p>
                <strong>Status:</strong> {humanLabel(selectedConflict.status)}
              </p>
              <p>
                <strong>Recommendation:</strong>{" "}
                {String(selectedConflict.recommendation || "Expert decision required — no auto-resolve")}
              </p>
            </>
          )}

          {detailBusy && <p className="muted">Загрузка evidence / dependencies…</p>}
          {detailError && (
            <div className="op-error" role="alert">
              {detailError}{" "}
              <button type="button" className="linkish" onClick={() => setDetailError(null)}>
                ✕
              </button>
            </div>
          )}

          {evidence && (
            <section>
              <h4>Evidence</h4>
              <pre className="small preview-block">
                {JSON.stringify(evidence.evidence || evidence, null, 2).slice(0, 2500)}
              </pre>
            </section>
          )}
          {dependencies && (
            <section>
              <h4>Dependencies</h4>
              <pre className="small preview-block">{JSON.stringify(dependencies, null, 2).slice(0, 2000)}</pre>
            </section>
          )}
          {blockers && (
            <section>
              <h4>Blockers</h4>
              <p className="muted small">
                blocked={String(Boolean(blockers.blocked))} — действия не auto-resolve
              </p>
              <pre className="small preview-block">{JSON.stringify(blockers, null, 2).slice(0, 2000)}</pre>
            </section>
          )}
          {applicability && (
            <section>
              <h4>Applicability</h4>
              <pre className="small preview-block">{JSON.stringify(applicability, null, 2).slice(0, 2000)}</pre>
            </section>
          )}

          {selectedDecision && (
            <div className="header-actions">
              <button
                type="button"
                disabled={busy || !canApprove || decisionBlocked}
                title={
                  !canApprove
                    ? "Требуется approve_decisions"
                    : decisionBlocked
                      ? "Есть blockers"
                      : undefined
                }
                onClick={() =>
                  openForm({
                    kind: "decision",
                    id: String(selectedDecision.id || selectedDecision.decision_id),
                    action: "approve",
                  })
                }
              >
                Approve
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  openForm({
                    kind: "decision",
                    id: String(selectedDecision.id || selectedDecision.decision_id),
                    action: "reject",
                  })
                }
              >
                Reject
              </button>
              <button
                type="button"
                disabled={busy || !canApprove}
                onClick={() =>
                  openForm({
                    kind: "decision",
                    id: String(selectedDecision.id || selectedDecision.decision_id),
                    action: "modify",
                  })
                }
              >
                Modify
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() =>
                  openForm({
                    kind: "decision",
                    id: String(selectedDecision.id || selectedDecision.decision_id),
                    action: "request-evidence",
                  })
                }
              >
                Request evidence
              </button>
            </div>
          )}
        </aside>
      )}
    </section>
  );
}

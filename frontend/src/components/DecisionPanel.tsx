import { useEffect, useState } from "react";
import {
  approveStudyDecision,
  formatApiError,
  getDecisionApplicability,
  getDecisionBlockers,
  getDecisionDependencies,
  getDecisionEvidence,
  keepCurrentDecisionValue,
  modifyStudyDecision,
  postExpertDecision,
  rejectStudyDecision,
  requestDecisionEvidence,
} from "../api/client";
import {
  DecisionForm,
  normalizeDecisionOption,
  normalizeDecisionOptions,
  type DecisionFormAction,
  type DecisionFormValues,
  type DecisionOptionInput,
} from "./DecisionForm";
import { humanLabel } from "../writerLabels";
import {
  AI_ROLE_COPY,
  domainTitle,
  explainDecisionBlockers,
  optionTitle,
  primaryNextAction,
} from "../workspace/decisionExplain";
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

function decisionHasOpenBlockers(d: Record<string, unknown> | null | undefined): boolean {
  if (!d) return false;
  const status = String(d.status || "").toUpperCase();
  // Terminal expert outcomes are done — don't treat as "blocked path"
  if (["APPROVED", "REJECTED", "KEEP_CURRENT", "ACCEPTED", "RESOLVED"].includes(status)) {
    return false;
  }
  if (status === "BLOCKED") return true;
  const reasons = d.blocking_reasons;
  if (Array.isArray(reasons) && reasons.length > 0) return true;
  const conflicts = d.blocking_conflicts;
  if (Array.isArray(conflicts) && conflicts.length > 0) return true;
  return false;
}

function formatBlockerHint(d: Record<string, unknown>): string {
  const explains = explainDecisionBlockers(d);
  if (!explains.length) {
    return "Утвердить нельзя: открыты dependency blockers. Можно экспертно задать значение через «Изменить».";
  }
  const first = explains[0]!;
  return `Утвердить нельзя: ${first.title}. Либо закройте пробел данных, либо нажмите «Изменить» и зафиксируйте опцию экспертно.`;
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
  aiEnabled?: boolean;
  onAnalyze: () => void;
  onDismissError: () => void;
  onOutcome: (outcome: Record<string, unknown>) => void;
  onNotice: (msg: string) => void;
  onRefresh: (slices: RefreshSlice[]) => Promise<void>;
  onTransportError: (msg: string) => void;
  runAction: (fn: () => Promise<void>) => Promise<void>;
  onGoTab?: (tab: "data" | "evidence" | "documents" | "decisions") => void;
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
    aiEnabled = false,
    onAnalyze,
    onDismissError,
    onOutcome,
    onNotice,
    onRefresh,
    onTransportError,
    runAction,
    onGoTab,
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
    if (!canApprove && (target.action === "approve" || target.action === "modify" || target.action === "keep-current")) {
      onNotice("Недостаточно прав (approve_decisions)");
      return;
    }
    // Approve alone is blocked by dependency gaps (backend 422).
    // Modify / keep-current remain available — expert path for minimal writer flow.
    if (target.kind === "decision" && target.action === "approve") {
      const d = decisions.find((x) => String(x.id || x.decision_id) === target.id);
      if (d && decisionHasOpenBlockers(d)) {
        onTransportError(formatBlockerHint(d));
        return;
      }
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
              message: "Decision modified (expert)",
              recalculation_required: true,
              affects: ["Protocol"],
              ...out,
            });
          } else if (formTarget.action === "keep-current") {
            out = await keepCurrentDecisionValue(studyId, did, {
              reviewer,
              rationale: values.rationale,
            });
            onOutcome({
              message: "Keep current value",
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
        onTransportError(formatApiError(err, "Decision action failed"));
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

  const formOptions: DecisionOptionInput[] = [];
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
    const recOpt = normalizeDecisionOption(
      (rec?.option ?? rec?.code ?? rec?.value) as DecisionOptionInput,
    );
    if (recOpt) formOptions.push(recOpt);
    for (const o of normalizeDecisionOptions((formDecision.options as DecisionOptionInput[]) || [])) {
      if (!formOptions.some((x) => normalizeDecisionOption(x)?.value === o.value)) {
        formOptions.push(o);
      }
    }
    defaultOption = recOpt?.value || "";
  }

  const decisionBlocked =
    Boolean(blockers?.blocked) ||
    (Array.isArray(blockers?.blocking_reasons) && (blockers!.blocking_reasons as unknown[]).length > 0) ||
    decisionHasOpenBlockers(selectedDecision);

  return (
    <section className="panel">
      <h2>Решения</h2>
      <p className="muted">
        С минимальными вводами: конфликт дозы закрываете явно; Washout/Sampling при пробеле t½/Tmax —
        через «Изменить и утвердить» (экспертная фиксация). Обычное «Утвердить» доступно после закрытия
        blockers. Рекомендация системы ≠ утверждение.
      </p>

      <aside className="ai-role-callout" aria-label="Роль ИИ">
        <strong>{AI_ROLE_COPY.title}</strong>
        <p className="muted small">
          Сейчас ИИ: <strong>{aiEnabled ? "включён" : "выключен"}</strong>
          {aiEnabled
            ? " — может предлагать извлечения и формулировки."
            : " — расчёты и правила работают без LLM."}
        </p>
        <ul className="small">
          {AI_ROLE_COPY.bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      </aside>

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
            <h3>Конфликт: {String(c.field)}</h3>
            <dl className="decision-facts">
              <div>
                <dt>Что не сходится</dt>
                <dd>
                  <strong>{String(c.value_a)}</strong> ({String(c.source_a)}) vs{" "}
                  <strong>{String(c.value_b)}</strong> ({String(c.source_b)})
                </dd>
              </div>
              <div>
                <dt>Почему важно</dt>
                <dd>{String(c.evidence || c.required_action || "Нужно экспертное сравнение источников")}</dd>
              </div>
              <div>
                <dt>Что сделать</dt>
                <dd>
                  {open
                    ? "Выберите значение A или B (Утвердить / Изменить). Автоматически не закроется."
                    : "Конфликт уже закрыт или не в статусе OPEN."}
                </dd>
              </div>
            </dl>
            <div className="header-actions" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                disabled={busy || !open || !canApprove}
                onClick={() => openForm({ kind: "conflict", id: cid, action: "approve" })}
              >
                Утвердить
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => openForm({ kind: "conflict", id: cid, action: "reject" })}
              >
                Отклонить
              </button>
              <button
                type="button"
                disabled={busy || !canApprove}
                onClick={() => openForm({ kind: "conflict", id: cid, action: "modify" })}
              >
                Изменить
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => openForm({ kind: "conflict", id: cid, action: "request-evidence" })}
              >
                Запросить evidence
              </button>
            </div>
          </div>
        );
      })}

      {decisions.map((d) => {
        const did = String(d.id || d.decision_id);
        const rec = d.recommendation as Record<string, unknown> | undefined;
        const status = String(d.status || "").toUpperCase();
        const terminal = ["APPROVED", "REJECTED", "KEEP_CURRENT", "ACCEPTED", "RESOLVED"].includes(status);
        const actionable = !terminal;
        const blocked = decisionHasOpenBlockers(d);
        const explains = explainDecisionBlockers(d);
        const recLabel =
          optionTitle(
            normalizeDecisionOption((rec?.option ?? rec?.code) as DecisionOptionInput)?.value ||
              rec?.option ||
              rec?.summary,
          ) || "—";
        const primary = explains[0];
        return (
          <div
            key={did}
            className={`decision-card ${blocked ? "decision-card-blocked" : ""} ${selectedId === did ? "row-selected" : ""}`}
            onClick={() => setSelectedId(did)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") setSelectedId(did);
            }}
          >
            <div className="header-actions">
              <span className={`status-pill ${statusClass(status)}`}>{humanLabel(d.status)}</span>
              <span className="muted small">{domainTitle(d.domain)}</span>
            </div>
            <h3>{domainTitle(d.question || d.domain || d.id)}</h3>
            <dl className="decision-facts">
              <div>
                <dt>Рекомендация системы</dt>
                <dd>
                  <strong>{recLabel}</strong>
                  <span className="muted small"> — ещё не утверждено; ИИ/engine только предлагает</span>
                </dd>
              </div>
              {terminal ? (
                <div>
                  <dt>Итог</dt>
                  <dd>
                    {status === "APPROVED" || status === "KEEP_CURRENT"
                      ? "Эксперт уже зафиксировал решение. Можно идти дальше по writer-пути."
                      : "Решение отклонено. Чтобы продолжить — «Изменить и утвердить»."}
                  </dd>
                </div>
              ) : blocked && primary ? (
                <>
                  <div>
                    <dt>Почему «Утвердить» недоступно</dt>
                    <dd>
                      <strong>{primary.title}</strong>
                      <div className="muted small">{primary.why}</div>
                      {explains.length > 1 ? (
                        <ul className="small blocker-list">
                          {explains.slice(1).map((e) => (
                            <li key={e.code}>{e.title}</li>
                          ))}
                        </ul>
                      ) : null}
                    </dd>
                  </div>
                  <div>
                    <dt>Как пройти шаг с минимальными вводами</dt>
                    <dd>
                      <p>
                        <strong>Быстрый путь:</strong> нажмите «Изменить и утвердить», выберите опцию (
                        {recLabel}) и укажите rationale — backend это разрешает даже без t½/Tmax.
                      </p>
                      <p className="muted small">
                        Полный путь: {primaryNextAction(explains)} — тогда станет доступно обычное «Утвердить».
                      </p>
                      <div className="header-actions" style={{ marginTop: "0.5rem" }}>
                        <button
                          type="button"
                          disabled={busy || !canApprove}
                          onClick={(e) => {
                            e.stopPropagation();
                            openForm({ kind: "decision", id: did, action: "modify" });
                          }}
                        >
                          Изменить и утвердить
                        </button>
                        {primary.nextTab && onGoTab ? (
                          <button
                            type="button"
                            className="secondary"
                            onClick={(e) => {
                              e.stopPropagation();
                              onGoTab(primary.nextTab!);
                            }}
                          >
                            Данные / Evidence
                          </button>
                        ) : null}
                      </div>
                    </dd>
                  </div>
                </>
              ) : (
                <div>
                  <dt>Что сделать</dt>
                  <dd>
                    Проверьте рекомендацию → «Утвердить», либо «Изменить и утвердить» / «Оставить текущее».
                  </dd>
                </div>
              )}
            </dl>
            <div className="header-actions" onClick={(e) => e.stopPropagation()}>
              <button
                type="button"
                disabled={busy || !actionable || !canApprove || blocked}
                title={blocked ? formatBlockerHint(d) : undefined}
                onClick={() => openForm({ kind: "decision", id: did, action: "approve" })}
              >
                Утвердить
              </button>
              <button
                type="button"
                disabled={busy || (!actionable && status !== "REJECTED") || !canApprove}
                title={
                  blocked
                    ? "Экспертная фиксация опции при открытых blockers (разрешено backend modify)"
                    : undefined
                }
                onClick={() => openForm({ kind: "decision", id: did, action: "modify" })}
              >
                Изменить и утвердить
              </button>
              <button
                type="button"
                disabled={busy || !actionable || !canApprove}
                onClick={() => openForm({ kind: "decision", id: did, action: "keep-current" })}
              >
                Оставить текущее
              </button>
              <button
                type="button"
                disabled={busy || !actionable}
                onClick={() => openForm({ kind: "decision", id: did, action: "reject" })}
              >
                Отклонить
              </button>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={() => openForm({ kind: "decision", id: did, action: "request-evidence" })}
              >
                Запросить evidence
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
          warning={
            formTarget.kind === "decision" &&
            formTarget.action === "modify" &&
            formDecision &&
            decisionHasOpenBlockers(formDecision)
              ? "Пробелы данных (t½/Tmax) остаются открытыми. Вы фиксируете опцию как экспертное решение — это допустимый путь Writer при минимальных вводах."
              : null
          }
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
                {normalizeDecisionOption(
                  ((selectedDecision.recommendation as Record<string, unknown> | undefined)?.option ??
                    (selectedDecision.recommendation as Record<string, unknown> | undefined)?.code) as DecisionOptionInput,
                )?.label ||
                  String(
                    (selectedDecision.recommendation as Record<string, unknown> | undefined)?.summary || "—",
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
                disabled={busy || !canApprove || decisionBlocked || decisionHasOpenBlockers(selectedDecision)}
                title={
                  !canApprove
                    ? "Требуется approve_decisions"
                    : decisionBlocked || decisionHasOpenBlockers(selectedDecision)
                      ? formatBlockerHint(selectedDecision)
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

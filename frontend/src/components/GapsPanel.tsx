import { useState } from "react";
import {
  formatApiError,
  researchStudyGap,
  resolveStudyGapManually,
  verifyStudyGap,
  type GapProposal,
  type GapSource,
  type StudyGap,
} from "../api/client";

const STATUS_RU: Record<string, string> = {
  OPEN: "Значения нет",
  PROPOSED: "Найдено ИИ — нужна проверка",
  VERIFIED: "Подтверждено",
};

const STATUS_CLASS: Record<string, string> = {
  OPEN: "status-yellow",
  PROPOSED: "status-yellow",
  VERIFIED: "status-green",
};

function proposalValue(p: GapProposal): string {
  const v = p.value == null || p.value === "" ? "—" : String(p.value);
  return p.unit ? `${v} ${p.unit}` : v;
}

function sourceLabel(p: GapProposal): string {
  if (p.extraction_method === "MANUAL") return "введено экспертом";
  if (p.extraction_method === "AI") return "извлечено ИИ";
  return "извлечено из источника";
}

export type GapsPanelProps = {
  studyId: string;
  gaps: StudyGap[];
  counts: { total: number; open: number; proposed: number; verified: number };
  resolved: Array<Record<string, unknown>>;
  reviewer: string;
  canApprove: boolean;
  busy: boolean;
  activeSubstance?: string;
  dosageForm?: string;
  dose?: string;
  onNotice: (msg: string) => void;
  onRefresh: () => Promise<void>;
  onGoDecisions: () => void;
};

export function GapsPanel(props: GapsPanelProps) {
  const {
    studyId,
    gaps,
    counts,
    resolved,
    reviewer,
    canApprove,
    busy,
    activeSubstance,
    dosageForm,
    dose,
    onNotice,
    onRefresh,
    onGoDecisions,
  } = props;

  const [localBusy, setLocalBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchInfo, setSearchInfo] = useState<
    Record<string, { status: string; message: string; sources: GapSource[] }>
  >({});
  const [manualFor, setManualFor] = useState<string | null>(null);
  const [manual, setManual] = useState<{ value: string; rationale: string; pk: string }>({
    value: "",
    rationale: "",
    pk: "",
  });

  const disabled = busy || localBusy !== null;

  async function run(code: string, fn: () => Promise<void>) {
    setError(null);
    setLocalBusy(code);
    try {
      await fn();
      await onRefresh();
    } catch (err: unknown) {
      setError(formatApiError(err));
    } finally {
      setLocalBusy(null);
    }
  }

  async function search(gap: StudyGap, useDemoSources: boolean) {
    await run(gap.code, async () => {
      const res = await researchStudyGap(studyId, gap.code, {
        active_substance: activeSubstance,
        dosage_form: dosageForm,
        dose,
        ...(useDemoSources ? { use_mock_provider: true } : {}),
      });
      const message = res.message || `Поиск выполнен, найдено предложений: ${res.found}`;
      setSearchInfo((prev) => ({
        ...prev,
        [gap.code]: { status: res.status, message, sources: res.sources || [] },
      }));
      onNotice(`${gap.title}: ${message}`);
    });
  }

  function startManual(gap: StudyGap) {
    setManualFor(gap.code);
    setManual({ value: "", rationale: "", pk: gap.pk_parameter_options[0] || "" });
  }

  if (!gaps.length) {
    return (
      <div>
        <p>
          Все необходимые входные данные есть — пробелов, требующих поиска или экспертного ввода, не
          осталось.
        </p>
        {resolved.length > 0 && (
          <>
            <h3>Закрытые пробелы</h3>
            <ul className="small">
              {resolved.map((r) => (
                <li key={String(r.code)}>
                  {String(r.title)}: <strong>{String(r.value ?? "—")}</strong>{" "}
                  {r.unit ? String(r.unit) : ""}{" "}
                  <span className="muted">
                    ({String(r.extraction_method) === "MANUAL" ? "введено экспертом" : "из источника"})
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="gaps-panel">
      <p>
        Это данные, которых не было в загруженных документах. Пока пробел открыт, платформа не
        подставляет значение и не считает зависимые шаги — но остальная работа над протоколом
        продолжается.
      </p>
      <p className="muted small">
        Открыто: {counts.open} · Предложено ИИ: {counts.proposed} · Подтверждено: {counts.verified}
      </p>
      {error && (
        <div className="op-error" role="alert">
          {error}{" "}
          <button type="button" className="linkish" onClick={() => setError(null)}>
            ✕
          </button>
        </div>
      )}

      {gaps.map((gap) => {
        const canResearch = gap.resolution.includes("RESEARCH");
        const canManual = gap.resolution.includes("MANUAL");
        const expertOnly = gap.resolution.includes("EXPERT_DECISION");
        const thisBusy = localBusy === gap.code;
        const info = searchInfo[gap.code];
        const emptySearch = Boolean(info) && info.status !== "OK" && gap.proposals.length === 0;

        return (
          <article className="gap-card" key={gap.code}>
            <div className="header-actions">
              <span className={`status-pill ${STATUS_CLASS[gap.status] || "status-gray"}`}>
                {STATUS_RU[gap.status] || gap.status}
              </span>
              <span className="muted small">Ждёт: {gap.blocked_by_this}</span>
            </div>
            <h3>{gap.title}</h3>
            <dl className="decision-facts">
              <div>
                <dt>Зачем нужно</dt>
                <dd>
                  {gap.why}
                  {gap.note ? <div className="muted small">{gap.note}</div> : null}
                </dd>
              </div>
              <div>
                <dt>Что не считается без него</dt>
                <dd>
                  {gap.blocked_by_this}
                  <div className="muted small">Остальные шаги протокола не заблокированы.</div>
                </dd>
              </div>
              {gap.sources_hint.length > 0 && (
                <div>
                  <dt>Где искать</dt>
                  <dd className="muted small">{gap.sources_hint.join(" · ")}</dd>
                </div>
              )}
            </dl>

            {gap.proposals.length > 0 && (
              <div className="ai-proposal-box">
                <h4>Найденные значения — предложение, не решение</h4>
                <ul className="small">
                  {gap.proposals.map((p) => (
                    <li key={p.claim_id}>
                      <div>
                        <strong>{proposalValue(p)}</strong>{" "}
                        <span className="muted">
                          {sourceLabel(p)}
                          {p.confidence ? ` · достоверность: ${p.confidence}` : ""}
                          {p.pk_parameter ? ` · ${p.pk_parameter}` : ""}
                        </span>
                      </div>
                      {p.excerpt ? <div className="muted">{String(p.excerpt).slice(0, 300)}</div> : null}
                      {p.verification_status === "VERIFIED" ? (
                        <span className="status-pill status-green">Подтверждено</span>
                      ) : (
                        <button
                          type="button"
                          disabled={disabled || !canApprove}
                          title={canApprove ? undefined : "Требуется право approve_decisions"}
                          onClick={() =>
                            void run(gap.code, async () => {
                              await verifyStudyGap(studyId, gap.code, {
                                claim_id: p.claim_id,
                                reviewer,
                                applicability_reason: `Подтверждено для этого исследования: ${gap.title}`,
                              });
                              onNotice(`${gap.title}: значение подтверждено, зависимые шаги пересчитаны`);
                            })
                          }
                        >
                          Подтвердить
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {info && (
              <p className={info.status === "OK" ? "muted small" : "op-error small"}>{info.message}</p>
            )}
            {info && info.sources.length > 0 && (
              <details className="small">
                <summary>Источники из поиска ({info.sources.length})</summary>
                <ul>
                  {info.sources.map((s) => (
                    <li key={String(s.url)}>
                      <a href={String(s.url)} target="_blank" rel="noreferrer">
                        {s.title || s.url}
                      </a>{" "}
                      <span className="muted">{s.source_type}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}

            <div className="header-actions">
              {canResearch && (
                <button type="button" disabled={disabled} onClick={() => void search(gap, false)}>
                  {thisBusy ? "Ищем…" : "Найти в источниках (ИИ)"}
                </button>
              )}
              {canResearch && emptySearch && (
                <button
                  type="button"
                  className="secondary"
                  disabled={disabled}
                  title="Демонстрационный набор источников — не для реального протокола"
                  onClick={() => void search(gap, true)}
                >
                  Показать демо-набор
                </button>
              )}
              {canManual && (
                <button
                  type="button"
                  className="secondary"
                  disabled={disabled || !canApprove}
                  title={canApprove ? undefined : "Требуется право approve_decisions"}
                  onClick={() => startManual(gap)}
                >
                  Ввести вручную
                </button>
              )}
              {expertOnly && (
                <button type="button" disabled={disabled} onClick={onGoDecisions}>
                  Открыть Решения
                </button>
              )}
            </div>

            {manualFor === gap.code && (
              <form
                className="gap-manual-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  void run(gap.code, async () => {
                    await resolveStudyGapManually(studyId, gap.code, {
                      value: manual.value,
                      rationale: manual.rationale,
                      unit: gap.unit,
                      pk_parameter: gap.requires_pk_parameter ? manual.pk : null,
                      actor: reviewer,
                    });
                    onNotice(`${gap.title}: значение внесено экспертом`);
                    setManualFor(null);
                  });
                }}
              >
                <label>
                  Значение{gap.unit ? `, ${gap.unit}` : ""}
                  <input
                    value={manual.value}
                    onChange={(e) => setManual((p) => ({ ...p, value: e.target.value }))}
                    placeholder={gap.numeric ? "например 9.5" : "например 2–4"}
                    required
                  />
                </label>
                {gap.requires_pk_parameter && (
                  <label>
                    PK-параметр
                    <select
                      value={manual.pk}
                      onChange={(e) => setManual((p) => ({ ...p, pk: e.target.value }))}
                      required
                    >
                      {gap.pk_parameter_options.map((o) => (
                        <option key={o} value={o}>
                          {o}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                <label>
                  Обоснование и источник
                  <textarea
                    value={manual.rationale}
                    onChange={(e) => setManual((p) => ({ ...p, rationale: e.target.value }))}
                    placeholder="Например: SmPC оригинального препарата, раздел 5.2"
                    required
                  />
                </label>
                <div className="header-actions">
                  <button type="submit" disabled={disabled}>
                    Сохранить как подтверждённое
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    disabled={disabled}
                    onClick={() => setManualFor(null)}
                  >
                    Отмена
                  </button>
                </div>
                <p className="muted small">
                  Значение будет записано с обоснованием и автором — в истории останется, кто его внёс.
                </p>
              </form>
            )}
          </article>
        );
      })}
    </div>
  );
}

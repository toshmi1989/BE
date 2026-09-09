import { useState } from "react";
import {
  calculateStudySampleSize,
  formatApiError,
  recomputeStudyStatistics,
} from "../api/client";

const BE_PARAMETER_OPTIONS = ["Cmax", "AUC0-t", "AUC0-72", "AUC0-inf"];

const POPULATION_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "PER_PROTOCOL", label: "Per protocol — субъекты, завершившие оба периода по протоколу" },
  { value: "PK_ANALYSIS_SET", label: "PK analysis set — субъекты с оценимым PK-профилем" },
  { value: "ALL_RANDOMIZED", label: "Все рандомизированные субъекты" },
  { value: "SAFETY_SET", label: "Safety set — субъекты, получившие хотя бы одну дозу" },
];

type Common = {
  studyId: string;
  reviewer: string;
  busy: boolean;
  canApprove: boolean;
  onNotice: (msg: string) => void;
  onRefresh: () => Promise<void>;
};

/** Expert selects PRIMARY BE endpoints and the analysis population. Never auto-chosen. */
export function StatisticsPlanForm(props: Common & { currentParameters?: string[] }) {
  const { studyId, reviewer, busy, canApprove, onNotice, onRefresh, currentParameters } = props;
  const [selected, setSelected] = useState<string[]>(
    (currentParameters || []).filter((p) => BE_PARAMETER_OPTIONS.includes(p)),
  );
  const [population, setPopulation] = useState("");
  const [rationale, setRationale] = useState("");
  const [localBusy, setLocalBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const disabled = busy || localBusy || !canApprove;

  function toggle(param: string) {
    setSelected((prev) =>
      prev.includes(param) ? prev.filter((p) => p !== param) : [...prev, param],
    );
  }

  return (
    <form
      className="engine-form"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        setLocalBusy(true);
        void (async () => {
          try {
            await recomputeStudyStatistics(studyId, {
              primary_be_parameters: selected,
              primary_be_source: "EXPERT_DECISION",
              analysis_population: population,
              analysis_population_source: "EXPERT_DECISION",
              acceptance_wording: rationale || undefined,
              created_by: reviewer,
            });
            onNotice("Статистический план пересчитан по вашему выбору — проверьте и утвердите");
            await onRefresh();
          } catch (err: unknown) {
            setError(formatApiError(err));
          } finally {
            setLocalBusy(false);
          }
        })();
      }}
    >
      <h4>Что должен выбрать эксперт</h4>
      <p className="muted small">
        Платформа не подставляет основной endpoint и популяцию анализа — это врачебное решение. После
        выбора план пересчитывается и становится доступным для утверждения.
      </p>

      <fieldset>
        <legend>Основной endpoint биоэквивалентности (PRIMARY BE)</legend>
        {BE_PARAMETER_OPTIONS.map((p) => (
          <label key={p} className="inline-check">
            <input
              type="checkbox"
              checked={selected.includes(p)}
              onChange={() => toggle(p)}
              disabled={disabled}
            />
            {p}
          </label>
        ))}
      </fieldset>

      <label>
        Популяция анализа
        <select
          value={population}
          onChange={(e) => setPopulation(e.target.value)}
          disabled={disabled}
          required
        >
          <option value="">— выберите —</option>
          {POPULATION_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>

      <label>
        Обоснование выбора
        <textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Например: основной параметр по требованиям регулятора для данной формы"
          disabled={disabled}
        />
      </label>

      {error && (
        <div className="op-error" role="alert">
          {error}
        </div>
      )}

      <div className="header-actions">
        <button type="submit" disabled={disabled || !selected.length || !population}>
          Применить выбор и пересчитать план
        </button>
      </div>
      {!canApprove && <p className="muted small">Нужно право approve_decisions.</p>}
    </form>
  );
}

/** Explicit inputs for the N calculation. Nothing is applied without submitting. */
export function SampleSizeCalcForm(props: Common & { design?: string }) {
  const { studyId, reviewer, busy, canApprove, onNotice, onRefresh, design } = props;
  const [form, setForm] = useState({
    parameter: "Cmax",
    expected_ratio: "0.95",
    power: "0.8",
    alpha: "0.05",
    be_lower: "0.8",
    be_upper: "1.25",
    dropout_percent: "10",
  });
  const [localBusy, setLocalBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const disabled = busy || localBusy || !canApprove;

  function set(key: keyof typeof form, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  return (
    <form
      className="engine-form"
      onSubmit={(e) => {
        e.preventDefault();
        setError(null);
        setLocalBusy(true);
        void (async () => {
          try {
            await calculateStudySampleSize(studyId, {
              design: design || "STANDARD_2X2_CROSSOVER",
              parameters: [form.parameter],
              expected_ratio: Number(form.expected_ratio),
              expected_ratio_source: "EXPERT_INPUT",
              power: Number(form.power),
              power_source: "EXPERT_INPUT",
              alpha: Number(form.alpha),
              alpha_source: "EXPERT_INPUT",
              be_lower: Number(form.be_lower),
              be_upper: Number(form.be_upper),
              be_limits_source: "EXPLICIT_CONFIGURATION",
              dropout_percent: Number(form.dropout_percent),
              dropout_source: "EXPERT_INPUT",
              inflation_method: "DIVIDE_BY_RETAINMENT_RATE",
              created_by: reviewer,
            });
            onNotice("Размер выборки рассчитан — расчёт ещё не утверждён");
            await onRefresh();
          } catch (err: unknown) {
            setError(formatApiError(err));
          } finally {
            setLocalBusy(false);
          }
        })();
      }}
    >
      <h4>Расчёт размера выборки</h4>
      <p className="muted small">
        Все параметры расчёта задаёте вы — платформа не берёт их молча. Значения ниже подставлены как
        обычная практика биоэквивалентных исследований, проверьте их перед расчётом.
      </p>
      <div className="form-grid">
        <label>
          PK-параметр
          <select value={form.parameter} onChange={(e) => set("parameter", e.target.value)} disabled={disabled}>
            {["Cmax", "AUC0-t", "AUC0-inf"].map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </label>
        <label>
          Ожидаемое отношение (GMR)
          <input value={form.expected_ratio} onChange={(e) => set("expected_ratio", e.target.value)} disabled={disabled} />
        </label>
        <label>
          Мощность
          <input value={form.power} onChange={(e) => set("power", e.target.value)} disabled={disabled} />
        </label>
        <label>
          Alpha
          <input value={form.alpha} onChange={(e) => set("alpha", e.target.value)} disabled={disabled} />
        </label>
        <label>
          Нижняя граница BE
          <input value={form.be_lower} onChange={(e) => set("be_lower", e.target.value)} disabled={disabled} />
        </label>
        <label>
          Верхняя граница BE
          <input value={form.be_upper} onChange={(e) => set("be_upper", e.target.value)} disabled={disabled} />
        </label>
        <label>
          Отсев, %
          <input value={form.dropout_percent} onChange={(e) => set("dropout_percent", e.target.value)} disabled={disabled} />
        </label>
      </div>

      {error && (
        <div className="op-error" role="alert">
          {error}
        </div>
      )}

      <div className="header-actions">
        <button type="submit" disabled={disabled}>
          Рассчитать N
        </button>
      </div>
      {!canApprove && <p className="muted small">Нужно право approve_decisions.</p>}
    </form>
  );
}

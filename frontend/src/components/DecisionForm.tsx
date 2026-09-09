import { useEffect, useId, useState, type FormEvent } from "react";

export type DecisionFormAction =
  | "approve"
  | "reject"
  | "modify"
  | "request-evidence"
  | "review";

export type DecisionFormValues = {
  rationale: string;
  selectedOption?: string;
  evidenceReason?: string;
  evidenceRefs?: string;
};

/** Backend may send plain strings or `{ code, label }` / `{ value, label }`. */
export type DecisionOptionInput =
  | string
  | number
  | boolean
  | {
      code?: unknown;
      label?: unknown;
      value?: unknown;
      option?: unknown;
      name?: unknown;
    }
  | null
  | undefined;

export type DecisionOptionChoice = { value: string; label: string };

export function normalizeDecisionOption(raw: DecisionOptionInput): DecisionOptionChoice | null {
  if (raw == null) return null;
  if (typeof raw === "string" || typeof raw === "number" || typeof raw === "boolean") {
    const value = String(raw).trim();
    return value ? { value, label: value } : null;
  }
  if (typeof raw !== "object") return null;
  const code =
    raw.code ?? raw.value ?? raw.option ?? raw.name ?? null;
  const label = raw.label ?? code;
  if (code != null && typeof code === "object") {
    // Nested object — refuse to stringify as [object Object]
    return null;
  }
  if (label != null && typeof label === "object") {
    const value = code != null ? String(code).trim() : "";
    return value ? { value, label: value } : null;
  }
  const value = code != null ? String(code).trim() : label != null ? String(label).trim() : "";
  if (!value) return null;
  return { value, label: label != null ? String(label) : value };
}

export function normalizeDecisionOptions(options: DecisionOptionInput[] | undefined): DecisionOptionChoice[] {
  const out: DecisionOptionChoice[] = [];
  const seen = new Set<string>();
  for (const raw of options || []) {
    const n = normalizeDecisionOption(raw);
    if (!n || seen.has(n.value)) continue;
    seen.add(n.value);
    out.push(n);
  }
  return out;
}

export type DecisionFormProps = {
  action: DecisionFormAction;
  title?: string;
  options?: DecisionOptionInput[];
  defaultOption?: string;
  /** When set, form hydrates from this draft (retained across open/close). */
  draft?: Partial<DecisionFormValues> | null;
  onDraftChange?: (draft: DecisionFormValues) => void;
  busy?: boolean;
  error?: string | null;
  onSubmit: (values: DecisionFormValues) => void | Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
};

const ACTION_LABELS: Record<DecisionFormAction, string> = {
  approve: "Утвердить",
  reject: "Отклонить",
  modify: "Изменить",
  "request-evidence": "Запросить evidence",
  review: "Review",
};

export function validateDecisionForm(
  action: DecisionFormAction,
  values: DecisionFormValues,
): string | null {
  const rationale = (values.rationale || "").trim();
  if (action === "request-evidence") {
    const reason = (values.evidenceReason || values.rationale || "").trim();
    if (!reason) return "Укажите, какое evidence нужно";
    return null;
  }
  if (action === "review") {
    if (!rationale) return "Причина review обязательна";
    return null;
  }
  if (!rationale) return "Обоснование (rationale) обязательно";
  if (action === "approve" || action === "modify") {
    const opt = (values.selectedOption || "").trim();
    if (!opt) return "Выберите или введите значение (option)";
  }
  return null;
}

function emptyValues(action: DecisionFormAction, defaultOption?: string): DecisionFormValues {
  return {
    rationale: "",
    selectedOption: defaultOption || "",
    evidenceReason: action === "request-evidence" ? "" : undefined,
    evidenceRefs: "",
  };
}

export function DecisionForm(props: DecisionFormProps) {
  const {
    action,
    title,
    options = [],
    defaultOption,
    draft,
    onDraftChange,
    busy,
    error,
    onSubmit,
    onCancel,
    submitLabel,
  } = props;
  const formId = useId();
  const [values, setValues] = useState<DecisionFormValues>(() => ({
    ...emptyValues(action, defaultOption),
    ...draft,
  }));
  const [localError, setLocalError] = useState<string | null>(null);

  useEffect(() => {
    setValues({
      ...emptyValues(action, defaultOption),
      ...draft,
    });
    setLocalError(null);
  }, [action, defaultOption, draft]);

  function update(patch: Partial<DecisionFormValues>) {
    setValues((prev) => {
      const next = { ...prev, ...patch };
      onDraftChange?.(next);
      return next;
    });
    setLocalError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const err = validateDecisionForm(action, values);
    if (err) {
      setLocalError(err);
      return;
    }
    setLocalError(null);
    await onSubmit({
      rationale: values.rationale.trim(),
      selectedOption: values.selectedOption?.trim(),
      evidenceReason: (values.evidenceReason || values.rationale).trim(),
      evidenceRefs: values.evidenceRefs?.trim(),
    });
  }

  const showOption = action === "approve" || action === "modify";
  const showEvidenceReason = action === "request-evidence";
  const displayError = localError || error || null;
  const optionChoices = normalizeDecisionOptions(options);

  return (
    <form className="decision-form inline-edit" onSubmit={(e) => void handleSubmit(e)} noValidate>
      <h3>{title || ACTION_LABELS[action]}</h3>
      {showOption && (
        <fieldset className="form-grid">
          <legend className="muted small">Выбранное значение</legend>
          {optionChoices.length > 0 ? (
            <div role="radiogroup" aria-labelledby={`${formId}-opt-label`}>
              <span id={`${formId}-opt-label`} className="muted small">
                Option
              </span>
              {optionChoices.map((opt) => (
                <label key={opt.value} className="radio-row">
                  <input
                    type="radio"
                    name={`${formId}-option`}
                    value={opt.value}
                    checked={values.selectedOption === opt.value}
                    disabled={busy}
                    onChange={() => update({ selectedOption: opt.value })}
                  />
                  {opt.label === opt.value ? opt.label : `${opt.label} (${opt.value})`}
                </label>
              ))}
            </div>
          ) : null}
          <label>
            {optionChoices.length ? "Или введите другое значение" : "Selected option"}
            <input
              value={values.selectedOption || ""}
              disabled={busy}
              onChange={(e) => update({ selectedOption: e.target.value })}
              aria-required="true"
            />
          </label>
        </fieldset>
      )}

      {showEvidenceReason ? (
        <label>
          Что нужно уточнить (обязательно)
          <textarea
            value={values.evidenceReason || ""}
            disabled={busy}
            rows={3}
            onChange={(e) => update({ evidenceReason: e.target.value, rationale: e.target.value })}
            aria-required="true"
          />
        </label>
      ) : (
        <label>
          {action === "review" ? "Причина review (обязательно)" : "Rationale (обязательно)"}
          <textarea
            value={values.rationale}
            disabled={busy}
            rows={3}
            onChange={(e) => update({ rationale: e.target.value })}
            aria-required="true"
          />
        </label>
      )}

      {(action === "approve" || action === "modify" || action === "request-evidence") && (
        <label>
          Evidence references (опционально)
          <input
            value={values.evidenceRefs || ""}
            disabled={busy}
            placeholder="ids / URLs через запятую"
            onChange={(e) => update({ evidenceRefs: e.target.value })}
          />
        </label>
      )}

      {displayError && (
        <div className="op-error" role="alert">
          {displayError}
          <button
            type="button"
            className="linkish"
            onClick={() => setLocalError(null)}
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}

      <div className="header-actions">
        <button type="submit" disabled={busy}>
          {busy ? "…" : submitLabel || ACTION_LABELS[action]}
        </button>
        <button type="button" className="secondary" disabled={busy} onClick={onCancel}>
          Отмена
        </button>
      </div>
    </form>
  );
}

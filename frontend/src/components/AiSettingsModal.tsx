import { useEffect, useState } from "react";
import {
  clearStoredAiApiKey,
  getAiSettings,
  getStoredAiApiKey,
  setStoredAiApiKey,
  updateAiSettings,
  type AiSettingsView,
} from "../api/client";

type Props = {
  open: boolean;
  onClose: () => void;
  onSaved?: (view: AiSettingsView) => void;
};

export function AiSettingsModal({ open, onClose, onSaved }: Props) {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [masked, setMasked] = useState<string | null>(null);
  const [statusDetail, setStatusDetail] = useState<string | null>(null);
  const [available, setAvailable] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotice(null);
    (async () => {
      try {
        const view = await getAiSettings();
        if (cancelled) return;
        setEnabled(Boolean(view.enabled));
        setMasked(view.api_key_masked);
        setAvailable(Boolean(view.status?.available));
        setStatusDetail(view.status?.detail ?? null);
        const local = getStoredAiApiKey();
        if (local) setApiKey(local);
        else setApiKey("");
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  async function save() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const key = apiKey.trim();
      if (key) setStoredAiApiKey(key);
      const view = await updateAiSettings({
        enabled,
        provider: "openai",
        model: "gpt-4o-mini",
        base_url: "https://api.openai.com/v1",
        api_key: key || undefined,
      });
      setMasked(view.api_key_masked);
      setAvailable(Boolean(view.status?.available));
      setStatusDetail(view.status?.detail ?? null);
      setNotice(
        enabled
          ? view.api_key_configured
            ? "ИИ включён (gpt-4o-mini). Ключ сохранён в памяти сервера до перезапуска."
            : "ИИ включён, но ключ не задан — extraction недоступен."
          : "ИИ выключен.",
      );
      onSaved?.(view);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function clearKey() {
    setSaving(true);
    setError(null);
    try {
      clearStoredAiApiKey();
      setApiKey("");
      const view = await updateAiSettings({ clear_api_key: true, enabled });
      setMasked(view.api_key_masked);
      setAvailable(Boolean(view.status?.available));
      setStatusDetail(view.status?.detail ?? null);
      setNotice("API key удалён из runtime.");
      onSaved?.(view);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="ai-settings-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="header-actions" style={{ justifyContent: "space-between" }}>
          <h2 id="ai-settings-title">Настройки ИИ</h2>
          <button type="button" className="secondary" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </div>

        <p className="muted small">
          Облачный провайдер: <strong>OpenAI gpt-4o-mini</strong>. ИИ только помогает извлекать факты и
          формулировать рекомендации — не утверждает решения и не финализирует протокол.
        </p>

        {loading ? <p className="muted">Загрузка…</p> : null}

        <label className="ai-toggle-row">
          <input
            type="checkbox"
            checked={enabled}
            disabled={loading || saving}
            onChange={(e) => setEnabled(e.target.checked)}
          />
          <span>Включить ИИ</span>
        </label>

        <label>
          OpenAI API key
          <input
            type="password"
            autoComplete="off"
            placeholder={masked ? `Текущий: ${masked}` : "sk-…"}
            value={apiKey}
            disabled={loading || saving}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </label>
        <p className="muted small">
          Ключ уходит на backend и хранится в памяти процесса (не в git). Также копируется в sessionStorage
          браузера для удобства. Не используйте production-секреты в публичных демо.
        </p>

        <p className="muted small">
          Статус: {enabled ? (available ? "доступен" : "недоступен") : "выключен"}
          {statusDetail ? ` — ${statusDetail}` : ""}
          {masked ? ` · ключ ${masked}` : ""}
        </p>

        {error ? (
          <div className="op-error" role="alert">
            {error}
          </div>
        ) : null}
        {notice ? <p className="notice-banner">{notice}</p> : null}

        <div className="header-actions">
          <button type="button" disabled={loading || saving} onClick={() => void save()}>
            {saving ? "…" : "Сохранить"}
          </button>
          <button type="button" className="secondary" disabled={loading || saving} onClick={() => void clearKey()}>
            Удалить ключ
          </button>
          <button type="button" className="secondary" disabled={saving} onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}

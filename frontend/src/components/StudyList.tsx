import { useCallback, useEffect, useState } from "react";
import { listStudies, type StudyListItem } from "../api/client";

type StudyListProps = {
  onOpen: (studyKey: string) => void;
  onCreateNew: () => void;
};

export function StudyList({ onOpen, onCreateNew }: StudyListProps) {
  const [items, setItems] = useState<StudyListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(20);
  const [q, setQ] = useState("");
  const [qApplied, setQApplied] = useState("");
  const [lifecycle, setLifecycle] = useState("");
  const [readiness, setReadiness] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listStudies({
        q: qApplied || undefined,
        lifecycle: lifecycle || undefined,
        readiness: readiness || undefined,
        offset,
        limit,
        sort: "-updated_at",
      });
      setItems(res.studies);
      setTotal(res.total);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить список исследований");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [qApplied, lifecycle, readiness, offset, limit]);

  useEffect(() => {
    void load();
  }, [load]);

  const page = Math.floor(offset / limit) + 1;
  const pages = Math.max(1, Math.ceil(total / limit));

  return (
    <section className="panel study-catalog">
      <div className="header-actions" style={{ justifyContent: "space-between" }}>
        <div>
          <h2>Мои исследования</h2>
          <p className="muted">Каталог WorkspaceStudy · GET /api/studies</p>
        </div>
        <button type="button" className="btn-primary-nav" onClick={onCreateNew}>
          + New Study
        </button>
      </div>

      <div className="form-grid study-catalog-filters">
        <label>
          Поиск
          <input
            value={q}
            placeholder="title / sponsor / product / key"
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setOffset(0);
                setQApplied(q.trim());
              }
            }}
          />
        </label>
        <label>
          Lifecycle
          <select
            value={lifecycle}
            onChange={(e) => {
              setOffset(0);
              setLifecycle(e.target.value);
            }}
          >
            <option value="">Все</option>
            <option value="DRAFT">DRAFT</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="ARCHIVED">ARCHIVED</option>
          </select>
        </label>
        <label>
          Readiness
          <select
            value={readiness}
            onChange={(e) => {
              setOffset(0);
              setReadiness(e.target.value);
            }}
          >
            <option value="">Все</option>
            <option value="NOT_READY">NOT_READY</option>
            <option value="IN_PROGRESS">IN_PROGRESS</option>
            <option value="READY">READY</option>
            <option value="BLOCKED">BLOCKED</option>
          </select>
        </label>
        <div className="header-actions">
          <button
            type="button"
            onClick={() => {
              setOffset(0);
              setQApplied(q.trim());
            }}
          >
            Найти
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              setQ("");
              setQApplied("");
              setLifecycle("");
              setReadiness("");
              setOffset(0);
            }}
          >
            Сброс
          </button>
        </div>
      </div>

      {error && (
        <div className="op-error" role="alert">
          {error}{" "}
          <button type="button" className="linkish" onClick={() => void load()}>
            Повторить
          </button>
          <button type="button" className="linkish" onClick={() => setError(null)}>
            ✕
          </button>
        </div>
      )}

      {loading ? (
        <p className="muted">Загрузка…</p>
      ) : !items.length ? (
        <div className="empty-state">
          <h3>Нет исследований</h3>
          <p>В организации пока нет WorkspaceStudy.</p>
          <p className="muted">Что сделать дальше: создайте исследование через + New Study.</p>
          <button type="button" onClick={onCreateNew}>
            + New Study
          </button>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Title / key</th>
              <th>Sponsor</th>
              <th>Product</th>
              <th>Lifecycle</th>
              <th>Readiness</th>
              <th>Docs</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.study_key}>
                <td>
                  <strong>{s.title || s.study_key}</strong>
                  <div className="muted small">{s.study_key}</div>
                </td>
                <td>{s.sponsor || "—"}</td>
                <td>
                  {s.product || "—"}
                  {s.dose ? ` · ${s.dose}` : ""}
                </td>
                <td>
                  <span className="status-pill status-gray">{s.lifecycle}</span>
                </td>
                <td>
                  <span className={`status-pill status-gray`}>
                    {s.readiness_label || s.readiness || "—"}
                  </span>
                </td>
                <td>{s.document_count}</td>
                <td>
                  <button type="button" className="linkish" onClick={() => onOpen(s.study_key)}>
                    Открыть
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {total > limit && (
        <div className="header-actions">
          <button
            type="button"
            className="secondary"
            disabled={offset <= 0 || loading}
            onClick={() => setOffset(Math.max(0, offset - limit))}
          >
            ← Назад
          </button>
          <span className="muted small">
            {page} / {pages} · всего {total}
          </span>
          <button
            type="button"
            className="secondary"
            disabled={offset + limit >= total || loading}
            onClick={() => setOffset(offset + limit)}
          >
            Далее →
          </button>
        </div>
      )}
    </section>
  );
}

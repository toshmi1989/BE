import { useMemo, useState } from "react";
import {
  getStudyWorkspace,
  getStudyConflicts,
  getStudyPreflight,
  getStudyReadiness,
  getStudyAudit,
  runStudyWorkflow,
  recomputeDecisionCenterGolden,
  bootstrapResearchCenterGolden,
  getSampleSizePanel,
  recomputeStatisticsGolden,
  getWriterReview,
  getBetaCases,
} from "../api/client";
import { Dashboard } from "./Dashboard";

type NavId =
  | "overview"
  | "documents"
  | "data"
  | "decisions"
  | "evidence"
  | "sample-size"
  | "statistics"
  | "protocol"
  | "preflight"
  | "history"
  | "review"
  | "beta"
  | "legacy";

const NAV: Array<{ id: NavId; label: string }> = [
  { id: "overview", label: "Обзор" },
  { id: "documents", label: "Документы" },
  { id: "data", label: "Данные исследования" },
  { id: "review", label: "Writer Review" },
  { id: "decisions", label: "Решения" },
  { id: "evidence", label: "Исследования / Evidence" },
  { id: "sample-size", label: "Sample Size" },
  { id: "statistics", label: "Statistics" },
  { id: "protocol", label: "Протокол" },
  { id: "preflight", label: "Проверка" },
  { id: "history", label: "История" },
  { id: "beta", label: "Beta cases" },
  { id: "legacy", label: "Legacy console" },
];

function statusClass(code: string | undefined): string {
  if (!code) return "status-gray";
  if (code === "READY" || code === "APPROVED" || code === "ACCEPTED") return "status-green";
  if (code === "BLOCKED" || code === "CRITICAL") return "status-red";
  if (code.includes("WARN") || code.includes("REVIEW") || code.includes("PENDING")) return "status-yellow";
  return "status-gray";
}

export function StudyWorkspace() {
  const [tab, setTab] = useState<NavId>("overview");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<Record<string, unknown> | null>(null);
  const [conflicts, setConflicts] = useState<Array<Record<string, unknown>>>([]);
  const [preflight, setPreflight] = useState<Record<string, unknown> | null>(null);
  const [audit, setAudit] = useState<Array<Record<string, unknown>>>([]);
  const [workflowNote, setWorkflowNote] = useState<string | null>(null);
  const [review, setReview] = useState<Record<string, unknown> | null>(null);
  const [selectedField, setSelectedField] = useState<string | null>(null);
  const [betaCases, setBetaCases] = useState<Array<Record<string, unknown>>>([]);

  const studyId = useMemo(() => {
    const h = (workspace?.header || {}) as Record<string, unknown>;
    return String(h.study_id || "UPDCB-02-BE-2026");
  }, [workspace]);

  async function refreshAll(sid = studyId) {
    const [ws, conf, ready, pf, aud] = await Promise.all([
      getStudyWorkspace(sid),
      getStudyConflicts(sid),
      getStudyReadiness(sid),
      getStudyPreflight(sid),
      getStudyAudit(sid),
    ]);
    setWorkspace({ ...ws, readiness_detail: ready });
    setConflicts((conf.conflicts as Array<Record<string, unknown>>) || []);
    setPreflight(pf);
    setAudit((aud.timeline as Array<Record<string, unknown>>) || []);
  }

  async function runGoldenWorkflow() {
    setBusy(true);
    setError(null);
    try {
      const out = await runStudyWorkflow("UPDCB-02-BE-2026", {
        use_golden_fixture: true,
        created_by: "ui-medical-writer",
      });
      // Warm related centers (assistive; no auto-approve)
      try {
        await recomputeDecisionCenterGolden();
      } catch {
        /* optional */
      }
      try {
        await bootstrapResearchCenterGolden();
      } catch {
        /* optional */
      }
      try {
        await getSampleSizePanel("UPDCB-02-BE-2026");
      } catch {
        /* optional */
      }
      try {
        await recomputeStatisticsGolden();
      } catch {
        /* optional */
      }
      setWorkflowNote(
        out.study_mutated === true
          ? "ERROR: Study mutated"
          : `Workflow ${String(out.workflow_id)} complete · readiness ${String((out.readiness as Record<string, unknown>)?.readiness_label || "")} · FINAL blocked until expert approvals`,
      );
      await refreshAll("UPDCB-02-BE-2026");
      setTab("overview");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Workflow failed");
    } finally {
      setBusy(false);
    }
  }

  if (tab === "legacy") {
    return (
      <div className="workspace">
        <aside className="workspace-sidebar">
          <div className="workspace-brand">BE Study Workspace</div>
          <nav>
            {NAV.map((n) => (
              <button
                key={n.id}
                type="button"
                className={tab === n.id ? "nav-item active" : "nav-item"}
                onClick={() => setTab(n.id)}
              >
                {n.label}
              </button>
            ))}
          </nav>
        </aside>
        <div className="workspace-main">
          <Dashboard />
        </div>
      </div>
    );
  }

  const header = (workspace?.header || {}) as Record<string, unknown>;
  const cards = (workspace?.summary_cards || {}) as Record<string, unknown>;
  const facts = (workspace?.canonical_facts || []) as Array<Record<string, unknown>>;
  const readiness = (workspace?.readiness || workspace?.readiness_detail || {}) as Record<
    string,
    unknown
  >;

  return (
    <div className="workspace">
      <aside className="workspace-sidebar">
        <div className="workspace-brand">BE Study Workspace</div>
        <p className="muted small">Recommendation ≠ approval · AI assistive only</p>
        <nav>
          {NAV.map((n) => (
            <button
              key={n.id}
              type="button"
              className={tab === n.id ? "nav-item active" : "nav-item"}
              onClick={() => setTab(n.id)}
            >
              {n.label}
            </button>
          ))}
        </nav>
      </aside>

      <div className="workspace-main">
        <header className="study-header">
          <div>
            <h1>Study {String(header.study_id || "—")}</h1>
            <p className="muted">
              Sponsor: {String(header.sponsor || "—")} · Product: {String(header.product || "—")} ·
              Dose: {String(header.dose || "—")}
            </p>
          </div>
          <div className="header-actions">
            <span className={`status-pill ${statusClass(String(header.readiness_code || ""))}`}>
              {String(header.overall_readiness || "Not loaded")}
            </span>
            <button type="button" disabled={busy} onClick={runGoldenWorkflow}>
              Run UPDCB workflow
            </button>
            <button type="button" disabled={busy || !workspace} onClick={() => refreshAll()}>
              Refresh
            </button>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}
        {workflowNote && <p className="muted">{workflowNote}</p>}

        {tab === "overview" && (
          <section className="panel">
            <h2>Обзор</h2>
            <div className="card-grid">
              {(
                [
                  ["Documents", cards.documents],
                  ["Critical conflicts", cards.critical_conflicts],
                  ["Knowledge gaps", cards.knowledge_gaps],
                  ["Pending decisions", cards.pending_decisions],
                  ["Sample size", cards.sample_size_status],
                  ["Statistics", cards.statistics_status],
                  ["Protocol", cards.protocol_status],
                ] as Array<[string, unknown]>
              ).map(([label, value]) => (
                <div key={label} className="summary-card">
                  <div className="muted">{label}</div>
                  <strong>{value == null ? "—" : String(value)}</strong>
                </div>
              ))}
            </div>
            <p>
              Lifecycle: <strong>{String(readiness.lifecycle || "—")}</strong> · FINAL allowed:{" "}
              {String(readiness.can_finalize ?? false)}
            </p>
          </section>
        )}

        {tab === "documents" && (
          <section className="panel">
            <h2>Документы</h2>
            <p className="muted">
              Upload / ingest / classify / extract via Study Input Package (PROPOSED ≠ VERIFIED). Use
              Legacy console for full upload forms.
            </p>
            <p>Documents in package: {String(cards.documents ?? 0)}</p>
          </section>
        )}

        {tab === "data" && (
          <section className="panel">
            <h2>Данные исследования (Canonical)</h2>
            <p className="muted">CURRENT_STUDY_FACT — not regulatory requirement</p>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Value</th>
                  <th>Status</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {facts.slice(0, 40).map((f) => (
                  <tr key={String(f.field)}>
                    <td>{String(f.field)}</td>
                    <td>{String(f.canonical_value)}</td>
                    <td>{String(f.status)}</td>
                    <td>{String(f.source)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {tab === "decisions" && (
          <section className="panel">
            <h2>Conflict Center / Decisions</h2>
            <p className="muted">
              System recommendation ≠ Expert approved decision. Dose 15 vs 30 mg is never auto-resolved.
            </p>
            <ul>
              {conflicts.map((c) => (
                <li key={String(c.id)}>
                  <span className={`status-pill ${statusClass(String(c.severity))}`}>
                    {String(c.severity)}
                  </span>{" "}
                  <strong>{String(c.field)}</strong>: {String(c.value_a)} ({String(c.source_a)}) vs{" "}
                  {String(c.value_b)} ({String(c.source_b)}) · {String(c.status)} ·{" "}
                  {String(c.required_action)}
                </li>
              ))}
            </ul>
            {!conflicts.length && <p className="muted">Run workflow to load conflicts.</p>}
          </section>
        )}

        {tab === "evidence" && (
          <section className="panel">
            <h2>Research / Evidence</h2>
            <p className="muted">
              Research Center remains available in Legacy console. Claims stay PROPOSED until expert
              verification. AI-off / Mock modes supported.
            </p>
          </section>
        )}

        {tab === "sample-size" && (
          <section className="panel">
            <h2>Sample Size</h2>
            <p>
              Status: <strong>{String(cards.sample_size_status || "—")}</strong>
            </p>
            <p className="muted">
              Recommendation ≠ Approved Sample Size. Deterministic engine only — no LLM arithmetic.
            </p>
          </section>
        )}

        {tab === "statistics" && (
          <section className="panel">
            <h2>Statistics</h2>
            <p>
              Status: <strong>{String(cards.statistics_status || "—")}</strong>
            </p>
            <p className="muted">
              PRIMARY_BE requires expert selection (AUC0-72 vs AUC0-inf scenarios). Recommendation ≠
              approval.
            </p>
          </section>
        )}

        {tab === "protocol" && (
          <section className="panel">
            <h2>Протокол</h2>
            <p>
              Protocol status: <strong>{String(cards.protocol_status || "—")}</strong>
            </p>
            <p className="muted">
              Draft versions are immutable. DOCX generation requires preflight without CRITICAL
              blockers. Use Legacy console for full preview/DOCX.
            </p>
          </section>
        )}

        {tab === "preflight" && (
          <section className="panel">
            <h2>Проверка (Preflight)</h2>
            <p>
              {String(preflight?.message || "Run workflow first")} · can FINALIZE:{" "}
              {String(preflight?.can_finalize ?? false)} · can DOCX:{" "}
              {String(preflight?.can_generate_docx ?? false)}
            </p>
            <ul>
              {((preflight?.checks as Array<Record<string, unknown>>) || []).map((c) => (
                <li key={String(c.code)}>
                  <span className={`status-pill ${statusClass(String(c.severity))}`}>
                    {String(c.severity)}
                  </span>{" "}
                  {c.ok ? "✓" : "✗"} {String(c.message)}
                </li>
              ))}
            </ul>
          </section>
        )}

        {tab === "history" && (
          <section className="panel">
            <h2>История (Audit)</h2>
            <ul>
              {audit.map((e) => (
                <li key={String(e.id)}>
                  {String(e.timestamp)} · {String(e.who)} · {String(e.event)} · {String(e.what)}
                </li>
              ))}
            </ul>
            {!audit.length && <p className="muted">No audit events yet.</p>}
          </section>
        )}

        {tab === "review" && (
          <section className="panel writer-review">
            <h2>Writer Review Mode</h2>
            <p className="muted">
              Canonical → Source → Evidence → Decision → Protocol sections. Missing shows as Not
              available / Needs source / Needs expert decision / Needs research — never silent N/A.
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const r = await getWriterReview(studyId, selectedField || undefined);
                  setReview(r);
                } catch (err: unknown) {
                  setError(err instanceof Error ? err.message : "Review load failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Load review bundle
            </button>
            <div className="review-grid">
              <div>
                <h3>Canonical</h3>
                <ul>
                  {(((review?.canonical_facts as Array<Record<string, unknown>>) || facts) as Array<
                    Record<string, unknown>
                  >)
                    .slice(0, 30)
                    .map((f) => (
                      <li key={String(f.field)}>
                        <button type="button" className="linkish" onClick={() => setSelectedField(String(f.field))}>
                          {String(f.field)}
                        </button>
                        : {f.canonical_value == null ? "Not available" : String(f.canonical_value)}
                      </li>
                    ))}
                </ul>
              </div>
              <div>
                <h3>Selected field</h3>
                {selectedField ? (
                  <pre className="small">
                    {JSON.stringify(
                      ((review?.canonical_facts as Array<Record<string, unknown>>) || []).find(
                        (f) => f.field === selectedField,
                      ) || { field: selectedField, status: "Needs source" },
                      null,
                      2,
                    )}
                  </pre>
                ) : (
                  <p className="muted">Select a field</p>
                )}
                <p className="muted">
                  Sections affected:{" "}
                  {JSON.stringify(review?.protocol_sections_affected || [])}
                </p>
              </div>
              <div>
                <h3>Evidence / Conflicts</h3>
                <ul>
                  {(((review?.conflicts as Array<Record<string, unknown>>) || conflicts) || []).map(
                    (c) => (
                      <li key={String(c.id || c.field)}>
                        {String(c.field)} · {String(c.status)}
                      </li>
                    ),
                  )}
                </ul>
              </div>
            </div>
          </section>
        )}

        {tab === "beta" && (
          <section className="panel">
            <h2>Beta cases</h2>
            <p className="muted">
              Real UPDCB + synthetic categories A–L. Golden protocol is reference only, not SoT.
            </p>
            <button
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const r = await getBetaCases();
                  setBetaCases((r.cases as Array<Record<string, unknown>>) || []);
                } catch (err: unknown) {
                  setError(err instanceof Error ? err.message : "Beta cases failed");
                } finally {
                  setBusy(false);
                }
              }}
            >
              Load registry
            </button>
            <ul>
              {betaCases.map((c) => (
                <li key={String(c.case_id)}>
                  <strong>{String(c.case_id)}</strong> [{String(c.origin)}] {String(c.description)}
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

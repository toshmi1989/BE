import { useCallback, useEffect, useState } from "react";

import { resolveApiBase } from "../api/client";

const API_BASE = resolveApiBase();

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<T>;
}

type IntakeDash = {
  display: string;
  full: number;
  partial: number;
  empty: number;
  slots: { slot: string; case_id: string | null; status: string }[];
};

type SessionDash = {
  writers: number;
  sessions: number;
  paired: number;
  completed: number;
  pending: { session_id: string; case_id: string; type: string }[];
};

type Status = {
  beta_label: string;
  reasons: string[];
  real_full_packages: number;
  real_partial_packages: number;
  writers: number;
  paired_sessions_complete: number;
  postgres_ops: string;
  production_gate: string;
  open_P1: string[];
};

export function ControlledBetaDashboard() {
  const [status, setStatus] = useState<Status | null>(null);
  const [intake, setIntake] = useState<IntakeDash | null>(null);
  const [sessions, setSessions] = useState<SessionDash | null>(null);
  const [caseId, setCaseId] = useState("REAL-UPDCB-02-BE-2026");
  const [writerId, setWriterId] = useState("W-BETA-01");
  const [pairId, setPairId] = useState("");
  const [activeSession, setActiveSession] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  const refresh = useCallback(async () => {
    const [s, i, w] = await Promise.all([
      api<Status>("/api/field-study/status"),
      api<IntakeDash>("/api/field-study/dashboard/intake"),
      api<SessionDash>("/api/field-study/dashboard/sessions"),
    ]);
    setStatus(s);
    setIntake(i);
    setSessions(w);
  }, []);

  useEffect(() => {
    refresh().catch((e) => setErr(String(e)));
  }, [refresh]);

  async function startManual() {
    setErr("");
    try {
      const out = await api<{ pair_id: string; session: { session_id: string } }>(
        "/api/field-study/sessions/timed/start",
        {
          method: "POST",
          body: JSON.stringify({
            case_id: caseId,
            writer_id: writerId,
            session_type: "MANUAL",
          }),
        },
      );
      setPairId(out.pair_id);
      setActiveSession(out.session.session_id);
      setMsg(`Manual started ${out.session.session_id}`);
      await refresh();
    } catch (e) {
      setErr(String(e));
    }
  }

  async function startAssisted() {
    setErr("");
    try {
      const out = await api<{ pair_id: string; session: { session_id: string } }>(
        "/api/field-study/sessions/timed/start",
        {
          method: "POST",
          body: JSON.stringify({
            case_id: caseId,
            writer_id: writerId,
            session_type: "SYSTEM_ASSISTED",
            pair_id: pairId,
          }),
        },
      );
      setActiveSession(out.session.session_id);
      setMsg(`Assisted started ${out.session.session_id}`);
      await refresh();
    } catch (e) {
      setErr(String(e));
    }
  }

  async function stopSession() {
    setErr("");
    try {
      await api(`/api/field-study/sessions/${activeSession}/timed/stop`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setMsg(`Stopped ${activeSession}`);
      setActiveSession("");
      await refresh();
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <div className="beta-ops">
      <h2>Controlled Beta Ops</h2>
      {status && (
        <section className="beta-panel">
          <h3>{status.beta_label}</h3>
          <p>Gate: {status.production_gate}</p>
          <ul>
            {(status.reasons || []).map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p>
            Packages {status.real_full_packages} full / {status.real_partial_packages} partial · Writers{" "}
            {status.writers} · Paired complete {status.paired_sessions_complete} · Postgres{" "}
            {status.postgres_ops}
          </p>
          <p>Open P1: {(status.open_P1 || []).join(", ") || "none"}</p>
        </section>
      )}

      {intake && (
        <section className="beta-panel">
          <h3>REAL PACKAGE INTAKE</h3>
          <p>
            <strong>{intake.display}</strong>
          </p>
          <p>
            {intake.full} FULL · {intake.partial} PARTIAL · {intake.empty} EMPTY
          </p>
          <div className="beta-slots">
            {intake.slots.map((s) => (
              <div key={s.slot} className="beta-slot">
                <span>{s.slot}</span>
                <span>{s.status}</span>
                <span>{s.case_id || "—"}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {sessions && (
        <section className="beta-panel">
          <h3>Writer sessions</h3>
          <p>
            Writers: {sessions.writers} · Sessions: {sessions.sessions} · Paired: {sessions.paired} ·
            Completed: {sessions.completed}
          </p>
          <p>Pending: {sessions.pending.length ? sessions.pending.map((p) => p.session_id).join(", ") : "—"}</p>
        </section>
      )}

      <section className="beta-panel">
        <h3>Session launcher</h3>
        <label>
          Case{" "}
          <input value={caseId} onChange={(e) => setCaseId(e.target.value)} />
        </label>
        <label>
          Writer (pseudonym){" "}
          <input value={writerId} onChange={(e) => setWriterId(e.target.value)} />
        </label>
        <label>
          Pair id{" "}
          <input value={pairId} onChange={(e) => setPairId(e.target.value)} placeholder="from manual" />
        </label>
        <div className="beta-actions">
          <button type="button" onClick={startManual}>
            Start MANUAL baseline
          </button>
          <button type="button" onClick={startAssisted} disabled={!pairId}>
            Start SYSTEM ASSISTED
          </button>
          <button type="button" onClick={stopSession} disabled={!activeSession}>
            Stop active timer
          </button>
          <button type="button" onClick={() => refresh()}>
            Refresh
          </button>
        </div>
        {msg && <p className="beta-ok">{msg}</p>}
        {err && <p className="beta-err">{err}</p>}
      </section>
    </div>
  );
}

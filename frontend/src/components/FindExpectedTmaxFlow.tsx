import { useState } from "react";
import {
  applyResearchToDecisions,
  createResearchCenterTasks,
  formatApiError,
  getResearchCenterTask,
  runResearchCenterTask,
  verifyResearchCenterClaim,
} from "../api/client";

type Claim = {
  id?: string;
  claim_text?: string;
  excerpt?: string;
  value?: unknown;
  field_path?: string;
  verification_status?: string;
  measurement?: Record<string, unknown>;
  confidence?: unknown;
  source_type?: string;
};

type Props = {
  studyId: string;
  reviewer: string;
  busy: boolean;
  activeSubstance?: string;
  dosageForm?: string;
  onNotice: (msg: string) => void;
  onDone: () => Promise<void>;
  runAction: (fn: () => Promise<void>) => Promise<void>;
};

/**
 * Knowledge gap → Research → AI PROPOSAL → expert verify → apply to Sampling.
 * Does not invent sampling timepoints; only supplies verified expected (planning) Tmax.
 */
export function FindExpectedTmaxFlow(props: Props) {
  const {
    studyId,
    reviewer,
    busy,
    activeSubstance = "upadacitinib",
    dosageForm = "tablet",
    onNotice,
    onDone,
    runAction,
  } = props;

  const [open, setOpen] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [localBusy, setLocalBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function startSearch() {
    setError(null);
    setLocalBusy(true);
    try {
      const created = await createResearchCenterTasks(studyId, {
        from_decisions: false,
        use_golden_fixture: false,
        gaps: [
          {
            code: "MISSING_TMAX_FOR_SAMPLING",
            title: `Find expected Tmax for ${activeSubstance} (${dosageForm})`,
          },
        ],
        active_substance: activeSubstance,
        dosage_form: dosageForm,
      });
      const tasks = (created.tasks as Array<Record<string, unknown>>) || [];
      const task = tasks[0];
      if (!task?.id) throw new Error("Research task was not created");
      const tid = String(task.id);
      setTaskId(tid);
      await runResearchCenterTask(tid, { use_mock_provider: true });
      const view = await getResearchCenterTask(tid);
      const ev = (view.evidence as Claim[]) || [];
      setClaims(ev);
      setOpen(true);
      onNotice("AI PROPOSAL: ожидаемый Tmax найден — нужна экспертная проверка");
    } catch (err: unknown) {
      setError(formatApiError(err));
    } finally {
      setLocalBusy(false);
    }
  }

  async function confirmClaim(claimId: string) {
    setError(null);
    await runAction(async () => {
      setLocalBusy(true);
      try {
        await verifyResearchCenterClaim(claimId, {
          reviewer: reviewer || "writer",
          applicability: "HIGH",
          applicability_reason: "Expert-verified expected (planning) Tmax for sampling design",
        });
        await applyResearchToDecisions(studyId, { use_golden_fixture: false });
        onNotice("Ожидаемый Tmax подтверждён (VERIFIED) — Sampling может пересчитаться");
        await onDone();
        setOpen(false);
      } catch (err: unknown) {
        setError(formatApiError(err));
        throw err;
      } finally {
        setLocalBusy(false);
      }
    });
  }

  const disabled = busy || localBusy;

  return (
    <div className="find-tmax-flow" onClick={(e) => e.stopPropagation()}>
      <button type="button" className="secondary" disabled={disabled} onClick={() => void startSearch()}>
        Найти Tmax
      </button>
      {error ? <p className="error small">{error}</p> : null}
      {open ? (
        <div className="ai-proposal-box">
          <h4>AI PROPOSAL — ожидаемый (плановый) Tmax</h4>
          <p className="muted small">
            Это не наблюдаемый Tmax после исследования. Sampling engine использует значение только после
            «Подтвердить». Task: {taskId || "—"}
          </p>
          {claims.length === 0 ? (
            <p className="muted small">Нет извлечённых claims — уточните источники вручную.</p>
          ) : (
            <ul className="small">
              {claims.map((c) => {
                const id = String(c.id || "");
                const val =
                  c.value ??
                  c.measurement?.value ??
                  (c.measurement?.range_low != null
                    ? `${c.measurement.range_low}–${c.measurement.range_high}`
                    : "—");
                return (
                  <li key={id || c.claim_text}>
                    <div>
                      <strong>Tmax: {String(val)}</strong>
                      {c.verification_status ? (
                        <span className="muted"> — {String(c.verification_status)}</span>
                      ) : null}
                    </div>
                    {c.excerpt ? <div className="muted">{String(c.excerpt).slice(0, 240)}</div> : null}
                    {id && String(c.verification_status || "").toUpperCase() !== "VERIFIED" ? (
                      <button type="button" disabled={disabled} onClick={() => void confirmClaim(id)}>
                        Подтвердить Tmax
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      ) : null}
    </div>
  );
}

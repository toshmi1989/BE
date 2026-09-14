import { useState } from "react";
import {
  extractProductEvidence,
  formatApiError,
  listProductEvidence,
  reviewProductEvidence,
  type ProductEvidencePanel,
  type ProductEvidenceProposal,
} from "../api/client";

export type ProductEvidencePanelProps = {
  studyId: string;
  reviewer: string;
  canApprove: boolean;
  busy: boolean;
  onNotice: (msg: string) => void;
  onRefresh: () => Promise<void>;
};

export function ProductEvidenceReview(props: ProductEvidencePanelProps) {
  const { studyId, reviewer, canApprove, busy, onNotice, onRefresh } = props;
  const [panel, setPanel] = useState<ProductEvidencePanel | null>(null);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      setPanel(await listProductEvidence(studyId));
      setLoaded(true);
    } catch (e) {
      onNotice(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }

  async function runExtract() {
    setLoading(true);
    try {
      const res = await extractProductEvidence(studyId, {
        force_mock: false,
        actor: reviewer || "writer",
      });
      onNotice(
        `Извлечение: ${String(res.claims_created ?? 0)} предложений (PROPOSED). AI confidence ≠ verification.`,
      );
      setPanel(await listProductEvidence(studyId));
      setLoaded(true);
      await onRefresh();
    } catch (e) {
      onNotice(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }

  async function act(p: ProductEvidenceProposal, action: "verify" | "reject") {
    if (!canApprove) {
      onNotice("Нет права подтверждать evidence");
      return;
    }
    setLoading(true);
    try {
      await reviewProductEvidence(studyId, {
        claim_id: p.claim_id,
        action,
        reviewer: reviewer || "expert",
        applicability: "DIRECT",
        applicability_reason:
          action === "verify"
            ? "Проверено экспертом для текущего исследования / дозировки"
            : undefined,
        comment: action === "reject" ? "Отклонено экспертом" : undefined,
      });
      onNotice(action === "verify" ? "Evidence VERIFIED" : "Evidence REJECTED");
      setPanel(await listProductEvidence(studyId));
      await onRefresh();
    } catch (e) {
      onNotice(formatApiError(e));
    } finally {
      setLoading(false);
    }
  }

  if (!loaded && !panel) {
    return (
      <section className="card" style={{ marginTop: 16 }}>
        <h3>PRODUCT EVIDENCE REVIEW</h3>
        <p className="muted">
          AI / deterministic extraction → PROPOSED claims. Verify clears FINAL pharmacology gate only
          when applicable.
        </p>
        <div className="row" style={{ gap: 8 }}>
          <button type="button" disabled={busy || loading} onClick={() => void refresh()}>
            Загрузить предложения
          </button>
          <button type="button" disabled={busy || loading} onClick={() => void runExtract()}>
            Извлечь из источников
          </button>
        </div>
      </section>
    );
  }

  const proposals = panel?.proposals || [];
  const proposed = proposals.filter((p) => p.status === "PROPOSED");

  return (
    <section className="card" style={{ marginTop: 16 }}>
      <h3>PRODUCT EVIDENCE REVIEW</h3>
      <p className="muted">
        🤖 AI proposal · confidence ≠ verified. Unverified claims cannot clear FINAL DOCX gate.
      </p>
      <div className="row" style={{ gap: 8, marginBottom: 8 }}>
        <button type="button" disabled={busy || loading} onClick={() => void runExtract()}>
          Извлечь из источников
        </button>
        <button type="button" disabled={busy || loading} onClick={() => void refresh()}>
          Обновить
        </button>
        <span className="muted">
          proposed={panel?.counts.proposed ?? 0} · verified={panel?.counts.verified ?? 0} ·
          pharmacology_verified={String(panel?.pharmacology_verified ?? false)}
        </span>
      </div>
      {proposed.length === 0 ? (
        <p className="muted">Нет PROPOSED product claims — запустите извлечение или research по пробелам.</p>
      ) : (
        <ul className="stack" style={{ listStyle: "none", padding: 0 }}>
          {proposed.map((p) => (
            <li key={p.claim_id} className="card" style={{ marginBottom: 8 }}>
              <div>
                <strong>{p.badge || "Proposal"}</strong> · <code>{p.field}</code>
              </div>
              <div>
                Value: <strong>{String(p.value ?? "—")}</strong>
                {p.unit ? ` ${p.unit}` : ""}
              </div>
              <div className="muted">Source: {p.source_id || "—"} · Location: {p.location || "—"}</div>
              <div className="muted">Excerpt: {p.excerpt || "—"}</div>
              <div className="muted">
                🤖 AI proposal · Status: <strong>PROPOSED</strong> (not verified)
              </div>
              <div className="muted">
                AI confidence: {p.confidence || "—"} — confidence ≠ verification
              </div>
              <div className="muted">Applicability: {p.applicability || "UNKNOWN"}</div>
              <div className="row" style={{ gap: 8, marginTop: 8 }}>
                <button type="button" disabled={!canApprove || busy || loading} onClick={() => void act(p, "verify")}>
                  Verify
                </button>
                <button type="button" disabled={!canApprove || busy || loading} onClick={() => void act(p, "reject")}>
                  Reject
                </button>
                <button
                  type="button"
                  disabled={busy || loading}
                  onClick={() => void runExtract()}
                  title="Request another source / re-extract"
                >
                  Request another source
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

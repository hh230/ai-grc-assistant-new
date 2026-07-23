import { useState } from "react";

import type { DecisionItem, RecentDecision } from "../api/client";
import { typeLabel } from "../labels";
import type { DecisionOutcome } from "./presenter";
import { useDecisions } from "./useDecisions";

// Decisions — "What decisions are waiting for me?" A list of DECISIONS, not missions: each card is a
// decision (the mission is context) carrying enough to decide in five seconds — proposed action,
// mission, waiting-since, evidence count — with Approve/Reject (the reused S2 command), a one-click
// path to the evidence, and a secondary "Open Mission →". When nothing waits, recent decisions keep
// the page alive.
export function DecisionsView({
  onOpenMission,
  onReviewEvidence,
}: {
  onOpenMission: (missionId: string) => void;
  onReviewEvidence: (missionId: string) => void;
}) {
  const { state, canDecide, approve, reject } = useDecisions();

  return (
    <section className="decisions">
      <header className="decisions__header">
        <h1>Decisions</h1>
        <p className="decisions__subtitle">What decisions are waiting for me?</p>
      </header>

      {state.kind === "loading" && <p className="decisions__note">Loading…</p>}

      {state.kind === "error" && (
        <p className="decisions__note decisions__note--error">
          Couldn’t load decisions: {state.message}
        </p>
      )}

      {state.kind === "ready" && (
        <>
          {state.outcome !== null && <OutcomeBanner outcome={state.outcome} />}
          {state.items.length === 0 ? (
            <NothingWaiting recent={state.recent} />
          ) : (
            <ul className="decisions__list">
              {state.items.map((d) => (
                <DecisionCard
                  key={d.decision_id}
                  decision={d}
                  canDecide={canDecide}
                  onApprove={() => approve(d.mission_id, d.decision_id)}
                  onReject={() => reject(d.mission_id, d.decision_id)}
                  onReviewEvidence={() => onReviewEvidence(d.mission_id)}
                  onOpenMission={() => onOpenMission(d.mission_id)}
                />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

// #7 — after a decision, say what the decision *did* to the mission, in human terms (the user pressed
// Approve and is waiting to learn "what happened next?" — not "what is the current status?").
function OutcomeBanner({ outcome }: { outcome: DecisionOutcome }) {
  const approved = outcome.decided === "approved";
  const verb = approved ? "Approved" : "Rejected";
  const mark = approved ? "✓ " : "";
  const effect = approved ? "has resumed" : "was stopped";
  return (
    <div className={`decision-outcome decision-outcome--${outcome.decided}`}>
      {mark}
      {verb} — {typeLabel(outcome.missionType)} · {outcome.missionScope} {effect}.
    </div>
  );
}

function NothingWaiting({ recent }: { recent: RecentDecision[] }) {
  // The page stays alive: a positive banner, then the last couple of decisions already made.
  return (
    <>
      <div className="decisions__clear">✓ Nothing waiting for your decision</div>
      {recent.length > 0 && (
        <section className="recent-decisions">
          <h2 className="recent-decisions__title">Recent decisions</h2>
          <ul className="recent-decisions__list">
            {recent.map((r, i) => (
              <li key={i} className="recent-decision">
                <span className={`recent-decision__badge recent-decision__badge--${r.approved ? "approved" : "rejected"}`}>
                  {r.approved ? "Approved" : "Rejected"}
                </span>
                <span className="recent-decision__action">{r.proposed_action}</span>
                <span className="recent-decision__time">{timeAgo(r.decided_at)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function DecisionCard({
  decision,
  canDecide,
  onApprove,
  onReject,
  onReviewEvidence,
  onOpenMission,
}: {
  decision: DecisionItem;
  canDecide: boolean;
  onApprove: () => Promise<void>;
  onReject: () => Promise<void>;
  onReviewEvidence: () => void;
  onOpenMission: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function decide(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false); // stay on the card to show the error (on success the card leaves the list)
    }
  }

  return (
    <li className="decision">
      <div className="decision__action">{decision.proposed_action}</div>
      <dl className="decision__facts">
        <dt>Mission</dt>
        <dd>
          {typeLabel(decision.mission_type)} · {decision.mission_scope}
        </dd>
        <dt>Waiting since</dt>
        <dd>{timeAgo(decision.waiting_since)}</dd>
        <dt>Evidence</dt>
        <dd>
          {evidenceLabel(decision.evidence_count)}
          <button className="decision__evidence-link" onClick={onReviewEvidence}>
            Review evidence →
          </button>
        </dd>
      </dl>

      {error !== null && <p className="decision__error">{error}</p>}

      <div className="decision__actions">
        {canDecide ? (
          <>
            <button
              className="gate__approve"
              disabled={busy}
              onClick={() => void decide(onApprove)}
            >
              {busy ? "…" : "Approve"}
            </button>
            <button
              className="gate__reject"
              disabled={busy}
              onClick={() => void decide(onReject)}
            >
              Reject
            </button>
          </>
        ) : (
          <span className="decision__muted">You don’t have permission to decide.</span>
        )}
        <button className="decision__open" onClick={onOpenMission}>
          Open Mission →
        </button>
      </div>
    </li>
  );
}

function evidenceLabel(n: number): string {
  if (n === 0) return "no evidence yet";
  return n === 1 ? "1 document" : `${n} documents`;
}

function timeAgo(epochSeconds: number): string {
  const min = Math.round((Date.now() - epochSeconds * 1000) / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return hr === 1 ? "1 hour ago" : `${hr} hours ago`;
  const d = Math.round(hr / 24);
  return d === 1 ? "yesterday" : `${d} days ago`;
}

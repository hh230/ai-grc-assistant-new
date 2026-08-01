import { useState } from "react";

import type { MissionDetail } from "../api/client";
import { statusLabel, typeLabel } from "../labels";
import { useMissionDetail } from "./useMissionDetail";

// The Work Surface. Mission Detail is ONE workspace; the tabs are just views of the same mission
// state (owner's rule — not independent pages with their own routing/source of truth). Each tab
// answers one question: Summary "what is this?" · Plan "what will it do?" · Execution "what has it
// done?" · Evidence "why?" · Decisions "what decision?" · Result "what did it produce?".
// NB: "Execution" — not "Findings" — because these are execution steps, not GRC findings yet; we
// don't use the word "Finding" until it means one (real findings arrive in S3/S4). Honest naming,
// like Evidence Mapping. The tab *keys* stay stable (Approvals/Deliverable); the user reads the
// product words via TAB_LABELS — Decisions and Result, the words the rest of the product already uses.
const TABS = ["Summary", "Plan", "Execution", "Evidence", "Approvals", "Deliverable"] as const;
type Tab = (typeof TABS)[number];

const TAB_LABELS: Record<Tab, string> = {
  Summary: "Summary",
  Plan: "Plan",
  Execution: "Execution",
  Evidence: "Evidence",
  Approvals: "Decisions",
  Deliverable: "Result",
};

export function MissionDetailView({
  missionId,
  onBack,
  onOpenResult,
  initialTab = "Summary",
  backLabel = "← Missions",
}: {
  missionId: string;
  onBack: () => void;
  onOpenResult: (missionId: string) => void;
  initialTab?: Tab;
  backLabel?: string;
}) {
  const { state, canApprove, approve, reject } = useMissionDetail(missionId);
  const [tab, setTab] = useState<Tab>(initialTab);

  return (
    <section className="detail">
      <button className="detail__back" onClick={onBack}>
        {backLabel}
      </button>

      {state.kind === "loading" && <p className="missions__note">Loading…</p>}
      {state.kind === "error" && (
        <p className="missions__note missions__note--error">Couldn’t load mission: {state.message}</p>
      )}

      {state.kind === "ready" && (
        <>
          <header className="detail__head">
            <h1>{typeLabel(state.detail.type)}</h1>
            <span className="detail__scope">{state.detail.scope}</span>
            <span className={`mission__status mission__status--${state.detail.status}`}>
              {statusLabel(state.detail.status)}
            </span>
          </header>

          <TrustBar detail={state.detail} />

          <nav className="detail__tabs">
            {TABS.map((t) => (
              <button
                key={t}
                className={`detail__tab ${t === tab ? "detail__tab--active" : ""}`}
                onClick={() => setTab(t)}
              >
                {TAB_LABELS[t]}
              </button>
            ))}
          </nav>

          <div className="detail__panel">
            <TabContent
              tab={tab}
              detail={state.detail}
              canApprove={canApprove}
              onApprove={approve}
              onReject={reject}
              onOpenResult={onOpenResult}
            />
          </div>
        </>
      )}
    </section>
  );
}

function TabContent({
  tab,
  detail,
  canApprove,
  onApprove,
  onReject,
  onOpenResult,
}: {
  tab: Tab;
  detail: MissionDetail;
  canApprove: boolean;
  onApprove: (stepId: string, comment?: string) => Promise<void>;
  onReject: (stepId: string, comment?: string) => Promise<void>;
  onOpenResult: (missionId: string) => void;
}) {
  switch (tab) {
    case "Summary":
      return (
        <dl className="kv">
          <dt>Type</dt>
          <dd>{typeLabel(detail.type)}</dd>
          <dt>Scope</dt>
          <dd>{detail.scope}</dd>
          <dt>Status</dt>
          <dd>{statusLabel(detail.status)}</dd>
          <dt>Updated</dt>
          <dd>{timeAgo(detail.updated_at)}</dd>
        </dl>
      );
    case "Plan":
      return (
        <ol className="plan">
          {detail.plan.map((step) => (
            <li key={step.id}>{step.description}</li>
          ))}
        </ol>
      );
    case "Execution":
      return detail.findings.length === 0 ? (
        <p className="missions__note">No steps have run yet.</p>
      ) : (
        <ul className="findings">
          {detail.findings.map((f) => (
            <li key={f.step_id}>
              <strong>{f.title}</strong>
              <p>{f.summary}</p>
              {f.citations.length > 0 && <span className="findings__cite">{f.citations.join(" · ")}</span>}
            </li>
          ))}
        </ul>
      );
    case "Evidence": {
      const cites = [...new Set(detail.findings.flatMap((f) => f.citations))];
      return cites.length === 0 ? (
        <p className="missions__note">No cited evidence yet.</p>
      ) : (
        <ul className="evidence">
          {cites.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      );
    }
    case "Approvals":
      return (
        <ApprovalsTab
          detail={detail}
          canApprove={canApprove}
          onApprove={onApprove}
          onReject={onReject}
        />
      );
    case "Deliverable":
      return detail.status === "completed" ? (
        <button className="missions__cta" onClick={() => onOpenResult(detail.id)}>
          Open Result →
        </button>
      ) : (
        <p className="missions__note">Available when the mission completes.</p>
      );
  }
}

// A **Decision Card** (not just two buttons): it says *why* the mission paused, what the system
// recommends, and on how much evidence — so "AI explains before it recommends" is visible — then the
// decision. The AI recommendation is shown honestly: the Core produces none yet, so we say so rather
// than fabricate one (the same honesty as not calling execution steps "findings").
function ApprovalsTab({
  detail,
  canApprove,
  onApprove,
  onReject,
}: {
  detail: MissionDetail;
  canApprove: boolean;
  onApprove: (stepId: string, comment?: string) => Promise<void>;
  onReject: (stepId: string, comment?: string) => Promise<void>;
}) {
  const gate = detail.approval;
  if (!gate || gate.status !== "pending") {
    return <p className="missions__note">No decision is waiting.</p>;
  }
  return (
    <div className="gate">
      <p className="gate__title">Human decision required</p>
      <dl className="gate__facts">
        <dt>Proposed action</dt>
        <dd>{cleanReason(gate.proposed_action)}</dd>
        <dt>AI recommendation</dt>
        <dd className="gate__muted">not available yet</dd>
        <dt>Evidence</dt>
        <dd>{evidenceCount(detail)} document(s)</dd>
      </dl>
      {/* Constraint 4: the buttons render ONLY for an Approver — not merely a 403 on click. */}
      {canApprove ? (
        <div className="gate__actions">
          <button className="gate__reject" onClick={() => void onReject(gate.id)}>
            Reject
          </button>
          <button className="gate__approve" onClick={() => void onApprove(gate.id)}>
            Approve
          </button>
        </div>
      ) : (
        <p className="gate__note">Waiting on an Approver.</p>
      )}
    </div>
  );
}

// A small **trust strip** at the top of the Work Surface: the customer knows at a glance what they
// are looking at and how far it can be trusted (the "Can I trust this?" question starts here, not
// only on the Deliverable). Framework is not a first-class API field yet (scope is free text), so it
// is left out honestly rather than parsed out of the scope string.
function TrustBar({ detail }: { detail: MissionDetail }) {
  const count = evidenceCount(detail);
  return (
    <>
      <div className="trustbar">
        <span>
          <strong>{count}</strong> evidence
        </span>
        <span>
          Human review: <strong>{humanReview(detail)}</strong>
        </span>
        <span>Updated {timeAgo(detail.updated_at)}</span>
      </div>
      {/* #6 — a zero-evidence result is confusing without a "why". Say it, honestly and plainly. */}
      {count === 0 && detail.status === "completed" && (
        <div className="no-evidence-note">
          <span>No relevant evidence was found for this mission yet.</span>
          <span className="no-evidence-note__cta">Add evidence to improve this result.</span>
        </div>
      )}
    </>
  );
}

function evidenceCount(detail: MissionDetail): number {
  return new Set(detail.findings.flatMap((f) => f.citations)).size;
}

function humanReview(detail: MissionDetail): string {
  if (!detail.approval) return "Not required";
  return titleCase(detail.approval.status); // Pending | Approved | Rejected
}

function cleanReason(reason: string): string {
  // The Core reason reads "approval required before step stp_xxx: <description>". Show the human
  // part only — this also drops the internal step id from the UI.
  const idx = reason.lastIndexOf(": ");
  return idx >= 0 ? reason.slice(idx + 2) : reason;
}

function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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

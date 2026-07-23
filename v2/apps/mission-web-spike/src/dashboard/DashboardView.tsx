import type { CoverageSnapshot, DashboardData, RecentMission } from "../api/client";
import { typeLabel } from "../labels";
import { useDashboard } from "./useDashboard";

// A Missions-list filter the Dashboard navigates to (a card's "journey").
export type MissionFilter = { status?: string; type?: string };

// Dashboard — "What needs my attention right now?" Attention-first: Waiting (the primary CTA when > 0)
// → Running → Failed → Recently completed → Coverage snapshot (last). Every card has a journey; there
// are no analytics (user/document counts, storage) — Dashboard ≠ Analytics.
export function DashboardView({
  onOpenMissions,
  onOpenMission,
  onNewMission,
}: {
  onOpenMissions: (filter: MissionFilter) => void;
  onOpenMission: (missionId: string) => void;
  onNewMission: () => void;
}) {
  const { load, reload } = useDashboard();

  return (
    <section className="dashboard">
      <header className="dashboard__header">
        <div className="dashboard__titles">
          <h1>Dashboard</h1>
          <p className="dashboard__subtitle">What needs my attention right now?</p>
        </div>
        <button className="dashboard__cta" onClick={onNewMission}>
          + New Mission
        </button>
      </header>

      {load.state === "loading" && <p className="dashboard__note">Loading…</p>}

      {load.state === "error" && (
        <p className="dashboard__note dashboard__note--error">
          Couldn’t load the dashboard: {load.message} <button onClick={reload}>Retry</button>
        </p>
      )}

      {load.state === "ready" && (
        <Body data={load.data} onOpenMissions={onOpenMissions} onOpenMission={onOpenMission} />
      )}
    </section>
  );
}

function Body({
  data,
  onOpenMissions,
  onOpenMission,
}: {
  data: DashboardData;
  onOpenMissions: (filter: MissionFilter) => void;
  onOpenMission: (missionId: string) => void;
}) {
  return (
    <>
      <Attention data={data} onOpenMissions={onOpenMissions} />

      <section className="recent">
        <h2 className="recent__title">Recently completed</h2>
        {data.recent.length === 0 ? (
          <p className="dashboard__note">Nothing completed yet.</p>
        ) : (
          <ul className="recent__list">
            {/* the user wants to know *what* finished — the last two, not a number */}
            {data.recent.slice(0, 2).map((m) => (
              <RecentRow key={m.id} m={m} onOpen={() => onOpenMission(m.id)} />
            ))}
          </ul>
        )}
      </section>

      <CoverageCard
        coverage={data.coverage}
        onOpen={() => onOpenMissions({ type: "gap_assessment" })}
      />
    </>
  );
}

function Attention({
  data,
  onOpenMissions,
}: {
  data: DashboardData;
  onOpenMissions: (filter: MissionFilter) => void;
}) {
  // Nothing waiting, running, or failed → the page is still alive: a small positive banner.
  if (data.waiting === 0 && data.running === 0 && data.failed === 0) {
    return <div className="attention__clear">✓ Nothing needs your attention right now.</div>;
  }
  return (
    <div className="attention-block">
      {/* Waiting is the Primary CTA when > 0 — the eye lands here first. */}
      {data.waiting > 0 && (
        <button
          className="attention__primary"
          onClick={() => onOpenMissions({ status: "awaiting_approval" })}
        >
          <span className="attention__primary-count">{data.waiting}</span>
          <span className="attention__primary-text">
            <span className="attention__primary-label">Waiting for you</span>
            <span className="attention__primary-sub">Decisions waiting for you</span>
          </span>
          <span className="attention__primary-cta">Review now →</span>
        </button>
      )}
      <ul className="attention">
        {data.waiting === 0 && (
          <AttentionCard
            n={0}
            label="Waiting for you"
            tone="waiting"
            onClick={() => onOpenMissions({ status: "awaiting_approval" })}
          />
        )}
        <AttentionCard
          n={data.running}
          label="Running"
          tone="running"
          onClick={() => onOpenMissions({ status: "executing" })}
        />
        <AttentionCard
          n={data.failed}
          label="Failed"
          tone="failed"
          onClick={() => onOpenMissions({ status: "failed" })}
        />
      </ul>
    </div>
  );
}

function AttentionCard({
  n,
  label,
  tone,
  onClick,
}: {
  n: number;
  label: string;
  tone: string;
  onClick: () => void;
}) {
  return (
    <li>
      <button className={`attention__card attention__card--${tone}`} onClick={onClick}>
        <span className="attention__count">{n}</span>
        <span className="attention__label">{label}</span>
      </button>
    </li>
  );
}

function RecentRow({ m, onOpen }: { m: RecentMission; onOpen: () => void }) {
  return (
    <li className="recent__item">
      <button className="recent__open" onClick={onOpen}>
        <span className="recent__type">{typeLabel(m.type)}</span>
        <span className="recent__scope">{m.scope}</span>
        <span className="recent__time">{timeAgo(m.completed_at)}</span>
      </button>
    </li>
  );
}

function CoverageCard({
  coverage,
  onOpen,
}: {
  coverage: CoverageSnapshot | null;
  onOpen: () => void;
}) {
  // Last, by design — and clickable, to the filtered Gap Assessments (never to a "report").
  return (
    <button className="coverage-snapshot" onClick={onOpen}>
      <span className="coverage-snapshot__title">Coverage snapshot →</span>
      {coverage === null ? (
        <span className="dashboard__note">
          No coverage yet — run a Gap Assessment to see where you stand.
        </span>
      ) : (
        <span className="coverage-snapshot__body">
          <span className="coverage-snapshot__pct">{Math.round(coverage.percent * 100)}%</span>
          <span className="coverage-snapshot__detail">
            {coverage.covered} of {coverage.total} controls with evidence
          </span>
        </span>
      )}
      {/* Protects the line the whole product defends: mapping, not attestation. */}
      <span className="coverage-snapshot__caveat">Based on completed Gap Assessments only.</span>
    </button>
  );
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

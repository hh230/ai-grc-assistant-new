import { useEffect, useMemo, useState } from "react";

import {
  MissionApiClient,
  type MissionListItem,
  type MissionListResponse,
} from "./api/client";
import { statusLabel, typeLabel } from "./labels";

const STATUSES = ["", "executing", "awaiting_approval", "completed", "failed"];
const TYPES = [
  "",
  "gap_assessment",
  "risk_assessment",
  "vendor_review",
  "policy_generator",
  "iso_controls",
];
const PAGE_SIZE = 4;

const SUMMARY = [
  { key: "executing", label: "Running" },
  { key: "awaiting_approval", label: "Awaiting decision" },
  { key: "completed", label: "Completed" },
  { key: "failed", label: "Failed" },
];

type Load =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; data: MissionListResponse };

export function MissionsView({
  onOpen,
  onNewMission,
  initialStatus = "",
  initialType = "",
}: {
  onOpen: (missionId: string) => void;
  onNewMission: () => void;
  initialStatus?: string;
  initialType?: string;
}) {
  const client = useMemo(() => new MissionApiClient(), []);
  const [status, setStatus] = useState(initialStatus);
  const [type, setType] = useState(initialType);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const [load, setLoad] = useState<Load>({ state: "loading" });

  useEffect(() => {
    let live = true;
    setLoad({ state: "loading" });
    client
      .listMissions({
        status: status || undefined,
        type: type || undefined,
        q: q || undefined,
        page,
        page_size: PAGE_SIZE,
      })
      .then((data) => live && setLoad({ state: "ready", data }))
      .catch((e: unknown) => {
        const message = e instanceof Error ? e.message : String(e);
        if (live) setLoad({ state: "error", message });
      });
    return () => {
      live = false;
    };
  }, [client, status, type, q, page, reloadKey]);

  function setFilter(setter: (v: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  return (
    <section className="missions">
      <header className="missions__header">
        <div className="missions__top">
          <h1>Missions</h1>
          <button className="missions__cta" onClick={onNewMission}>
            + New Mission
          </button>
        </div>

        <SummaryStrip
          client={client}
          reloadKey={reloadKey}
          onFilterStatus={(s) => setFilter(setStatus, s)}
        />

        <div className="missions__filters">
          <input
            placeholder="Search scope…"
            value={q}
            onChange={(e) => setFilter(setQ, e.target.value)}
          />
          <select value={status} onChange={(e) => setFilter(setStatus, e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s ? statusLabel(s) : "All statuses"}
              </option>
            ))}
          </select>
          <select value={type} onChange={(e) => setFilter(setType, e.target.value)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t ? typeLabel(t) : "All types"}
              </option>
            ))}
          </select>
        </div>
      </header>

      {load.state === "loading" && <p className="missions__note">Loading…</p>}

      {load.state === "error" && (
        <p className="missions__note missions__note--error">
          Couldn’t load missions: {load.message}{" "}
          <button onClick={() => setReloadKey((k) => k + 1)}>Retry</button>
        </p>
      )}

      {load.state === "ready" &&
        (load.data.items.length === 0 ? (
          <p className="missions__note">No missions match — try clearing filters, or start a new one.</p>
        ) : (
          <MissionRows data={load.data} page={page} onPage={setPage} onOpen={onOpen} />
        ))}
    </section>
  );
}

function SummaryStrip({
  client,
  reloadKey,
  onFilterStatus,
}: {
  client: MissionApiClient;
  reloadKey: number;
  onFilterStatus: (status: string) => void;
}) {
  const [items, setItems] = useState<MissionListItem[] | null>(null);

  useEffect(() => {
    let live = true;
    client
      .listMissions({ page_size: 200 })
      .then((data) => live && setItems(data.items))
      .catch(() => live && setItems(null));
    return () => {
      live = false;
    };
  }, [client, reloadKey]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const m of items ?? []) c[m.status] = (c[m.status] ?? 0) + 1;
    return c;
  }, [items]);

  if (items === null) return null;

  return (
    <div className="summary">
      {SUMMARY.map(({ key, label: text }) => (
        <button
          key={key}
          className={`summary__chip summary__chip--${key}`}
          onClick={() => onFilterStatus(key)}
          title={`Filter to ${text}`}
        >
          <span className="summary__count">{counts[key] ?? 0}</span>
          <span className="summary__label">{text}</span>
        </button>
      ))}
    </div>
  );
}

function MissionRows({
  data,
  page,
  onPage,
  onOpen,
}: {
  data: MissionListResponse;
  page: number;
  onPage: (p: number) => void;
  onOpen: (missionId: string) => void;
}) {
  return (
    <>
      <ul className="missions__list">
        {data.items.map((m) => (
          <MissionRow key={m.id} m={m} onOpen={onOpen} />
        ))}
      </ul>
      <footer className="missions__pager">
        <button disabled={page <= 1} onClick={() => onPage(page - 1)}>
          Prev
        </button>
        <span>
          Page {data.page} · {data.total} total
        </span>
        <button disabled={!data.has_next} onClick={() => onPage(page + 1)}>
          Next
        </button>
      </footer>
    </>
  );
}

function MissionRow({ m, onOpen }: { m: MissionListItem; onOpen: (missionId: string) => void }) {
  // The whole row is the click target — the one primary decision: open this mission.
  return (
    <li className="mission">
      <button className="mission__open" onClick={() => onOpen(m.id)}>
        <span className="mission__type">{typeLabel(m.type)}</span>
        <span className="mission__scope">{m.scope}</span>
        <span className="mission__meta">
          <span className={`mission__status mission__status--${m.status}`}>{statusLabel(m.status)}</span>
          <span className="mission__time">{timeAgo(m.updated_at)}</span>
        </span>
      </button>
    </li>
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

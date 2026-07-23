import { useMemo } from "react";

import type { MissionApiClient, ResultView, TrustBarData } from "../api/client";
import { typeLabel } from "../labels";
import { ResultPresenterRegistry } from "./presenters";
import { useResult } from "./useResult";

// The Result page. The user sees "Result" (the domain's "Deliverable" never appears). Fixed order —
// evidence-first: Trust Bar → content → Export (last). The page never switches on content kind: the
// presenter registry decides how content renders and which exports it offers.
export function ResultPage({ missionId, onBack }: { missionId: string; onBack: () => void }) {
  const { client, state } = useResult(missionId);
  const registry = useMemo(() => new ResultPresenterRegistry(), []);

  return (
    <section className="result">
      <button className="detail__back" onClick={onBack}>
        ← Back
      </button>
      {state.kind === "loading" && <p className="missions__note">Loading…</p>}
      {state.kind === "error" && (
        <p className="missions__note missions__note--error">Couldn’t load result: {state.message}</p>
      )}
      {state.kind === "ready" && <ResultBody result={state.result} client={client} registry={registry} />}
    </section>
  );
}

function ResultBody({
  result,
  client,
  registry,
}: {
  result: ResultView;
  client: MissionApiClient;
  registry: ResultPresenterRegistry;
}) {
  const presenter = registry.forContent(result.content);
  return (
    <>
      <header className="detail__head">
        <h1>Result</h1>
        <span className="detail__scope">{prettyTitle(result.title)}</span>
      </header>

      {/* 1. Trust Bar — the frame, first (evidence-first). */}
      <TrustBar trust={result.trust} />

      {/* #6 — a zero-evidence result reads as "broken" without a reason. Give one, plainly. */}
      {result.trust.evidence_count === 0 && (
        <div className="no-evidence-note">
          <span>No relevant evidence was found for this mission yet.</span>
          <span className="no-evidence-note__cta">Add evidence to improve this result.</span>
        </div>
      )}

      {/* 2. Content — the presenter for this result type (no switch here). */}
      <div className="result__content">
        <presenter.Content result={result} />
      </div>

      {/* 3. Export — last; the presenter says which formats this result offers. */}
      <ExportBar
        formats={presenter.availableExports}
        onExport={(fmt) => downloadExport(client, result, fmt)}
      />
    </>
  );
}

function TrustBar({ trust }: { trust: TrustBarData }) {
  return (
    <div className="trustbar">
      <span>
        <strong>{trust.evidence_count}</strong> evidence
      </span>
      <span>
        Human review: <strong>{trust.human_review}</strong>
      </span>
      <span>Updated {timeAgo(trust.updated_at)}</span>
    </div>
  );
}

function ExportBar({ formats, onExport }: { formats: string[]; onExport: (fmt: string) => void }) {
  return (
    <footer className="export">
      <span className="export__label">Export</span>
      {formats.map((fmt) => (
        <button key={fmt} className="export__btn" onClick={() => onExport(fmt)}>
          {fmt.toUpperCase()}
        </button>
      ))}
    </footer>
  );
}

// The API title reads "gap assessment: <scope>" (the type lower-cased). Show the product's cased type
// ("Gap Assessment: <scope>") without a backend change — the type token is everything before ": ".
function prettyTitle(title: string): string {
  const idx = title.indexOf(": ");
  if (idx < 0) return title;
  const type = title.slice(0, idx).replace(/ /g, "_");
  return `${typeLabel(type)}: ${title.slice(idx + 2)}`;
}

async function downloadExport(client: MissionApiClient, result: ResultView, fmt: string): Promise<void> {
  const blob = await client.exportResult(result.mission_id, fmt);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${result.mission_id}.${fmt}`;
  anchor.click();
  URL.revokeObjectURL(url);
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

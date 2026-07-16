import type { LibraryOverview } from "@/lib/types/view";
import { formatDateTime, formatInt, formatPercent, rateColor } from "@/lib/format";

const RATE_LABELS: Array<{ key: keyof LibraryOverview; countKey: keyof LibraryOverview; total: keyof LibraryOverview; name: string; denom: string }> = [
  { key: "parsingSuccessRate", countKey: "parsedCount", total: "totalDocuments", name: "Parsing", denom: "documents" },
  { key: "chunkingSuccessRate", countKey: "chunkedCount", total: "parsedCount", name: "Chunking", denom: "parsed docs" },
  { key: "embeddingSuccessRate", countKey: "embeddedCount", total: "chunkedCount", name: "Embedding", denom: "chunked docs" },
];

export function OverviewCards({ overview }: { overview: LibraryOverview }) {
  return (
    <>
      <div className="overview">
        <div className="stat">
          <span className="value">{formatInt(overview.totalDocuments)}</span>
          <span className="label">Total documents</span>
        </div>
        <div className="stat">
          <span className="value">{formatInt(overview.totalPages)}</span>
          <span className="label">Total pages</span>
        </div>
        <div className="stat">
          <span className="value">{formatInt(overview.totalChunks)}</span>
          <span className="label">Total chunks</span>
        </div>
        <div className="stat">
          <span className="value">{formatInt(overview.totalEmbeddings)}</span>
          <span className="label">Total embeddings</span>
        </div>
        <div className="stat">
          <span className="value">{formatInt(overview.totalDocumentProfiles)}</span>
          <span className="label">Document profiles</span>
        </div>
        <div className="stat">
          <span className="value">{formatInt(overview.parsedCount)}</span>
          <span className="label">Parsed</span>
        </div>
        <div className="stat">
          <span className="value">{formatInt(overview.chunkedCount)}</span>
          <span className="label">Chunked</span>
        </div>
        <div className="stat" style={{ gridColumn: "span 1" }}>
          <span className="value" style={{ fontSize: "15px" }}>{formatDateTime(overview.lastPipelineRun)}</span>
          <span className="label">Last pipeline run</span>
        </div>
      </div>

      <div className="rates">
        {RATE_LABELS.map((r) => {
          const value = overview[r.key] as number;
          const count = overview[r.countKey] as number;
          const total = overview[r.total] as number;
          return (
            <div className="rate-card" key={r.name}>
              <div className="rate-head">
                <span className="name">{r.name} success rate</span>
                <span className="pct" style={{ color: rateColor(value) }}>{formatPercent(value)}</span>
              </div>
              <div className="rate-track">
                <div className="rate-fill" style={{ width: `${Math.min(100, value * 100)}%`, background: rateColor(value) }} />
              </div>
              <span className="rate-detail">{formatInt(count)} of {formatInt(total)} {r.denom}</span>
            </div>
          );
        })}
      </div>
    </>
  );
}

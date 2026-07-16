import type { PipelineRun } from "@/lib/types/view";
import { formatDateTime, formatDuration, formatInt } from "@/lib/format";

export function PipelineHistory({ runs }: { runs: PipelineRun[] }) {
  if (runs.length === 0) {
    return <p className="section-note">No pipeline runs recorded yet.</p>;
  }
  return (
    <div className="runs">
      {runs.map((run) => (
        <div className="run" key={run.id}>
          <div>
            <div className="run-stage">
              {run.stage}
              {run.approximate && (
                <span className="badge flat" style={{ marginLeft: 8 }} title="Reconstructed from artifacts; some fields estimated">
                  reconstructed
                </span>
              )}
            </div>
            <div className="run-time">{formatDateTime(run.startTime)}</div>
          </div>
          <div className="cell"><div className="k">Duration</div><div className="v">{formatDuration(run.durationSeconds)}</div></div>
          <div className="cell"><div className="k">Documents</div><div className="v">{formatInt(run.documentsProcessed)}</div></div>
          <div className="cell"><div className="k">Chunks</div><div className="v">{run.chunksGenerated === null ? "—" : formatInt(run.chunksGenerated)}</div></div>
          <div className="cell"><div className="k">Embeddings</div><div className="v">{run.embeddingsGenerated === null ? "—" : formatInt(run.embeddingsGenerated)}</div></div>
          <div className="cell">
            <div className="k">Failures</div>
            <div className="v" style={{ color: run.failures > 0 ? "var(--bad)" : "var(--ok)" }}>{formatInt(run.failures)}</div>
            {run.provider && <div className="run-time">{run.provider}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

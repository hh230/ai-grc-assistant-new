import Link from "next/link";
import { notFound } from "next/navigation";

import {
  loadChunks,
  loadEmbeddingIndex,
  loadEmbeddingManifest,
  loadManifest,
} from "@/lib/services/knowledgeRepository";
import { buildDocumentDetail } from "@/lib/services/documentService";
import { formatBytes, formatDateTime, formatDuration, formatInt } from "@/lib/format";
import type { ChunkStatistics } from "@/lib/types/view";

export const dynamic = "force-dynamic";

function Distribution({ title, data }: { title: string; data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div className="panel">
      <div className="panel-head">{title}</div>
      <div className="dist">
        {entries.map(([label, value]) => (
          <div className="dist-row" key={label}>
            <span className="dist-label">{label}</span>
            <div className="dist-track">
              <div className="dist-fill" style={{ width: `${(value / max) * 100}%` }} />
            </div>
            <span className="dist-val">{formatInt(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ChunkStatsPanels({ stats }: { stats: ChunkStatistics }) {
  return (
    <>
      <div className="panel">
        <div className="panel-head">Chunk statistics</div>
        <dl className="kv">
          <div><dt>Total chunks</dt><dd>{formatInt(stats.total)}</dd></div>
          <div><dt>With page numbers</dt><dd>{formatInt(stats.withPageNumbers)}</dd></div>
          <div><dt>Fallback windows</dt><dd>{formatInt(stats.fallbackWindows)}</dd></div>
          <div><dt>Average characters</dt><dd>{formatInt(stats.averageCharacters)}</dd></div>
          <div><dt>Largest chunk</dt><dd>{formatInt(stats.largestChunkChars)} chars</dd></div>
          <div><dt>Smallest chunk</dt><dd>{formatInt(stats.smallestChunkChars)} chars</dd></div>
        </dl>
      </div>
      <Distribution title="Chunks by content type" data={stats.byContentType} />
    </>
  );
}

export default async function DocumentDetailPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  const decodedId = decodeURIComponent(documentId);

  const [manifest, chunks, embeddingIndex, embeddingManifest] = await Promise.all([
    loadManifest(decodedId),
    loadChunks(decodedId),
    loadEmbeddingIndex(),
    loadEmbeddingManifest(),
  ]);

  if (!manifest) notFound();

  const embeddingCount = embeddingIndex?.counts[decodedId] ?? 0;
  const detail = buildDocumentDetail(manifest, chunks, embeddingCount, embeddingManifest);

  return (
    <main className="shell">
      <Link className="back-link" href="/">← Knowledge Center</Link>

      <div className="topbar">
        <div className="brand">
          <span className="eyebrow">Document detail</span>
          <h1 style={{ unicodeBidi: "isolate" }}>{detail.general.name}</h1>
        </div>
        <span className="crumb mono">{detail.general.relativePath}</span>
      </div>

      <div className="detail-grid">
        {/* General information */}
        <div className="panel">
          <div className="panel-head">General information</div>
          <dl className="kv">
            <div><dt>Category</dt><dd>{detail.general.category}</dd></div>
            <div><dt>Document profile</dt><dd>{detail.general.documentProfile ?? "unmapped"}</dd></div>
            <div><dt>Profile source</dt><dd>{detail.general.profileAssignmentSource ?? "—"}</dd></div>
            <div><dt>Format</dt><dd>{detail.general.extension}</dd></div>
            <div><dt>Size</dt><dd>{formatBytes(detail.general.sizeBytes)}</dd></div>
            <div><dt>Language</dt><dd>{detail.general.language}</dd></div>
            <div><dt>Checksum</dt><dd style={{ fontSize: 11 }}>{detail.general.checksum.slice(0, 16)}…</dd></div>
          </dl>
        </div>

        {/* Pipeline status */}
        <div className="panel">
          <div className="panel-head">
            Pipeline status
            <span className={`badge ${detail.pipelineStatus.status === "parsed" ? "ok" : "bad"}`}>{detail.pipelineStatus.status}</span>
          </div>
          <div className="stage-track">
            {detail.pipelineStatus.stagesCompleted.map((s) => (
              <span className="stage-chip" key={s}>{s}</span>
            ))}
          </div>
          <dl className="kv">
            <div><dt>Parsed</dt><dd>{detail.pipelineStatus.parsed ? "yes" : "no"}</dd></div>
            <div><dt>Chunked</dt><dd>{detail.pipelineStatus.chunked ? "yes" : "no"}</dd></div>
            <div><dt>Embedded</dt><dd>{detail.pipelineStatus.embedded ? "yes" : "no"}</dd></div>
          </dl>
        </div>

        {/* Parsing information */}
        <div className="panel">
          <div className="panel-head">Parsing information</div>
          <dl className="kv">
            <div><dt>Parser</dt><dd>{detail.parsing.parser ?? "—"}</dd></div>
            <div><dt>Engine used</dt><dd>{detail.parsing.parserUsed ?? "—"}</dd></div>
            <div><dt>Fallback used</dt><dd>{detail.parsing.parserFallback ? "yes" : "no"}</dd></div>
            <div><dt>Pages</dt><dd>{formatInt(detail.parsing.pageCount)}</dd></div>
            <div><dt>Characters</dt><dd>{formatInt(detail.parsing.characterCount)}</dd></div>
            <div><dt>Extraction time</dt><dd>{formatDuration(detail.parsing.extractionDuration)}</dd></div>
            <div><dt>Parsed at</dt><dd style={{ fontSize: 11 }}>{formatDateTime(detail.parsing.parsedAt)}</dd></div>
          </dl>
        </div>

        {/* Parser attempts */}
        <div className="panel">
          <div className="panel-head">Parser attempts</div>
          <div className="attempts">
            {detail.parserAttempts.length === 0 && <span className="muted mono" style={{ padding: "4px 0" }}>No attempts recorded.</span>}
            {detail.parserAttempts.map((a, i) => (
              <div className="attempt" key={i}>
                <span className={`flag ${a.ok ? "ok" : "no"}`}>{a.ok ? "●" : "○"}</span>
                <span>{a.backend}</span>
                {a.error && <span className="err">{a.error}</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Chunk statistics */}
        {detail.chunkStats ? (
          <ChunkStatsPanels stats={detail.chunkStats} />
        ) : (
          <div className="panel">
            <div className="panel-head">Chunk statistics</div>
            <p className="no-warn" style={{ color: "var(--ink-faint)" }}>No chunks — document was not chunked.</p>
          </div>
        )}

        {/* Embedding statistics */}
        <div className="panel">
          <div className="panel-head">Embedding statistics</div>
          <dl className="kv">
            <div><dt>Embedded</dt><dd>{detail.embeddingStats.embedded ? "yes" : "no"}</dd></div>
            <div><dt>Embeddings</dt><dd>{formatInt(detail.embeddingStats.count)}</dd></div>
            <div><dt>Provider</dt><dd>{detail.embeddingStats.provider ?? "—"}</dd></div>
            <div><dt>Model</dt><dd style={{ fontSize: 11 }}>{detail.embeddingStats.model ?? "—"}</dd></div>
            <div><dt>Dimensions</dt><dd>{formatInt(detail.embeddingStats.dimensions)}</dd></div>
            <div><dt>Version</dt><dd>{detail.embeddingStats.version ?? "—"}</dd></div>
          </dl>
        </div>

        {/* Citation information */}
        <div className="panel full">
          <div className="panel-head">Citation information <span className="muted mono" style={{ fontWeight: 400 }}>sample of citable units</span></div>
          <div className="citations">
            {detail.citations.length === 0 && <span className="muted mono" style={{ padding: "4px 0" }}>No structured citations for this document.</span>}
            {detail.citations.map((c, i) => (
              <div className="citation" key={i}>
                <span className="code">{c.code ?? "—"}</span>
                <span className="title">{c.title ?? (c.headingPath.length ? c.headingPath.join(" › ") : "—")}</span>
                <span className="page">{c.pageStart !== null ? (c.pageStart === c.pageEnd ? `p. ${c.pageStart}` : `pp. ${c.pageStart}–${c.pageEnd}`) : ""}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Warnings / failures */}
        <div className="panel full">
          <div className="panel-head">Warnings &amp; failures</div>
          {detail.warnings.length === 0 ? (
            <p className="no-warn">● No warnings — this document passed every stage cleanly.</p>
          ) : (
            <div className="warnings">
              {detail.warnings.map((w, i) => (
                <div className={`warn-item ${w.startsWith("Parsing failed") ? "bad" : ""}`} key={i}>{w}</div>
              ))}
            </div>
          )}
        </div>

        {/* Manual operations */}
        <div className="panel full">
          <div className="panel-head">Manual operations</div>
          <div className="ops">
            <button type="button" className="op-btn" disabled title="Available in a future phase">Re-parse</button>
            <button type="button" className="op-btn" disabled title="Available in a future phase">Re-chunk</button>
            <button type="button" className="op-btn" disabled title="Available in a future phase">Re-embed</button>
            <span className="op-note">Prepared for a future phase — actions are disabled.</span>
          </div>
        </div>

        {/* Raw manifest */}
        <div className="panel full">
          <div className="panel-head">Manifest (raw)</div>
          <pre className="raw">{JSON.stringify(detail.manifest, null, 2)}</pre>
        </div>
      </div>
    </main>
  );
}

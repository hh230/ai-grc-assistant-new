import { OverviewCards } from "@/components/OverviewCards";
import { DocumentsExplorer } from "@/components/DocumentsExplorer";
import { PipelineHistory } from "@/components/PipelineHistory";
import {
  loadAllManifests,
  loadEmbeddingIndex,
  loadEmbeddingManifest,
} from "@/lib/services/knowledgeRepository";
import {
  buildDocumentRows,
  buildFilterOptions,
  buildOverview,
} from "@/lib/services/libraryService";
import { buildPipelineHistory } from "@/lib/services/pipelineHistoryService";

// Always render on request: the page reflects whatever the generated artifacts currently say.
export const dynamic = "force-dynamic";

export default async function KnowledgeCenterPage() {
  const [manifests, embeddingIndex, embeddingManifest] = await Promise.all([
    loadAllManifests(),
    loadEmbeddingIndex(),
    loadEmbeddingManifest(),
  ]);

  const overview = buildOverview(manifests, embeddingIndex, embeddingManifest);
  const rows = buildDocumentRows(manifests, embeddingIndex);
  const options = buildFilterOptions(rows);
  const history = buildPipelineHistory(manifests, embeddingManifest);

  return (
    <main className="shell">
      <div className="topbar">
        <div className="brand">
          <span className="eyebrow">Rasheed V2 — Knowledge Pipeline</span>
          <h1>Knowledge Center</h1>
        </div>
        <span className="crumb">Read-only dashboard · reads generated manifests &amp; artifacts</span>
      </div>

      {manifests.length === 0 ? (
        <p className="section-note">
          No knowledge artifacts found. Run the import pipeline
          (<span className="mono">python -m knowledge_importer.cli</span>) and the embedding
          phase to populate the Knowledge Center.
        </p>
      ) : (
        <>
          <section className="section">
            <div className="section-head">
              <h2>Library overview</h2>
            </div>
            <OverviewCards overview={overview} />
          </section>

          <section className="section">
            <div className="section-head">
              <h2>Documents</h2>
              <span className="meta">click a document for full pipeline detail</span>
            </div>
            <DocumentsExplorer rows={rows} options={options} />
          </section>

          <section className="section">
            <div className="section-head">
              <h2>Pipeline history</h2>
            </div>
            <p className="section-note">
              Reconstructed from the generated artifacts. The import (parse + chunk) run is
              derived from the document manifests; the embedding run comes from the embedding
              manifest. A persistent multi-run log is a future addition.
            </p>
            <PipelineHistory runs={history} />
          </section>
        </>
      )}
    </main>
  );
}

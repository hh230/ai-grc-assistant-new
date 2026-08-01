import { useState } from "react";

import type { DocumentItem } from "../api/client";
import { UPLOAD_KINDS, type EvidenceCollectionVM } from "./collections";
import { useKnowledge } from "./useKnowledge";

// Knowledge — "What evidence do we have?" The view answers it in the product's language: Evidence
// Collections first (Policies (12) · …), each opened to reveal its documents. Never a flat file list;
// the collection is the unit. No Trust Bar (this is a management view, not a decision). The file is
// hidden behind its evidence role — no folders, no formats-as-the-model.
export function KnowledgeView() {
  const { state, upload, reload } = useKnowledge();
  const [openKind, setOpenKind] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  return (
    <section className="knowledge">
      <header className="knowledge__header">
        <div className="knowledge__titles">
          <h1>Evidence</h1>
          <p className="knowledge__subtitle">What evidence do we have?</p>
        </div>
        {/* #2 — the primary action stays a clear, prominent button; clicking it opens a focused
            panel below (not a thin inline strip in the header). */}
        <button className="knowledge__cta" onClick={() => setUploadOpen((v) => !v)}>
          + Upload evidence
        </button>
      </header>

      {uploadOpen && <UploadForm onUpload={upload} onClose={() => setUploadOpen(false)} />}

      {state.kind === "loading" && <p className="knowledge__note">Loading evidence…</p>}

      {state.kind === "error" && (
        <p className="knowledge__note knowledge__note--error">
          Couldn’t load evidence: {state.message} <button onClick={reload}>Retry</button>
        </p>
      )}

      {state.kind === "ready" &&
        (state.total === 0 ? (
          <EmptyState />
        ) : openKind === null ? (
          <Collections collections={state.collections} onOpen={setOpenKind} />
        ) : (
          <CollectionDetail
            collection={state.collections.find((c) => c.kind === openKind)}
            onBack={() => setOpenKind(null)}
          />
        ))}
    </section>
  );
}

function EmptyState() {
  return (
    <div className="knowledge__empty">
      <p className="knowledge__empty-title">No evidence yet</p>
      <p className="knowledge__empty-hint">
        Upload your policies, procedures, standards, and reports — missions work on your own evidence.
      </p>
    </div>
  );
}

function Collections({
  collections,
  onOpen,
}: {
  collections: EvidenceCollectionVM[];
  onOpen: (kind: string) => void;
}) {
  // The overview: one card per collection, the count front and centre — the collection is the unit.
  return (
    <ul className="collections">
      {collections.map((collection) => (
        <li key={collection.kind}>
          <button className="collection" onClick={() => onOpen(collection.kind)}>
            <span className="collection__count">{collection.count}</span>
            <span className="collection__label">{collection.label}</span>
            <span className="collection__hint">
              {collection.count === 1 ? "1 document" : `${collection.count} documents`} →
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function CollectionDetail({
  collection,
  onBack,
}: {
  collection: EvidenceCollectionVM | undefined;
  onBack: () => void;
}) {
  if (collection === undefined) {
    // The open collection emptied out (e.g. a filter changed) — fall back to the overview.
    return (
      <p className="knowledge__note">
        <button onClick={onBack}>← All evidence</button>
      </p>
    );
  }
  return (
    <div className="collection-detail">
      <div className="collection-detail__bar">
        <button className="collection-detail__back" onClick={onBack}>
          ← All evidence
        </button>
        <h2 className="collection-detail__title">
          {collection.label} <span className="collection-detail__count">{collection.count}</span>
        </h2>
      </div>
      <ul className="documents">
        {collection.documents.map((doc) => (
          <DocumentRow key={doc.id} doc={doc} />
        ))}
      </ul>
    </div>
  );
}

function DocumentRow({ doc }: { doc: DocumentItem }) {
  return (
    <li className="document">
      <span className="document__name">{doc.filename}</span>
      <span className="document__meta">
        <span className="document__size">{formatSize(doc.size)}</span>
        <span className="document__time">{timeAgo(doc.uploaded_at)}</span>
        <StatusPill status={doc.status} />
      </span>
    </li>
  );
}

function StatusPill({ status }: { status: string }) {
  const text = status === "ready" ? "Ready" : status === "ingesting" ? "Ingesting…" : "Failed";
  return <span className={`status status--${status}`}>{text}</span>;
}

// A focused upload panel (not a thin header strip): a titled card with **labeled** fields — Evidence
// type (the Collection the file joins) and File — so the primary action reads clearly. "Unclassified"
// is not offer­able here (#3): it is the system's bin, never an author's choice (UPLOAD_KINDS).
function UploadForm({
  onUpload,
  onClose,
}: {
  onUpload: (kind: string, file: File) => Promise<void>;
  onClose: () => void;
}) {
  const [kind, setKind] = useState(UPLOAD_KINDS[0].kind);
  const [file, setFile] = useState<File | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (file === null) return;
    setBusy(true);
    setError(null);
    try {
      await onUpload(kind, file);
      setFile(null);
      setInputKey((k) => k + 1); // reset the native file input
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="upload-panel">
      <h2 className="upload-panel__title">Upload evidence</h2>
      <div className="upload-panel__fields">
        <label className="upload-panel__field">
          <span className="upload-panel__label">Evidence type</span>
          <select value={kind} onChange={(e) => setKind(e.target.value)} disabled={busy}>
            {UPLOAD_KINDS.map((def) => (
              <option key={def.kind} value={def.kind}>
                {def.label}
              </option>
            ))}
          </select>
        </label>
        <label className="upload-panel__field">
          <span className="upload-panel__label">File</span>
          <input
            key={inputKey}
            type="file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            disabled={busy}
          />
        </label>
      </div>
      <div className="upload-panel__actions">
        <button className="upload__submit" onClick={submit} disabled={busy || file === null}>
          {busy ? "Uploading…" : "Upload"}
        </button>
        <button className="upload__cancel" onClick={onClose} disabled={busy}>
          Cancel
        </button>
      </div>
      {error !== null && <p className="upload__error">{error}</p>}
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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

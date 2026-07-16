"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { filterDocuments } from "@/lib/services/libraryService";
import { formatDateTime, formatInt } from "@/lib/format";
import type { DocumentFilters, DocumentRow, FilterOptions } from "@/lib/types/view";

const EMPTY: DocumentFilters = {
  category: null,
  documentProfile: null,
  status: null,
  parser: null,
  language: null,
  search: null,
};

function Flag({ on, warn }: { on: boolean; warn?: boolean }) {
  if (on && warn) return <span className="flag warn" title="Completed with warnings">▲</span>;
  if (on) return <span className="flag ok" title="Yes">●</span>;
  return <span className="flag no" title="No">○</span>;
}

/**
 * The one interactive surface. All logic — filtering + search — is delegated to the pure
 * `filterDocuments` service; this component only holds the current filter selection and
 * renders. No aggregation or business rules live here.
 */
export function DocumentsExplorer({ rows, options }: { rows: DocumentRow[]; options: FilterOptions }) {
  const [filters, setFilters] = useState<DocumentFilters>(EMPTY);

  const visible = useMemo(() => filterDocuments(rows, filters), [rows, filters]);

  function update<K extends keyof DocumentFilters>(key: K, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value === "" ? null : value }));
  }

  const isFiltered = Object.values(filters).some((v) => v !== null);

  return (
    <div>
      <div className="controls">
        <input
          type="search"
          placeholder="Search name, filename, or category…"
          value={filters.search ?? ""}
          onChange={(e) => update("search", e.target.value)}
          aria-label="Search documents"
        />
        <select value={filters.category ?? ""} onChange={(e) => update("category", e.target.value)} aria-label="Filter by category">
          <option value="">All categories</option>
          {options.categories.map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
        <select value={filters.documentProfile ?? ""} onChange={(e) => update("documentProfile", e.target.value)} aria-label="Filter by document profile">
          <option value="">All profiles</option>
          {options.documentProfiles.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <select value={filters.status ?? ""} onChange={(e) => update("status", e.target.value)} aria-label="Filter by status">
          <option value="">All statuses</option>
          {options.statuses.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select value={filters.parser ?? ""} onChange={(e) => update("parser", e.target.value)} aria-label="Filter by parser">
          <option value="">All parsers</option>
          {options.parsers.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <select value={filters.language ?? ""} onChange={(e) => update("language", e.target.value)} aria-label="Filter by language">
          <option value="">All languages</option>
          {options.languages.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
        {isFiltered && (
          <button type="button" className="reset" onClick={() => setFilters(EMPTY)}>Reset</button>
        )}
        <span className="result-count">{formatInt(visible.length)} of {formatInt(rows.length)}</span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Document</th>
              <th>Category</th>
              <th>Profile</th>
              <th>Parser</th>
              <th>Parsed</th>
              <th>Chunked</th>
              <th>Embedded</th>
              <th className="num">Pages</th>
              <th className="num">Chunks</th>
              <th className="num">Embeddings</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.documentId}>
                <td>
                  <Link className="doc-name" href={`/documents/${encodeURIComponent(row.documentId)}`}>{row.name}</Link>
                </td>
                <td><span className="pill">{row.category}</span></td>
                <td className="mono">{row.documentProfile ?? <span className="badge flat">unmapped</span>}</td>
                <td className="mono muted">{row.parserUsed ?? "—"}</td>
                <td><Flag on={row.parsed} /></td>
                <td><Flag on={row.chunked} warn={row.chunked && row.hasWarnings} /></td>
                <td><Flag on={row.embedded} /></td>
                <td className="num mono">{formatInt(row.pages)}</td>
                <td className="num mono">{formatInt(row.chunks)}</td>
                <td className="num mono">{formatInt(row.embeddings)}</td>
                <td className="mono muted">{formatDateTime(row.lastUpdated)}</td>
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={11} style={{ textAlign: "center", padding: "28px", color: "var(--ink-faint)" }}>
                  No documents match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

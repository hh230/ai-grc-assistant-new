/**
 * PostgreSQL connection pool behind a port — the shared seam every repository adapter in
 * this app connects through (documents, evidence, analyses, document chunks/pgvector,
 * conversations, policies, risks). One pool per process; swapping the database (host,
 * credentials, pooler) never touches a repository. Node-only.
 */

import { Pool } from "pg";

let pool: Pool | null = null;

// Strips whitespace/newlines and a single pair of wrapping quotes — the most common way a
// connection string gets mangled when pasted into a dashboard's env var UI (e.g.
// `"postgresql://...")` instead of `postgresql://...`). An unstripped leading quote isn't a
// valid URL scheme, so `pg`'s parser silently falls back to its PGHOST/PGPORT defaults
// (localhost:5432) instead of failing — which is what actually happened in production.
function sanitizeConnectionString(raw: string): string {
  const trimmed = raw.trim();
  const unquoted =
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
      ? trimmed.slice(1, -1)
      : trimmed;
  return unquoted.trim();
}

export function getPool(): Pool {
  if (!pool) {
    const rawConnectionString = process.env.DATABASE_URL;
    if (!rawConnectionString) {
      throw new Error("DATABASE_URL is not set.");
    }
    const connectionString = sanitizeConnectionString(rawConnectionString);

    let host: string;
    try {
      host = new URL(connectionString).hostname;
    } catch {
      throw new Error(
        "DATABASE_URL is not a valid connection string (check for stray quotes or line breaks).",
      );
    }

    const isLocal = host === "localhost" || host === "127.0.0.1";
    pool = new Pool({
      connectionString,
      // Managed providers (Supabase, RDS, etc.) require TLS; local dev Postgres doesn't
      // present a trusted cert, so only enable it for non-local hosts.
      ssl: isLocal ? undefined : { rejectUnauthorized: false },
    });
  }
  return pool;
}

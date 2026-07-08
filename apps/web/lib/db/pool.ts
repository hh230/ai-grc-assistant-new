/**
 * PostgreSQL connection pool behind a port — the shared seam every repository adapter in
 * this app connects through (documents, evidence, analyses, document chunks/pgvector,
 * conversations, policies, risks). One pool per process; swapping the database (host,
 * credentials, pooler) never touches a repository. Node-only.
 *
 * Sized for a serverless PgBouncer/Supavisor *transaction*-mode pooler (port 6543), not a
 * direct connection or a *session*-mode pooler (port 5432): session mode dedicates one
 * upstream Postgres backend per client for the client's entire TCP lifetime, so it caps out
 * fast under Vercel's many concurrent/short-lived function instances (observed in production:
 * `EMAXCONNSESSION ... pool_size: 15`) and an abruptly-killed client leaves that backend
 * orphaned until TCP timeout. Transaction mode only holds a backend for the duration of an
 * active transaction — idle time and unclean client death don't pin a connection — so `max`
 * here is deliberately small (this app doesn't need many *concurrent* backends per instance,
 * just to never sit on idle ones) and `idleTimeoutMillis` is short so a warm serverless
 * instance releases connections quickly instead of accumulating them across invocations.
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
      // Small per-instance ceiling: with a transaction-mode pooler in front, many serverless
      // instances can each hold a few connections without approaching Postgres's real backend
      // limit — the failure mode we're avoiding is instances *accumulating* idle connections,
      // not lacking concurrency within one instance.
      max: Number(process.env.DATABASE_POOL_MAX ?? 5),
      // Release an idle connection back to the pooler quickly instead of holding it open
      // for the lifetime of a warm (but momentarily idle) serverless instance.
      idleTimeoutMillis: 10_000,
      // Fail fast if the pooler itself is saturated rather than hanging the request.
      connectionTimeoutMillis: 10_000,
      // Let the process exit if this pool is the only open handle — relevant for the
      // one-off scripts (migrations, admin bootstrap) that also import this module.
      allowExitOnIdle: true,
    });
    // A backend that the pooler recycles mid-use (e.g. a transaction-mode connection
    // handed to a different session) surfaces as an `error` on the idle client, which
    // otherwise crashes the process — same class of fix as any long-lived pg.Pool.
    pool.on("error", (error) => {
      console.error("Unexpected error on idle Postgres client", error);
    });
  }
  return pool;
}

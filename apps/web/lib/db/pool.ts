/**
 * PostgreSQL connection pool behind a port — the shared seam every repository adapter in
 * this app connects through (documents, evidence, analyses, document chunks/pgvector,
 * conversations, policies, risks). One pool per process; swapping the database (host,
 * credentials, pooler) never touches a repository. Node-only.
 */

import { Pool } from "pg";

let pool: Pool | null = null;

export function getPool(): Pool {
  if (!pool) {
    const connectionString = process.env.DATABASE_URL;
    if (!connectionString) {
      throw new Error("DATABASE_URL is not set.");
    }
    pool = new Pool({ connectionString });
  }
  return pool;
}

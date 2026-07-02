#!/usr/bin/env node
/**
 * Applies every SQL file in lib/db/migrations, in filename order, exactly once, tracked in
 * a `schema_migrations` table. Idempotent — safe to re-run. Node-only, standalone (does not
 * go through Next.js), so it loads .env.local/.env itself.
 */

import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import pg from "pg";

const appRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
dotenv.config({ path: path.join(appRoot, ".env.local") });
dotenv.config({ path: path.join(appRoot, "..", "..", ".env") });

const migrationsDir = path.join(appRoot, "lib", "db", "migrations");

async function main() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set (checked apps/web/.env.local and root .env).");
  }

  const client = new pg.Client({ connectionString });
  await client.connect();
  try {
    await client.query(
      `CREATE TABLE IF NOT EXISTS schema_migrations (
         filename text PRIMARY KEY,
         applied_at timestamptz NOT NULL DEFAULT now()
       )`,
    );

    const { rows: applied } = await client.query("SELECT filename FROM schema_migrations");
    const appliedSet = new Set(applied.map((r) => r.filename));

    const files = readdirSync(migrationsDir)
      .filter((f) => f.endsWith(".sql"))
      .sort();

    for (const file of files) {
      if (appliedSet.has(file)) {
        console.log(`skip  ${file} (already applied)`);
        continue;
      }
      const sql = readFileSync(path.join(migrationsDir, file), "utf8");
      console.log(`apply ${file}`);
      await client.query("BEGIN");
      try {
        await client.query(sql);
        await client.query("INSERT INTO schema_migrations (filename) VALUES ($1)", [file]);
        await client.query("COMMIT");
      } catch (error) {
        await client.query("ROLLBACK");
        throw new Error(`Migration ${file} failed: ${error instanceof Error ? error.message : error}`);
      }
    }
    console.log("Migrations up to date.");
  } finally {
    await client.end();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

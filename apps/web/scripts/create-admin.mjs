#!/usr/bin/env node
/**
 * Bootstraps the very first platform account (KI-P9, ADR-0034). With demo login removed and
 * no public signup, this is the only way to get a first `owner` into the system — from there,
 * that owner reviews access requests and everyone else arrives through the invite flow.
 * Idempotent (re-running with the same email updates nothing and reports the existing
 * account); standalone (does not go through Next.js), so it loads .env.local/.env itself.
 *
 * Usage:
 *   node scripts/create-admin.mjs --email you@company.com --password 'Secret123!' \
 *     --name "Jane Doe" --org "Acme Platform Team"
 * or via env vars: ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME, ADMIN_ORG_NAME.
 */

import { randomBytes, randomUUID, scrypt as scryptCallback } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import pg from "pg";

const appRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
dotenv.config({ path: path.join(appRoot, ".env.local") });
dotenv.config({ path: path.join(appRoot, "..", "..", ".env") });

const KEYLEN = 64;
const PARAMS = { N: 16384, r: 8, p: 1 };

function scrypt(password, salt, keylen, params) {
  return new Promise((resolve, reject) => {
    scryptCallback(password, salt, keylen, params, (error, derivedKey) => {
      if (error) reject(error);
      else resolve(derivedKey);
    });
  });
}

// Mirrors lib/auth/password.ts's hashPassword exactly (`scrypt$N$r$p$saltHex$hashHex`) — this
// script cannot import that TS module directly, so the format is duplicated deliberately.
async function hashPassword(password) {
  const salt = randomBytes(16);
  const derived = await scrypt(password, salt, KEYLEN, PARAMS);
  return `scrypt$${PARAMS.N}$${PARAMS.r}$${PARAMS.p}$${salt.toString("hex")}$${derived.toString("hex")}`;
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith("--")) continue;
    const key = arg.slice(2);
    const value = argv[i + 1];
    args[key] = value;
    i += 1;
  }
  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const email = (args.email ?? process.env.ADMIN_EMAIL ?? "").trim().toLowerCase();
  const password = args.password ?? process.env.ADMIN_PASSWORD ?? "";
  const name = args.name ?? process.env.ADMIN_NAME ?? "Platform Owner";
  const orgName = args.org ?? process.env.ADMIN_ORG_NAME ?? "Platform Administration";
  const orgType = args["org-type"] ?? process.env.ADMIN_ORG_TYPE ?? "Enterprise";
  const industry = args.industry ?? process.env.ADMIN_INDUSTRY ?? "Platform";

  if (!email || !email.includes("@")) {
    throw new Error("A valid --email (or ADMIN_EMAIL) is required.");
  }
  if (!password || password.length < 8) {
    throw new Error("A --password (or ADMIN_PASSWORD) of at least 8 characters is required.");
  }

  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set (checked apps/web/.env.local and root .env).");
  }

  const client = new pg.Client({ connectionString });
  await client.connect();
  try {
    const { rows: existing } = await client.query(
      "SELECT id FROM users WHERE lower(email) = lower($1)",
      [email],
    );
    if (existing.length > 0) {
      console.log(`User ${email} already exists (id=${existing[0].id}) — nothing to do.`);
      return;
    }

    const userId = randomUUID();
    const orgId = randomUUID();
    const passwordHash = await hashPassword(password);
    const now = new Date().toISOString();

    await client.query("BEGIN");
    try {
      await client.query(
        `INSERT INTO users (id, email, name, password_hash, created_at) VALUES ($1, $2, $3, $4, $5)`,
        [userId, email, name, passwordHash, now],
      );
      await client.query(
        `INSERT INTO organizations (id, name, org_type, industry, created_by_user_id, created_at)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [orgId, orgName, orgType, industry, userId, now],
      );
      await client.query(
        `INSERT INTO user_organizations (user_id, organization_id, role) VALUES ($1, $2, 'owner')`,
        [userId, orgId],
      );
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    }

    console.log(`Created platform owner ${email} (user=${userId}, org=${orgId} "${orgName}").`);
  } finally {
    await client.end();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

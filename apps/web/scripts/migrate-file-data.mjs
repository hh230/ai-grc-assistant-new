#!/usr/bin/env node
/**
 * One-off data migration: loads the legacy file-based JSON indexes + per-document vector
 * files under STORAGE_DIR (default "<app>/.data") into PostgreSQL. Idempotent — every
 * insert is `ON CONFLICT DO NOTHING`, so re-running never clobbers rows the app has since
 * written or modified through the Postgres-backed repositories. Node-only, standalone.
 */

import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import pg from "pg";

const appRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
dotenv.config({ path: path.join(appRoot, ".env.local") });
dotenv.config({ path: path.join(appRoot, "..", "..", ".env") });

const storageRoot = process.env.STORAGE_DIR ?? path.join(appRoot, ".data");

function readJson(file) {
  const target = path.join(storageRoot, file);
  if (!existsSync(target)) return [];
  const parsed = JSON.parse(readFileSync(target, "utf8"));
  return Array.isArray(parsed) ? parsed : [];
}

function toVectorLiteral(vector) {
  return `[${vector.join(",")}]`;
}

async function migrateDocuments(client) {
  const records = readJson("documents.json");
  for (const r of records) {
    await client.query(
      `INSERT INTO documents (
         id, tenant_id, uploaded_by_user_id, uploaded_by_name, file_name, content_type, kind,
         size_bytes, checksum_sha256, storage_key, status, status_detail, created_at, updated_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
       ON CONFLICT (id) DO NOTHING`,
      [
        r.id,
        r.tenantId,
        r.uploadedByUserId,
        r.uploadedByName,
        r.fileName,
        r.contentType,
        r.kind,
        r.sizeBytes,
        r.checksumSha256,
        r.storageKey,
        r.status,
        r.statusDetail ?? null,
        r.createdAt,
        r.updatedAt,
      ],
    );
  }
  console.log(`documents: ${records.length} row(s) migrated (or already present)`);
}

async function migrateEvidence(client) {
  const records = readJson("evidence.json");
  for (const e of records) {
    await client.query(
      `INSERT INTO evidence (
         id, tenant_id, title, description, tags, control_ids, current_version_id,
         created_by_user_id, created_by_name, created_at, updated_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
       ON CONFLICT (id) DO NOTHING`,
      [
        e.id,
        e.tenantId,
        e.title,
        e.description ?? null,
        JSON.stringify(e.tags ?? []),
        JSON.stringify(e.controlIds ?? []),
        e.currentVersionId,
        e.createdByUserId,
        e.createdByName,
        e.createdAt,
        e.updatedAt,
      ],
    );
    for (const v of e.versions ?? []) {
      await client.query(
        `INSERT INTO evidence_versions (
           id, evidence_id, tenant_id, version_number, file_name, content_type, kind, size_bytes,
           checksum_sha256, storage_key, note, uploaded_by_user_id, uploaded_by_name, created_at
         ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
         ON CONFLICT (id) DO NOTHING`,
        [
          v.id,
          e.id,
          e.tenantId,
          v.versionNumber,
          v.fileName,
          v.contentType,
          v.kind,
          v.sizeBytes,
          v.checksumSha256,
          v.storageKey,
          v.note ?? null,
          v.uploadedByUserId,
          v.uploadedByName,
          v.createdAt,
        ],
      );
    }
  }
  console.log(`evidence: ${records.length} row(s) migrated (or already present)`);
}

async function migrateAnalyses(client) {
  const records = readJson("analyses.json");
  for (const r of records) {
    await client.query(
      `INSERT INTO analyses (
         id, document_id, tenant_id, file_name, status, error, char_count, page_count,
         chunk_count, embedding_provider, chat_provider, summary, findings, frameworks,
         key_terms, requested_by_user_id, requested_by_name, created_at, updated_at,
         completed_at, duration_ms
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
       ON CONFLICT (id) DO NOTHING`,
      [
        r.id,
        r.documentId,
        r.tenantId,
        r.fileName,
        r.status,
        r.error ?? null,
        r.charCount ?? 0,
        r.pageCount ?? null,
        r.chunkCount ?? 0,
        r.embeddingProvider ?? null,
        r.chatProvider ?? null,
        r.summary ?? null,
        JSON.stringify(r.findings ?? []),
        JSON.stringify(r.frameworks ?? []),
        JSON.stringify(r.keyTerms ?? []),
        r.requestedByUserId,
        r.requestedByName,
        r.createdAt,
        r.updatedAt,
        r.completedAt ?? null,
        r.durationMs ?? null,
      ],
    );
  }
  console.log(`analyses: ${records.length} row(s) migrated (or already present)`);
}

async function migrateConversations(client) {
  const records = readJson("conversations.json");
  let messageCount = 0;
  for (const c of records) {
    await client.query(
      `INSERT INTO conversations (id, tenant_id, user_id, title, created_at, updated_at)
       VALUES ($1,$2,$3,$4,$5,$6)
       ON CONFLICT (id) DO NOTHING`,
      [c.id, c.tenantId, c.userId, c.title, c.createdAt, c.updatedAt],
    );
    for (const m of c.messages ?? []) {
      await client.query(
        `INSERT INTO chat_messages (id, conversation_id, role, content, citations, created_at)
         VALUES ($1,$2,$3,$4,$5,$6)
         ON CONFLICT (id) DO NOTHING`,
        [m.id, c.id, m.role, m.content, m.citations ? JSON.stringify(m.citations) : null, m.createdAt],
      );
      messageCount += 1;
    }
  }
  console.log(
    `conversations: ${records.length} row(s), ${messageCount} message(s) migrated (or already present)`,
  );
}

async function migratePolicies(client) {
  const records = readJson("policies.json");
  for (const p of records) {
    await client.query(
      `INSERT INTO policies (
         id, tenant_id, title, summary, body, status, owner_name, control_ids,
         created_by_user_id, created_by_name, created_at, updated_at, approved_by_name, approved_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
       ON CONFLICT (id) DO NOTHING`,
      [
        p.id,
        p.tenantId,
        p.title,
        p.summary ?? null,
        p.body ?? null,
        p.status,
        p.ownerName,
        JSON.stringify(p.controlIds ?? []),
        p.createdByUserId,
        p.createdByName,
        p.createdAt,
        p.updatedAt,
        p.approvedByName ?? null,
        p.approvedAt ?? null,
      ],
    );
  }
  console.log(`policies: ${records.length} row(s) migrated (or already present)`);
}

async function migrateRisks(client) {
  const records = readJson("risks.json");
  for (const r of records) {
    await client.query(
      `INSERT INTO risks (
         id, tenant_id, title, description, category, likelihood, impact, status, owner_name,
         control_ids, mitigation_plan, residual_likelihood, residual_impact,
         created_by_user_id, created_by_name, created_at, updated_at, accepted_by_name, accepted_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
       ON CONFLICT (id) DO NOTHING`,
      [
        r.id,
        r.tenantId,
        r.title,
        r.description ?? null,
        r.category,
        r.likelihood,
        r.impact,
        r.status,
        r.ownerName,
        JSON.stringify(r.controlIds ?? []),
        r.mitigationPlan ?? null,
        r.residualLikelihood ?? null,
        r.residualImpact ?? null,
        r.createdByUserId,
        r.createdByName,
        r.createdAt,
        r.updatedAt,
        r.acceptedByName ?? null,
        r.acceptedAt ?? null,
      ],
    );
  }
  console.log(`risks: ${records.length} row(s) migrated (or already present)`);
}

async function migrateVectors(client) {
  const vectorsDir = path.join(storageRoot, "vectors");
  if (!existsSync(vectorsDir)) {
    console.log("document_chunks: no vectors/ directory found, skipping");
    return;
  }
  let fileCount = 0;
  let chunkCount = 0;
  for (const tenantId of readdirSync(vectorsDir)) {
    const tenantDir = path.join(vectorsDir, tenantId);
    for (const name of readdirSync(tenantDir)) {
      if (!name.endsWith(".json")) continue;
      const doc = JSON.parse(readFileSync(path.join(tenantDir, name), "utf8"));
      fileCount += 1;
      for (const chunk of doc.chunks ?? []) {
        await client.query(
          `INSERT INTO document_chunks (
             tenant_id, document_id, chunk_index, file_name, embedding_provider, chunk_text,
             char_start, char_end, embedding
           ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::vector)
           ON CONFLICT (document_id, chunk_index) DO NOTHING`,
          [
            doc.tenantId,
            doc.documentId,
            chunk.index,
            doc.fileName,
            doc.embeddingProvider,
            chunk.text,
            chunk.charStart,
            chunk.charEnd,
            toVectorLiteral(chunk.embedding),
          ],
        );
        chunkCount += 1;
      }
    }
  }
  console.log(
    `document_chunks: ${fileCount} document(s), ${chunkCount} chunk(s) migrated (or already present)`,
  );
}

async function main() {
  const connectionString = process.env.DATABASE_URL;
  if (!connectionString) {
    throw new Error("DATABASE_URL is not set (checked apps/web/.env.local and root .env).");
  }
  const client = new pg.Client({ connectionString });
  await client.connect();
  try {
    await migrateDocuments(client);
    await migrateEvidence(client);
    await migrateAnalyses(client);
    await migrateConversations(client);
    await migratePolicies(client);
    await migrateRisks(client);
    await migrateVectors(client);
    console.log("Data migration complete.");
  } finally {
    await client.end();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

/**
 * Evidence repository behind a port, backed by PostgreSQL (`evidence` + `evidence_versions`
 * tables). Tenant-scoped (CLAUDE.md §20, default deny). Node-only.
 */

import type { Pool, PoolClient } from "pg";
import { getPool } from "@/lib/db/pool";
import type { Evidence, EvidenceVersion } from "./types";

export interface EvidenceRepository {
  list(tenantId: string): Promise<Evidence[]>;
  get(tenantId: string, id: string): Promise<Evidence | null>;
  create(evidence: Evidence): Promise<Evidence>;
  update(
    tenantId: string,
    id: string,
    mutate: (evidence: Evidence) => Evidence,
  ): Promise<Evidence | null>;
  delete(tenantId: string, id: string): Promise<Evidence | null>;
}

interface EvidenceRow {
  id: string;
  tenant_id: string;
  title: string;
  description: string | null;
  tags: string[];
  control_ids: string[];
  current_version_id: string;
  created_by_user_id: string;
  created_by_name: string;
  created_at: Date;
  updated_at: Date;
}

interface EvidenceVersionRow {
  id: string;
  evidence_id: string;
  version_number: number;
  file_name: string;
  content_type: string;
  kind: string;
  size_bytes: string;
  checksum_sha256: string;
  storage_key: string;
  note: string | null;
  uploaded_by_user_id: string;
  uploaded_by_name: string;
  created_at: Date;
}

function toVersion(row: EvidenceVersionRow): EvidenceVersion {
  return {
    id: row.id,
    versionNumber: row.version_number,
    fileName: row.file_name,
    contentType: row.content_type,
    kind: row.kind,
    sizeBytes: Number(row.size_bytes),
    checksumSha256: row.checksum_sha256,
    storageKey: row.storage_key,
    note: row.note ?? undefined,
    uploadedByUserId: row.uploaded_by_user_id,
    uploadedByName: row.uploaded_by_name,
    createdAt: row.created_at.toISOString(),
  };
}

function toEvidence(row: EvidenceRow, versions: EvidenceVersion[]): Evidence {
  return {
    id: row.id,
    tenantId: row.tenant_id,
    title: row.title,
    description: row.description ?? undefined,
    tags: row.tags,
    controlIds: row.control_ids,
    versions,
    currentVersionId: row.current_version_id,
    createdByUserId: row.created_by_user_id,
    createdByName: row.created_by_name,
    createdAt: row.created_at.toISOString(),
    updatedAt: row.updated_at.toISOString(),
  };
}

async function fetchVersions(
  client: Pool | PoolClient,
  evidenceIds: string[],
): Promise<Map<string, EvidenceVersion[]>> {
  const byEvidence = new Map<string, EvidenceVersion[]>();
  if (evidenceIds.length === 0) return byEvidence;
  const { rows } = await client.query<EvidenceVersionRow>(
    `SELECT * FROM evidence_versions WHERE evidence_id = ANY($1) ORDER BY version_number ASC`,
    [evidenceIds],
  );
  for (const row of rows) {
    const list = byEvidence.get(row.evidence_id) ?? [];
    list.push(toVersion(row));
    byEvidence.set(row.evidence_id, list);
  }
  return byEvidence;
}

async function insertVersion(
  client: PoolClient,
  evidenceId: string,
  tenantId: string,
  version: EvidenceVersion,
): Promise<void> {
  await client.query(
    `INSERT INTO evidence_versions (
       id, evidence_id, tenant_id, version_number, file_name, content_type, kind, size_bytes,
       checksum_sha256, storage_key, note, uploaded_by_user_id, uploaded_by_name, created_at
     ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
     ON CONFLICT (id) DO NOTHING`,
    [
      version.id,
      evidenceId,
      tenantId,
      version.versionNumber,
      version.fileName,
      version.contentType,
      version.kind,
      version.sizeBytes,
      version.checksumSha256,
      version.storageKey,
      version.note ?? null,
      version.uploadedByUserId,
      version.uploadedByName,
      version.createdAt,
    ],
  );
}

class PostgresEvidenceRepository implements EvidenceRepository {
  async list(tenantId: string): Promise<Evidence[]> {
    const pool = getPool();
    const { rows } = await pool.query<EvidenceRow>(
      `SELECT * FROM evidence WHERE tenant_id = $1 ORDER BY updated_at DESC`,
      [tenantId],
    );
    const versionsByEvidence = await fetchVersions(
      pool,
      rows.map((r) => r.id),
    );
    return rows.map((row) => toEvidence(row, versionsByEvidence.get(row.id) ?? []));
  }

  async get(tenantId: string, id: string): Promise<Evidence | null> {
    const pool = getPool();
    const { rows } = await pool.query<EvidenceRow>(
      `SELECT * FROM evidence WHERE tenant_id = $1 AND id = $2`,
      [tenantId, id],
    );
    const row = rows[0];
    if (!row) return null;
    const versionsByEvidence = await fetchVersions(pool, [row.id]);
    return toEvidence(row, versionsByEvidence.get(row.id) ?? []);
  }

  async create(evidence: Evidence): Promise<Evidence> {
    const client = await getPool().connect();
    try {
      await client.query("BEGIN");
      await client.query(
        `INSERT INTO evidence (
           id, tenant_id, title, description, tags, control_ids, current_version_id,
           created_by_user_id, created_by_name, created_at, updated_at
         ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)`,
        [
          evidence.id,
          evidence.tenantId,
          evidence.title,
          evidence.description ?? null,
          JSON.stringify(evidence.tags),
          JSON.stringify(evidence.controlIds),
          evidence.currentVersionId,
          evidence.createdByUserId,
          evidence.createdByName,
          evidence.createdAt,
          evidence.updatedAt,
        ],
      );
      for (const version of evidence.versions) {
        await insertVersion(client, evidence.id, evidence.tenantId, version);
      }
      await client.query("COMMIT");
      return evidence;
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async update(
    tenantId: string,
    id: string,
    mutate: (evidence: Evidence) => Evidence,
  ): Promise<Evidence | null> {
    const client = await getPool().connect();
    try {
      await client.query("BEGIN");
      const { rows } = await client.query<EvidenceRow>(
        `SELECT * FROM evidence WHERE tenant_id = $1 AND id = $2 FOR UPDATE`,
        [tenantId, id],
      );
      const row = rows[0];
      if (!row) {
        await client.query("ROLLBACK");
        return null;
      }
      const versionsByEvidence = await fetchVersions(client, [row.id]);
      const current = toEvidence(row, versionsByEvidence.get(row.id) ?? []);
      const updated = mutate(current);

      await client.query(
        `UPDATE evidence SET title = $3, description = $4, tags = $5, control_ids = $6,
           current_version_id = $7, updated_at = $8
         WHERE tenant_id = $1 AND id = $2`,
        [
          tenantId,
          id,
          updated.title,
          updated.description ?? null,
          JSON.stringify(updated.tags),
          JSON.stringify(updated.controlIds),
          updated.currentVersionId,
          updated.updatedAt,
        ],
      );
      // Versions are append-only in this app (see addEvidenceVersion) — insert any that are
      // new since the row was loaded; existing ones are left untouched.
      for (const version of updated.versions) {
        await insertVersion(client, id, tenantId, version);
      }
      await client.query("COMMIT");
      return updated;
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async delete(tenantId: string, id: string): Promise<Evidence | null> {
    const client = await getPool().connect();
    try {
      await client.query("BEGIN");
      const { rows } = await client.query<EvidenceRow>(
        `SELECT * FROM evidence WHERE tenant_id = $1 AND id = $2 FOR UPDATE`,
        [tenantId, id],
      );
      const row = rows[0];
      if (!row) {
        await client.query("ROLLBACK");
        return null;
      }
      const versionsByEvidence = await fetchVersions(client, [row.id]);
      const evidence = toEvidence(row, versionsByEvidence.get(row.id) ?? []);
      await client.query(`DELETE FROM evidence WHERE tenant_id = $1 AND id = $2`, [tenantId, id]);
      await client.query("COMMIT");
      return evidence;
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }
}

export const evidenceRepository: EvidenceRepository = new PostgresEvidenceRepository();

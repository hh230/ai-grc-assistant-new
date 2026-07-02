/**
 * Document metadata repository behind a port, backed by PostgreSQL (`documents` table).
 * Swap this adapter for another one without changing callers. Every method is tenant-scoped
 * — a caller can only ever reach its own tenant's records (CLAUDE.md §20, default deny).
 * Node-only.
 */

import { getPool } from "@/lib/db/pool";
import type { DocumentCategory, DocumentRecord, DocumentStatus } from "./types";

export interface DocumentRepository {
  list(tenantId: string): Promise<DocumentRecord[]>;
  get(tenantId: string, id: string): Promise<DocumentRecord | null>;
  /** Upload-time dedupe: find an existing document with the same content hash. */
  findByChecksum(tenantId: string, checksumSha256: string): Promise<DocumentRecord | null>;
  create(record: DocumentRecord): Promise<DocumentRecord>;
  updateStatus(
    tenantId: string,
    id: string,
    status: DocumentStatus,
    detail?: string,
  ): Promise<DocumentRecord | null>;
  delete(tenantId: string, id: string): Promise<boolean>;
}

interface DocumentRow {
  id: string;
  tenant_id: string;
  uploaded_by_user_id: string;
  uploaded_by_name: string;
  file_name: string;
  content_type: string;
  kind: string;
  category: DocumentCategory;
  size_bytes: string;
  checksum_sha256: string;
  storage_key: string;
  status: DocumentStatus;
  status_detail: string | null;
  created_at: Date;
  updated_at: Date;
}

function toRecord(row: DocumentRow): DocumentRecord {
  return {
    id: row.id,
    tenantId: row.tenant_id,
    uploadedByUserId: row.uploaded_by_user_id,
    uploadedByName: row.uploaded_by_name,
    fileName: row.file_name,
    contentType: row.content_type,
    kind: row.kind,
    category: row.category,
    sizeBytes: Number(row.size_bytes),
    checksumSha256: row.checksum_sha256,
    storageKey: row.storage_key,
    status: row.status,
    statusDetail: row.status_detail ?? undefined,
    createdAt: row.created_at.toISOString(),
    updatedAt: row.updated_at.toISOString(),
  };
}

class PostgresDocumentRepository implements DocumentRepository {
  async list(tenantId: string): Promise<DocumentRecord[]> {
    const { rows } = await getPool().query<DocumentRow>(
      `SELECT * FROM documents WHERE tenant_id = $1 ORDER BY created_at DESC`,
      [tenantId],
    );
    return rows.map(toRecord);
  }

  async get(tenantId: string, id: string): Promise<DocumentRecord | null> {
    const { rows } = await getPool().query<DocumentRow>(
      `SELECT * FROM documents WHERE tenant_id = $1 AND id = $2`,
      [tenantId, id],
    );
    return rows[0] ? toRecord(rows[0]) : null;
  }

  async findByChecksum(tenantId: string, checksumSha256: string): Promise<DocumentRecord | null> {
    const { rows } = await getPool().query<DocumentRow>(
      `SELECT * FROM documents WHERE tenant_id = $1 AND checksum_sha256 = $2
       ORDER BY created_at DESC LIMIT 1`,
      [tenantId, checksumSha256],
    );
    return rows[0] ? toRecord(rows[0]) : null;
  }

  async create(record: DocumentRecord): Promise<DocumentRecord> {
    await getPool().query(
      `INSERT INTO documents (
         id, tenant_id, uploaded_by_user_id, uploaded_by_name, file_name, content_type, kind,
         category, size_bytes, checksum_sha256, storage_key, status, status_detail, created_at,
         updated_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)`,
      [
        record.id,
        record.tenantId,
        record.uploadedByUserId,
        record.uploadedByName,
        record.fileName,
        record.contentType,
        record.kind,
        record.category,
        record.sizeBytes,
        record.checksumSha256,
        record.storageKey,
        record.status,
        record.statusDetail ?? null,
        record.createdAt,
        record.updatedAt,
      ],
    );
    return record;
  }

  async updateStatus(
    tenantId: string,
    id: string,
    status: DocumentStatus,
    detail?: string,
  ): Promise<DocumentRecord | null> {
    const { rows } = await getPool().query<DocumentRow>(
      `UPDATE documents SET status = $3, status_detail = $4, updated_at = now()
       WHERE tenant_id = $1 AND id = $2
       RETURNING *`,
      [tenantId, id, status, detail ?? null],
    );
    return rows[0] ? toRecord(rows[0]) : null;
  }

  async delete(tenantId: string, id: string): Promise<boolean> {
    const { rowCount } = await getPool().query(
      `DELETE FROM documents WHERE tenant_id = $1 AND id = $2`,
      [tenantId, id],
    );
    return (rowCount ?? 0) > 0;
  }
}

export const documentRepository: DocumentRepository = new PostgresDocumentRepository();

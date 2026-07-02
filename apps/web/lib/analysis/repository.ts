/**
 * Analysis record repository behind a port, backed by PostgreSQL (`analyses` table).
 * V2-P2.5: every analysis run inserts a new versioned row instead of overwriting the
 * previous one — full history is kept per document. Tenant-scoped (CLAUDE.md §20, default
 * deny). Node-only.
 */

import { getPool } from "@/lib/db/pool";
import type {
  AnalysisFinding,
  AnalysisRecord,
  AnalysisStatus,
  FrameworkCoverage,
  Recommendation,
} from "./types";

export interface AnalysisWithVersionCount extends AnalysisRecord {
  versionCount: number;
}

export interface AnalysisRepository {
  /** Latest version per document, newest-analyzed first — the history page's main list. */
  listLatestPerDocument(tenantId: string): Promise<AnalysisWithVersionCount[]>;
  /** Every version for one document, newest version first. */
  listVersions(tenantId: string, documentId: string): Promise<AnalysisRecord[]>;
  get(tenantId: string, analysisId: string): Promise<AnalysisRecord | null>;
  getLatest(tenantId: string, documentId: string): Promise<AnalysisRecord | null>;
  /** Next version number to assign for a document's next analysis run. */
  nextVersion(tenantId: string, documentId: string): Promise<number>;
  insert(record: AnalysisRecord): Promise<AnalysisRecord>;
  patch(
    tenantId: string,
    analysisId: string,
    patch: Partial<AnalysisRecord>,
  ): Promise<AnalysisRecord | null>;
  delete(tenantId: string, analysisId: string): Promise<void>;
  deleteAllForDocument(tenantId: string, documentId: string): Promise<void>;
}

interface AnalysisRow {
  id: string;
  document_id: string;
  tenant_id: string;
  file_name: string;
  title: string;
  version: number;
  status: AnalysisStatus;
  error: string | null;
  char_count: number;
  page_count: number | null;
  chunk_count: number;
  embedding_provider: string | null;
  chat_provider: string | null;
  summary: string | null;
  findings: AnalysisFinding[];
  frameworks: FrameworkCoverage[];
  key_terms: string[];
  strengths: string[];
  weaknesses: string[];
  recommendations: Recommendation[];
  compliance_score: number | null;
  risk_score: number | null;
  maturity_level: string | null;
  requested_by_user_id: string;
  requested_by_name: string;
  created_at: Date;
  updated_at: Date;
  completed_at: Date | null;
  duration_ms: number | null;
}

function toRecord(row: AnalysisRow): AnalysisRecord {
  return {
    id: row.id,
    documentId: row.document_id,
    tenantId: row.tenant_id,
    fileName: row.file_name,
    title: row.title,
    version: row.version,
    status: row.status,
    error: row.error ?? undefined,
    charCount: row.char_count,
    pageCount: row.page_count ?? undefined,
    chunkCount: row.chunk_count,
    embeddingProvider: row.embedding_provider ?? undefined,
    chatProvider: row.chat_provider ?? undefined,
    summary: row.summary ?? undefined,
    findings: row.findings,
    frameworks: row.frameworks,
    keyTerms: row.key_terms,
    strengths: row.strengths,
    weaknesses: row.weaknesses,
    recommendations: row.recommendations,
    complianceScore: row.compliance_score ?? undefined,
    riskScore: row.risk_score ?? undefined,
    maturityLevel: row.maturity_level ?? undefined,
    requestedByUserId: row.requested_by_user_id,
    requestedByName: row.requested_by_name,
    createdAt: row.created_at.toISOString(),
    updatedAt: row.updated_at.toISOString(),
    completedAt: row.completed_at?.toISOString(),
    durationMs: row.duration_ms ?? undefined,
  };
}

class PostgresAnalysisRepository implements AnalysisRepository {
  async listLatestPerDocument(tenantId: string): Promise<AnalysisWithVersionCount[]> {
    const { rows } = await getPool().query<AnalysisRow & { version_count: string }>(
      `SELECT * FROM (
         SELECT *,
           COUNT(*) OVER (PARTITION BY document_id) AS version_count,
           ROW_NUMBER() OVER (PARTITION BY document_id ORDER BY version DESC) AS rn
         FROM analyses WHERE tenant_id = $1
       ) t WHERE rn = 1 ORDER BY created_at DESC`,
      [tenantId],
    );
    return rows.map((row) => ({ ...toRecord(row), versionCount: Number(row.version_count) }));
  }

  async listVersions(tenantId: string, documentId: string): Promise<AnalysisRecord[]> {
    const { rows } = await getPool().query<AnalysisRow>(
      `SELECT * FROM analyses WHERE tenant_id = $1 AND document_id = $2 ORDER BY version DESC`,
      [tenantId, documentId],
    );
    return rows.map(toRecord);
  }

  async get(tenantId: string, analysisId: string): Promise<AnalysisRecord | null> {
    const { rows } = await getPool().query<AnalysisRow>(
      `SELECT * FROM analyses WHERE tenant_id = $1 AND id = $2`,
      [tenantId, analysisId],
    );
    return rows[0] ? toRecord(rows[0]) : null;
  }

  async getLatest(tenantId: string, documentId: string): Promise<AnalysisRecord | null> {
    const { rows } = await getPool().query<AnalysisRow>(
      `SELECT * FROM analyses WHERE tenant_id = $1 AND document_id = $2
       ORDER BY version DESC LIMIT 1`,
      [tenantId, documentId],
    );
    return rows[0] ? toRecord(rows[0]) : null;
  }

  async nextVersion(tenantId: string, documentId: string): Promise<number> {
    const { rows } = await getPool().query<{ next: number }>(
      `SELECT COALESCE(MAX(version), 0) + 1 AS next FROM analyses
       WHERE tenant_id = $1 AND document_id = $2`,
      [tenantId, documentId],
    );
    return rows[0]?.next ?? 1;
  }

  async insert(record: AnalysisRecord): Promise<AnalysisRecord> {
    await getPool().query(
      `INSERT INTO analyses (
         id, document_id, tenant_id, file_name, title, version, status, error, char_count,
         page_count, chunk_count, embedding_provider, chat_provider, summary, findings,
         frameworks, key_terms, strengths, weaknesses, recommendations, compliance_score,
         risk_score, maturity_level, requested_by_user_id, requested_by_name, created_at,
         updated_at, completed_at, duration_ms
       ) VALUES (
         $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,
         $24,$25,$26,$27,$28,$29
       )`,
      [
        record.id,
        record.documentId,
        record.tenantId,
        record.fileName,
        record.title,
        record.version,
        record.status,
        record.error ?? null,
        record.charCount,
        record.pageCount ?? null,
        record.chunkCount,
        record.embeddingProvider ?? null,
        record.chatProvider ?? null,
        record.summary ?? null,
        JSON.stringify(record.findings),
        JSON.stringify(record.frameworks),
        JSON.stringify(record.keyTerms),
        JSON.stringify(record.strengths),
        JSON.stringify(record.weaknesses),
        JSON.stringify(record.recommendations),
        record.complianceScore ?? null,
        record.riskScore ?? null,
        record.maturityLevel ?? null,
        record.requestedByUserId,
        record.requestedByName,
        record.createdAt,
        record.updatedAt,
        record.completedAt ?? null,
        record.durationMs ?? null,
      ],
    );
    return record;
  }

  async patch(
    tenantId: string,
    analysisId: string,
    patch: Partial<AnalysisRecord>,
  ): Promise<AnalysisRecord | null> {
    const client = await getPool().connect();
    try {
      await client.query("BEGIN");
      const { rows } = await client.query<AnalysisRow>(
        `SELECT * FROM analyses WHERE tenant_id = $1 AND id = $2 FOR UPDATE`,
        [tenantId, analysisId],
      );
      const row = rows[0];
      if (!row) {
        await client.query("ROLLBACK");
        return null;
      }
      const updated: AnalysisRecord = {
        ...toRecord(row),
        ...patch,
        updatedAt: new Date().toISOString(),
      };
      await client.query(
        `UPDATE analyses SET
           file_name = $3, title = $4, status = $5, error = $6, char_count = $7,
           page_count = $8, chunk_count = $9, embedding_provider = $10, chat_provider = $11,
           summary = $12, findings = $13, frameworks = $14, key_terms = $15, strengths = $16,
           weaknesses = $17, recommendations = $18, compliance_score = $19, risk_score = $20,
           maturity_level = $21, updated_at = $22, completed_at = $23, duration_ms = $24
         WHERE tenant_id = $1 AND id = $2`,
        [
          tenantId,
          analysisId,
          updated.fileName,
          updated.title,
          updated.status,
          updated.error ?? null,
          updated.charCount,
          updated.pageCount ?? null,
          updated.chunkCount,
          updated.embeddingProvider ?? null,
          updated.chatProvider ?? null,
          updated.summary ?? null,
          JSON.stringify(updated.findings),
          JSON.stringify(updated.frameworks),
          JSON.stringify(updated.keyTerms),
          JSON.stringify(updated.strengths),
          JSON.stringify(updated.weaknesses),
          JSON.stringify(updated.recommendations),
          updated.complianceScore ?? null,
          updated.riskScore ?? null,
          updated.maturityLevel ?? null,
          updated.updatedAt,
          updated.completedAt ?? null,
          updated.durationMs ?? null,
        ],
      );
      await client.query("COMMIT");
      return updated;
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async delete(tenantId: string, analysisId: string): Promise<void> {
    await getPool().query(`DELETE FROM analyses WHERE tenant_id = $1 AND id = $2`, [
      tenantId,
      analysisId,
    ]);
  }

  async deleteAllForDocument(tenantId: string, documentId: string): Promise<void> {
    await getPool().query(`DELETE FROM analyses WHERE tenant_id = $1 AND document_id = $2`, [
      tenantId,
      documentId,
    ]);
  }
}

export const analysisRepository: AnalysisRepository = new PostgresAnalysisRepository();

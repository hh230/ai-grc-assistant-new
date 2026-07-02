/**
 * Risk repository behind a port, backed by PostgreSQL (`risks` table). Tenant-scoped
 * (CLAUDE.md §20, default deny). Node-only.
 */

import { getPool } from "@/lib/db/pool";
import type { Risk, RiskCategory, RiskStatus } from "./types";

export interface RiskRepository {
  list(tenantId: string): Promise<Risk[]>;
  get(tenantId: string, id: string): Promise<Risk | null>;
  create(risk: Risk): Promise<Risk>;
  update(tenantId: string, id: string, mutate: (risk: Risk) => Risk): Promise<Risk | null>;
  delete(tenantId: string, id: string): Promise<boolean>;
}

interface RiskRow {
  id: string;
  tenant_id: string;
  title: string;
  description: string | null;
  category: RiskCategory;
  likelihood: number;
  impact: number;
  status: RiskStatus;
  owner_name: string;
  control_ids: string[];
  mitigation_plan: string | null;
  residual_likelihood: number | null;
  residual_impact: number | null;
  created_by_user_id: string;
  created_by_name: string;
  created_at: Date;
  updated_at: Date;
  accepted_by_name: string | null;
  accepted_at: Date | null;
}

function toRisk(row: RiskRow): Risk {
  return {
    id: row.id,
    tenantId: row.tenant_id,
    title: row.title,
    description: row.description ?? undefined,
    category: row.category,
    likelihood: row.likelihood,
    impact: row.impact,
    status: row.status,
    ownerName: row.owner_name,
    controlIds: row.control_ids,
    mitigationPlan: row.mitigation_plan ?? undefined,
    residualLikelihood: row.residual_likelihood ?? undefined,
    residualImpact: row.residual_impact ?? undefined,
    createdByUserId: row.created_by_user_id,
    createdByName: row.created_by_name,
    createdAt: row.created_at.toISOString(),
    updatedAt: row.updated_at.toISOString(),
    acceptedByName: row.accepted_by_name ?? undefined,
    acceptedAt: row.accepted_at?.toISOString(),
  };
}

class PostgresRiskRepository implements RiskRepository {
  async list(tenantId: string): Promise<Risk[]> {
    const { rows } = await getPool().query<RiskRow>(
      `SELECT * FROM risks WHERE tenant_id = $1 ORDER BY updated_at DESC`,
      [tenantId],
    );
    return rows.map(toRisk);
  }

  async get(tenantId: string, id: string): Promise<Risk | null> {
    const { rows } = await getPool().query<RiskRow>(
      `SELECT * FROM risks WHERE tenant_id = $1 AND id = $2`,
      [tenantId, id],
    );
    return rows[0] ? toRisk(rows[0]) : null;
  }

  async create(risk: Risk): Promise<Risk> {
    await getPool().query(
      `INSERT INTO risks (
         id, tenant_id, title, description, category, likelihood, impact, status, owner_name,
         control_ids, mitigation_plan, residual_likelihood, residual_impact,
         created_by_user_id, created_by_name, created_at, updated_at, accepted_by_name, accepted_at
       ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)`,
      [
        risk.id,
        risk.tenantId,
        risk.title,
        risk.description ?? null,
        risk.category,
        risk.likelihood,
        risk.impact,
        risk.status,
        risk.ownerName,
        JSON.stringify(risk.controlIds),
        risk.mitigationPlan ?? null,
        risk.residualLikelihood ?? null,
        risk.residualImpact ?? null,
        risk.createdByUserId,
        risk.createdByName,
        risk.createdAt,
        risk.updatedAt,
        risk.acceptedByName ?? null,
        risk.acceptedAt ?? null,
      ],
    );
    return risk;
  }

  async update(tenantId: string, id: string, mutate: (risk: Risk) => Risk): Promise<Risk | null> {
    const client = await getPool().connect();
    try {
      await client.query("BEGIN");
      const { rows } = await client.query<RiskRow>(
        `SELECT * FROM risks WHERE tenant_id = $1 AND id = $2 FOR UPDATE`,
        [tenantId, id],
      );
      const row = rows[0];
      if (!row) {
        await client.query("ROLLBACK");
        return null;
      }
      const updated = mutate(toRisk(row));
      await client.query(
        `UPDATE risks SET
           title = $3, description = $4, category = $5, likelihood = $6, impact = $7,
           status = $8, owner_name = $9, control_ids = $10, mitigation_plan = $11,
           residual_likelihood = $12, residual_impact = $13, updated_at = $14,
           accepted_by_name = $15, accepted_at = $16
         WHERE tenant_id = $1 AND id = $2`,
        [
          tenantId,
          id,
          updated.title,
          updated.description ?? null,
          updated.category,
          updated.likelihood,
          updated.impact,
          updated.status,
          updated.ownerName,
          JSON.stringify(updated.controlIds),
          updated.mitigationPlan ?? null,
          updated.residualLikelihood ?? null,
          updated.residualImpact ?? null,
          updated.updatedAt,
          updated.acceptedByName ?? null,
          updated.acceptedAt ?? null,
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

  async delete(tenantId: string, id: string): Promise<boolean> {
    const { rowCount } = await getPool().query(`DELETE FROM risks WHERE tenant_id = $1 AND id = $2`, [
      tenantId,
      id,
    ]);
    return (rowCount ?? 0) > 0;
  }
}

export const riskRepository: RiskRepository = new PostgresRiskRepository();

/**
 * Mission repository, backed by PostgreSQL (`policy_missions` + `policy_mission_steps`,
 * 0015_policy_missions.sql). Read-only from apps/web today — missions are written by the
 * Policy Intelligence pipeline via `grc_persistence_web.missions.PolicyMissionStore`
 * (packages/persistence-web), not by this app. Node-only.
 */

import { getPool } from "@/lib/db/pool";
import type { Mission } from "./types";

export interface MissionsRepository {
  listForTenant(tenantId: string): Promise<Mission[]>;
}

interface MissionRow {
  id: string;
  agent: string;
  goal: string;
  status: string;
  awaiting_approval: boolean;
  created_by_name: string;
  created_at: Date;
  updated_at: Date;
  step_count: string;
  last_step: string | null;
}

class PostgresMissionsRepository implements MissionsRepository {
  async listForTenant(tenantId: string): Promise<Mission[]> {
    const { rows } = await getPool().query<MissionRow>(
      `SELECT
         m.id, m.agent, m.goal, m.status, m.awaiting_approval, m.created_by_name,
         m.created_at, m.updated_at,
         count(s.id) AS step_count,
         (SELECT step FROM policy_mission_steps
           WHERE mission_id = m.id ORDER BY position DESC LIMIT 1) AS last_step
       FROM policy_missions m
       LEFT JOIN policy_mission_steps s ON s.mission_id = m.id
       WHERE m.tenant_id = $1
       GROUP BY m.id
       ORDER BY m.created_at DESC`,
      [tenantId],
    );
    return rows.map((row) => ({
      id: row.id,
      agent: row.agent,
      goal: row.goal,
      status: row.status,
      awaitingApproval: row.awaiting_approval,
      createdByName: row.created_by_name,
      createdAt: row.created_at.toISOString(),
      updatedAt: row.updated_at.toISOString(),
      stepCount: Number(row.step_count),
      lastStep: row.last_step,
    }));
  }
}

export const missionsRepository: MissionsRepository = new PostgresMissionsRepository();

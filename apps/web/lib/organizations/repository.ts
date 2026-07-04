/**
 * Organization + membership repository, backed by PostgreSQL (`organizations` +
 * `user_organizations`). A user can belong to more than one organization; membership is
 * the join table a session's active `organizationId` is validated against on switch.
 * Node-only.
 */

import { getPool } from "@/lib/db/pool";
import type { Organization, OrganizationMembership } from "./types";

export interface OrganizationRepository {
  listForUser(userId: string): Promise<OrganizationMembership[]>;
  get(organizationId: string): Promise<Organization | null>;
  getMembership(userId: string, organizationId: string): Promise<OrganizationMembership | null>;
  isMember(userId: string, organizationId: string): Promise<boolean>;
  create(org: Organization): Promise<Organization>;
  addMember(userId: string, organizationId: string, role: string): Promise<void>;
}

interface OrganizationRow {
  id: string;
  name: string;
  org_type: string;
  industry: string;
  created_by_user_id: string;
  created_at: Date;
}

function toOrganization(row: OrganizationRow): Organization {
  return {
    id: row.id,
    name: row.name,
    orgType: row.org_type,
    industry: row.industry,
    createdByUserId: row.created_by_user_id,
    createdAt: row.created_at.toISOString(),
  };
}

class PostgresOrganizationRepository implements OrganizationRepository {
  async listForUser(userId: string): Promise<OrganizationMembership[]> {
    const { rows } = await getPool().query<OrganizationRow & { role: string }>(
      `SELECT o.*, m.role FROM organizations o
       JOIN user_organizations m ON m.organization_id = o.id
       WHERE m.user_id = $1
       ORDER BY m.created_at ASC`,
      [userId],
    );
    return rows.map((row) => ({ ...toOrganization(row), role: row.role }));
  }

  async get(organizationId: string): Promise<Organization | null> {
    const { rows } = await getPool().query<OrganizationRow>(
      `SELECT * FROM organizations WHERE id = $1`,
      [organizationId],
    );
    return rows[0] ? toOrganization(rows[0]) : null;
  }

  async getMembership(
    userId: string,
    organizationId: string,
  ): Promise<OrganizationMembership | null> {
    const { rows } = await getPool().query<OrganizationRow & { role: string }>(
      `SELECT o.*, m.role FROM organizations o
       JOIN user_organizations m ON m.organization_id = o.id
       WHERE m.user_id = $1 AND m.organization_id = $2`,
      [userId, organizationId],
    );
    const row = rows[0];
    return row ? { ...toOrganization(row), role: row.role } : null;
  }

  async isMember(userId: string, organizationId: string): Promise<boolean> {
    const { rows } = await getPool().query(
      `SELECT 1 FROM user_organizations WHERE user_id = $1 AND organization_id = $2`,
      [userId, organizationId],
    );
    return rows.length > 0;
  }

  async create(org: Organization): Promise<Organization> {
    await getPool().query(
      `INSERT INTO organizations (id, name, org_type, industry, created_by_user_id, created_at)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [org.id, org.name, org.orgType, org.industry, org.createdByUserId, org.createdAt],
    );
    return org;
  }

  async addMember(userId: string, organizationId: string, role: string): Promise<void> {
    await getPool().query(
      `INSERT INTO user_organizations (user_id, organization_id, role)
       VALUES ($1, $2, $3)
       ON CONFLICT (user_id, organization_id) DO NOTHING`,
      [userId, organizationId, role],
    );
  }
}

export const organizationRepository: OrganizationRepository = new PostgresOrganizationRepository();

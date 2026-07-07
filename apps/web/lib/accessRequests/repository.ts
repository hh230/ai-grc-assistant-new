/**
 * Access request repository, backed by PostgreSQL (`access_requests`,
 * 0024_access_onboarding.sql). Node-only.
 */

import { getPool } from "@/lib/db/pool";
import type { AccessRequest, AccessRequestStatus } from "./types";

export interface AccessRequestRepository {
  create(request: AccessRequest): Promise<AccessRequest>;
  findPendingByEmail(email: string): Promise<AccessRequest | null>;
  get(id: string): Promise<AccessRequest | null>;
  list(status?: AccessRequestStatus): Promise<AccessRequest[]>;
  updateStatus(
    id: string,
    status: AccessRequestStatus,
    reviewedBy: string,
    reviewedAt: string,
  ): Promise<void>;
}

interface AccessRequestRow {
  id: string;
  name: string;
  email: string;
  organization_name: string;
  role_title: string;
  message: string | null;
  status: string;
  created_at: Date;
  reviewed_at: Date | null;
  reviewed_by: string | null;
}

function toAccessRequest(row: AccessRequestRow): AccessRequest {
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    organizationName: row.organization_name,
    roleTitle: row.role_title,
    message: row.message,
    status: row.status as AccessRequestStatus,
    createdAt: row.created_at.toISOString(),
    reviewedAt: row.reviewed_at ? row.reviewed_at.toISOString() : null,
    reviewedBy: row.reviewed_by,
  };
}

class PostgresAccessRequestRepository implements AccessRequestRepository {
  async create(request: AccessRequest): Promise<AccessRequest> {
    await getPool().query(
      `INSERT INTO access_requests
         (id, name, email, organization_name, role_title, message, status, created_at,
          reviewed_at, reviewed_by)
       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`,
      [
        request.id,
        request.name,
        request.email,
        request.organizationName,
        request.roleTitle,
        request.message,
        request.status,
        request.createdAt,
        request.reviewedAt,
        request.reviewedBy,
      ],
    );
    return request;
  }

  async findPendingByEmail(email: string): Promise<AccessRequest | null> {
    const { rows } = await getPool().query<AccessRequestRow>(
      `SELECT * FROM access_requests
       WHERE lower(email) = lower($1) AND status = 'pending'
       ORDER BY created_at DESC LIMIT 1`,
      [email],
    );
    return rows[0] ? toAccessRequest(rows[0]) : null;
  }

  async get(id: string): Promise<AccessRequest | null> {
    const { rows } = await getPool().query<AccessRequestRow>(
      `SELECT * FROM access_requests WHERE id = $1`,
      [id],
    );
    return rows[0] ? toAccessRequest(rows[0]) : null;
  }

  async list(status?: AccessRequestStatus): Promise<AccessRequest[]> {
    const { rows } = status
      ? await getPool().query<AccessRequestRow>(
          `SELECT * FROM access_requests WHERE status = $1 ORDER BY created_at DESC`,
          [status],
        )
      : await getPool().query<AccessRequestRow>(
          `SELECT * FROM access_requests ORDER BY created_at DESC`,
        );
    return rows.map(toAccessRequest);
  }

  async updateStatus(
    id: string,
    status: AccessRequestStatus,
    reviewedBy: string,
    reviewedAt: string,
  ): Promise<void> {
    await getPool().query(
      `UPDATE access_requests SET status = $2, reviewed_by = $3, reviewed_at = $4 WHERE id = $1`,
      [id, status, reviewedBy, reviewedAt],
    );
  }
}

export const accessRequestRepository: AccessRequestRepository =
  new PostgresAccessRequestRepository();

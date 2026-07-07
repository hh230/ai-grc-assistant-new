/**
 * User account repository, backed by PostgreSQL (`users`, 0024_access_onboarding.sql). The
 * swap point for a real identity backend (SSO/OIDC): replace `PostgresUsersRepository` and
 * nothing else in the auth flow changes (CLAUDE.md §6 #5, mirrors `lib/organizations`). Node-only.
 */

import { getPool } from "@/lib/db/pool";
import type { User } from "./types";

export interface UsersRepository {
  findByEmail(email: string): Promise<User | null>;
  findById(userId: string): Promise<User | null>;
  create(user: User): Promise<User>;
}

interface UserRow {
  id: string;
  email: string;
  name: string;
  password_hash: string;
  created_at: Date;
}

function toUser(row: UserRow): User {
  return {
    id: row.id,
    email: row.email,
    name: row.name,
    passwordHash: row.password_hash,
    createdAt: row.created_at.toISOString(),
  };
}

class PostgresUsersRepository implements UsersRepository {
  async findByEmail(email: string): Promise<User | null> {
    const { rows } = await getPool().query<UserRow>(
      `SELECT * FROM users WHERE lower(email) = lower($1)`,
      [email.trim()],
    );
    return rows[0] ? toUser(rows[0]) : null;
  }

  async findById(userId: string): Promise<User | null> {
    const { rows } = await getPool().query<UserRow>(`SELECT * FROM users WHERE id = $1`, [
      userId,
    ]);
    return rows[0] ? toUser(rows[0]) : null;
  }

  async create(user: User): Promise<User> {
    await getPool().query(
      `INSERT INTO users (id, email, name, password_hash, created_at)
       VALUES ($1, $2, $3, $4, $5)`,
      [user.id, user.email, user.name, user.passwordHash, user.createdAt],
    );
    return user;
  }
}

export const usersRepository: UsersRepository = new PostgresUsersRepository();

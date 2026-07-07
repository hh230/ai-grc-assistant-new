/**
 * Login-time user lookup behind an `AuthRepository` port (KI-P9, ADR-0034). Replaces the
 * old in-memory `SEED_USERS` demo directory with a real Postgres-backed one: an account only
 * exists once it was created via the invite-accept flow (`lib/invitations/service.ts`), so
 * there is no public signup and no hardcoded demo password.
 *
 * A `StoredUser` folds together identity (`users`) and the account's *first* organization
 * membership (`user_organizations`, joined via `lib/organizations/repository.ts`) — the same
 * shape the login route already expects to build a session from. Users with no membership at
 * all cannot sign in (there is nothing to scope their session to).
 *
 * `apiToken` is a placeholder, not a real backend-recognized credential: `apps/api`'s
 * `API_AUTH_TOKENS` still only maps the handful of dev bearer tokens seeded in
 * `apps/api/.../composition.py`. Bridging real web users to real backend principals is
 * out of KI-P9's scope (auth/users/orgs/invitations only) and is named, not silently
 * dropped — see ADR-0034 "Known limitations".
 */

import { organizationRepository } from "@/lib/organizations/repository";
import { usersRepository } from "@/lib/users/repository";
import { isUserRole, type UserRole } from "./roles";

export interface StoredUser {
  userId: string;
  email: string;
  name: string;
  initials: string;
  organizationId: string;
  organizationName: string;
  roles: UserRole[];
  /** scrypt hash — see `password.ts`. */
  passwordHash: string;
  /** Backend bearer token this user presents to the FastAPI API (server-side only). */
  apiToken: string;
}

export interface AuthRepository {
  findByEmail(email: string): Promise<StoredUser | null>;
}

function initialsFrom(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const initials = parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
  return initials || "?";
}

class PostgresAuthRepository implements AuthRepository {
  async findByEmail(email: string): Promise<StoredUser | null> {
    const user = await usersRepository.findByEmail(email);
    if (!user) return null;

    const memberships = await organizationRepository.listForUser(user.id);
    const membership = memberships[0];
    if (!membership || !isUserRole(membership.role)) return null;

    return {
      userId: user.id,
      email: user.email,
      name: user.name,
      initials: initialsFrom(user.name),
      organizationId: membership.id,
      organizationName: membership.name,
      roles: [membership.role],
      passwordHash: user.passwordHash,
      apiToken: `web-user:${user.id}`,
    };
  }
}

export const authRepository: AuthRepository = new PostgresAuthRepository();

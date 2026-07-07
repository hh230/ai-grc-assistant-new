/** A real, Postgres-backed account (KI-P9, ADR-0034) — created only through the invite-accept
 * flow (`lib/invitations/service.ts`). Never carries anything beyond identity + credential;
 * organization membership lives in `user_organizations` (`lib/organizations`), not here. */
export interface User {
  id: string;
  email: string;
  name: string;
  /** scrypt hash — see `lib/auth/password.ts`. */
  passwordHash: string;
  createdAt: string;
}

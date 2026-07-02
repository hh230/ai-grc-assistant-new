/**
 * Seeded user directory behind an `AuthRepository` port. This is the swap point for a real
 * identity backend: replace `InMemoryAuthRepository` with an OIDC/SSO adapter or a call to
 * the FastAPI `/auth` surface, and nothing else in the auth flow changes (CLAUDE.md §6 #5,
 * §17 — extend behind the port, don't edit the flow).
 *
 * Node-only (holds password hashes). All demo users share the password `GrcDemo!2026` and
 * belong to tenant `dev-org`, so the `owner` account's `dev-token` matches the backend's
 * seeded dev principal (`apps/api/.../composition.py`).
 */

import type { UserRole } from "./roles";

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

const ORG_ID = "dev-org";
const ORG_NAME = "Acme Financial Group";

const SEED_USERS: StoredUser[] = [
  {
    userId: "dev-user",
    email: "owner@acme.test",
    name: "Mona Al-Owner",
    initials: "MO",
    organizationId: ORG_ID,
    organizationName: ORG_NAME,
    roles: ["owner"],
    passwordHash:
      "scrypt$16384$8$1$b599ad50ea495488c482666f266ec759$429090a2dd03bcbc4255605e305c66845d03380d3c3f4486d0889d36d69412f35ad79fce1c1b42fdf5459588dcafc82ed108e577d71dfe0c094edd2fbc056c45",
    apiToken: "dev-token",
  },
  {
    userId: "user-admin",
    email: "admin@acme.test",
    name: "Adam Admin",
    initials: "AA",
    organizationId: ORG_ID,
    organizationName: ORG_NAME,
    roles: ["admin"],
    passwordHash:
      "scrypt$16384$8$1$90d8b86e03ec3938e9cb029cf5ea7803$696a42c15a848fd88fbce99e9664a7363ecc64c2d64bb99e2031ee29cc478757eaf2cfa1ae515c93f762d8ec3441b185a8e829e8b23848f7aa8d4ffdd58fc3d8",
    apiToken: "dev-token-admin",
  },
  {
    userId: "user-compliance",
    email: "compliance@acme.test",
    name: "Carla Compliance",
    initials: "CC",
    organizationId: ORG_ID,
    organizationName: ORG_NAME,
    roles: ["compliance_manager"],
    passwordHash:
      "scrypt$16384$8$1$1a3d904b8e2a6f62bcb35e1995d00466$3e2430ca223aeb8d7a20273809023ed8bfdc05d73c0995ddfbc0d15b592522754896f5a86eddf4a6e03e9b71dacd92cdad2b54f444fc4ca8da3a96c97a536c11",
    apiToken: "dev-token-compliance",
  },
  {
    userId: "user-risk",
    email: "risk@acme.test",
    name: "Rami Risk",
    initials: "RR",
    organizationId: ORG_ID,
    organizationName: ORG_NAME,
    roles: ["risk_manager"],
    passwordHash:
      "scrypt$16384$8$1$1c2c99f065e8e955f5e22a1f8ca16ca4$7d2efc71542a5b3a756ce82eddd919c44a6e14bdea871df5dfc6e174ac4f84d759b0e44145bef8963fb52cdc5b3ccfcf7b3ead4ecef3382940f32880a73d49fb",
    apiToken: "dev-token-risk",
  },
  {
    userId: "user-analyst",
    email: "analyst@acme.test",
    name: "Ana Analyst",
    initials: "AN",
    organizationId: ORG_ID,
    organizationName: ORG_NAME,
    roles: ["analyst"],
    passwordHash:
      "scrypt$16384$8$1$e40ca6a8b602c3939fe79a764a702fb8$bb54acdbc18e5ec7bf330f0bca665ed25488b1de100fe5907271215f281616cebc001762a258ddc7140fa0d99c2409f8a1a36d76dc4dd190e49b08c9972826c2",
    apiToken: "dev-token-analyst",
  },
  {
    userId: "user-auditor",
    email: "auditor@acme.test",
    name: "Aziz Auditor",
    initials: "AZ",
    organizationId: ORG_ID,
    organizationName: ORG_NAME,
    roles: ["auditor"],
    passwordHash:
      "scrypt$16384$8$1$b1349e417f20c81ac86ee24167330107$87b86da34f09e0b7fceda4c2072961f2478aec39098659cf509bba5366a5e264693f9ecf71dad1af91ade25edf5e0619f632cfe8460772b6051e0a6dc0fbe954",
    apiToken: "dev-token-auditor",
  },
  {
    userId: "user-viewer",
    email: "viewer@acme.test",
    name: "Vera Viewer",
    initials: "VV",
    organizationId: ORG_ID,
    organizationName: ORG_NAME,
    roles: ["viewer"],
    passwordHash:
      "scrypt$16384$8$1$9077761bc4ec5321b7f0b6425c372ff8$d808f3331dd4c5fa3f8e9079bc838b07fb5fdf75c5aa2ddfa767c28bdeda90c638311e308dd5cdbc39be43c80e4e21ef25833c59e55eef803a7604a599b3b016",
    apiToken: "dev-token-viewer",
  },
];

export interface AuthRepository {
  findByEmail(email: string): Promise<StoredUser | null>;
}

class InMemoryAuthRepository implements AuthRepository {
  private readonly byEmail: Map<string, StoredUser>;

  constructor(users: StoredUser[]) {
    this.byEmail = new Map(users.map((user) => [user.email.toLowerCase(), user]));
  }

  async findByEmail(email: string): Promise<StoredUser | null> {
    return this.byEmail.get(email.trim().toLowerCase()) ?? null;
  }
}

export const authRepository: AuthRepository = new InMemoryAuthRepository(SEED_USERS);

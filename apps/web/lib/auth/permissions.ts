/**
 * Default-deny RBAC permission matrix — a faithful mirror of the backend
 * `RbacAuthorizationService` (`apps/api/.../runtime/authorization.py`). The frontend uses
 * it to gate UI affordances and routes; the backend remains the authoritative enforcer on
 * every write. Keeping the two in lockstep means the UI never offers an action the API
 * will reject. An absent entry is denied.
 */

import type { UserRole } from "./roles";

export const ACTIONS = [
  "create",
  "read",
  "update",
  "delete",
  "approve",
  "execute",
  "publish",
] as const;
export type Action = (typeof ACTIONS)[number];

export const RESOURCE_TYPES = [
  "mission",
  "workspace",
  "policy",
  "risk",
  "assessment",
  "evidence",
  "control",
  "framework",
  "knowledge_source",
  "report",
  "tool",
  "agent",
  "plugin",
  "audit",
] as const;
export type ResourceType = (typeof RESOURCE_TYPES)[number];

const ALL_ACTIONS: readonly Action[] = ACTIONS;
const READ: readonly Action[] = ["read"];
const AUTHOR: readonly Action[] = ["create", "read", "update", "execute"];

const OPERATIONAL: readonly ResourceType[] = [
  "mission",
  "workspace",
  "control",
  "policy",
  "risk",
  "assessment",
  "evidence",
  "report",
  "knowledge_source",
];
const CATALOG: readonly ResourceType[] = ["framework", "tool", "agent", "plugin"];
const ALL_RESOURCES: readonly ResourceType[] = RESOURCE_TYPES;

type Matrix = Partial<Record<ResourceType, ReadonlySet<Action>>>;

function grant(resources: readonly ResourceType[], actions: readonly Action[]): Matrix {
  const matrix: Matrix = {};
  for (const resource of resources) matrix[resource] = new Set(actions);
  return matrix;
}

function merge(...matrices: Matrix[]): Matrix {
  const merged: Matrix = {};
  for (const matrix of matrices) {
    for (const [resource, actions] of Object.entries(matrix) as [
      ResourceType,
      ReadonlySet<Action>,
    ][]) {
      merged[resource] = new Set([...(merged[resource] ?? []), ...actions]);
    }
  }
  return merged;
}

const without = (resources: readonly ResourceType[], ...exclude: ResourceType[]): ResourceType[] =>
  resources.filter((resource) => !exclude.includes(resource));

const POLICY: Record<UserRole, Matrix> = {
  owner: grant(ALL_RESOURCES, ALL_ACTIONS),
  admin: grant(ALL_RESOURCES, ALL_ACTIONS),
  compliance_manager: merge(
    grant(OPERATIONAL, ALL_ACTIONS),
    grant(CATALOG, READ),
    grant(["audit"], READ),
  ),
  risk_manager: merge(
    grant(["risk"], ALL_ACTIONS),
    grant(["mission"], AUTHOR),
    grant(without(OPERATIONAL, "risk", "mission"), READ),
    grant(CATALOG, READ),
    grant(["audit"], READ),
  ),
  analyst: merge(grant(OPERATIONAL, AUTHOR), grant(CATALOG, READ)),
  auditor: grant(ALL_RESOURCES, READ),
  viewer: merge(grant(OPERATIONAL, READ), grant(CATALOG, READ)),
};

/** True when any of the principal's roles grants `action` on `resource`. Default deny. */
export function can(roles: readonly UserRole[], action: Action, resource: ResourceType): boolean {
  return roles.some((role) => POLICY[role]?.[resource]?.has(action) ?? false);
}

/** Convenience: can the principal read this resource at all? */
export function canRead(roles: readonly UserRole[], resource: ResourceType): boolean {
  return can(roles, "read", resource);
}

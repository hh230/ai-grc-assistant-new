/**
 * Organization membership + creation. Any authenticated user may create a new organization
 * (self-service tenant creation) and becomes its owner; switching requires actual
 * membership, verified against `user_organizations` — never trust a client-supplied
 * organization id without checking it (CLAUDE.md §20, default deny).
 */

import { randomUUID } from "node:crypto";
import { z } from "zod";
import { ForbiddenError, ValidationError } from "@/lib/errors";
import type { ActorContext } from "@/lib/auth/actor";
import { organizationRepository } from "./repository";
import type { Organization, OrganizationMembership } from "./types";


export const createOrganizationSchema = z.object({
  name: z.string().trim().min(1, "Company name is required.").max(200),
  orgType: z.string().trim().min(1, "Company type is required.").max(120),
  industry: z.string().trim().min(1, "Company activity/industry is required.").max(120),
});

export type CreateOrganizationInput = z.infer<typeof createOrganizationSchema>;

export async function listMyOrganizations(actor: ActorContext): Promise<OrganizationMembership[]> {
  return organizationRepository.listForUser(actor.userId);
}

export async function createOrganization(
  actor: ActorContext,
  input: unknown,
): Promise<Organization> {
  const parsed = createOrganizationSchema.safeParse(input);
  if (!parsed.success) {
    throw new ValidationError(parsed.error.issues[0]?.message ?? "Invalid organization details.");
  }
  const org: Organization = {
    id: randomUUID(),
    name: parsed.data.name,
    orgType: parsed.data.orgType,
    industry: parsed.data.industry,
    createdByUserId: actor.userId,
    createdAt: new Date().toISOString(),
  };
  await organizationRepository.create(org);
  await organizationRepository.addMember(actor.userId, org.id, "owner");
  return org;
}

/** Verifies membership before a session switch; throws if the user does not belong. */
export async function assertMembership(
  actor: ActorContext,
  organizationId: string,
): Promise<OrganizationMembership> {
  const membership = await organizationRepository.getMembership(actor.userId, organizationId);
  if (!membership) {
    throw new ForbiddenError("You are not a member of this organization.");
  }
  return membership;
}

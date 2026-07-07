/**
 * Access request lifecycle (KI-P9, ADR-0034): a visitor submits one from the public landing
 * page; an owner/admin reviews it; approving creates an `Invitation` (never a user directly).
 * Node-only.
 */

import { randomUUID } from "node:crypto";
import { z } from "zod";
import type { ActorContext } from "@/lib/auth/actor";
import { NotFoundError, ValidationError } from "@/lib/errors";
import { INVITED_ROLES, type InvitedRole } from "@/lib/invitations/types";
import { createInvitation, type CreatedInvitation } from "@/lib/invitations/service";
import { accessRequestRepository } from "./repository";
import type { AccessRequest, AccessRequestStatus } from "./types";

export const submitAccessRequestSchema = z.object({
  name: z.string().trim().min(1, "Full name is required.").max(200),
  email: z.string().trim().email("A valid work email is required."),
  organizationName: z.string().trim().min(1, "Organization name is required.").max(200),
  roleTitle: z.string().trim().min(1, "Job title / role is required.").max(200),
  message: z.string().trim().max(2000).optional(),
});

/** Submitting twice with the same email while a request is still pending returns the
 * existing one instead of creating a duplicate — idempotent, no spam-guard logic needed. */
export async function submitAccessRequest(input: unknown): Promise<AccessRequest> {
  const parsed = submitAccessRequestSchema.safeParse(input);
  if (!parsed.success) {
    throw new ValidationError(parsed.error.issues[0]?.message ?? "Invalid request.");
  }

  const existing = await accessRequestRepository.findPendingByEmail(parsed.data.email);
  if (existing) return existing;

  const request: AccessRequest = {
    id: randomUUID(),
    name: parsed.data.name,
    email: parsed.data.email.toLowerCase(),
    organizationName: parsed.data.organizationName,
    roleTitle: parsed.data.roleTitle,
    message: parsed.data.message?.trim() || null,
    status: "pending",
    createdAt: new Date().toISOString(),
    reviewedAt: null,
    reviewedBy: null,
  };
  await accessRequestRepository.create(request);
  return request;
}

export async function listAccessRequests(status?: AccessRequestStatus): Promise<AccessRequest[]> {
  return accessRequestRepository.list(status);
}

async function loadPendingOrThrow(id: string): Promise<AccessRequest> {
  const request = await accessRequestRepository.get(id);
  if (!request) throw new NotFoundError("Access request not found.");
  if (request.status !== "pending") {
    throw new ValidationError("This access request has already been reviewed.");
  }
  return request;
}

export const approveAccessRequestSchema = z.object({
  invitedRole: z.enum(INVITED_ROLES).default("owner"),
});

export interface ApproveAccessRequestResult {
  accessRequest: AccessRequest;
  invitation: CreatedInvitation["invitation"];
  /** The raw invite token — surface once, in this response, for the admin to copy/send. */
  token: string;
}

export async function approveAccessRequest(
  actor: ActorContext,
  id: string,
  input: unknown,
): Promise<ApproveAccessRequestResult> {
  const request = await loadPendingOrThrow(id);
  const parsed = approveAccessRequestSchema.safeParse(input ?? {});
  const invitedRole: InvitedRole = parsed.success ? parsed.data.invitedRole : "owner";

  const now = new Date().toISOString();
  await accessRequestRepository.updateStatus(id, "approved", actor.userId, now);

  const { invitation, token } = await createInvitation({
    email: request.email,
    organizationName: request.organizationName,
    invitedRole,
    accessRequestId: request.id,
  });

  return {
    accessRequest: { ...request, status: "approved", reviewedAt: now, reviewedBy: actor.userId },
    invitation,
    token,
  };
}

export async function rejectAccessRequest(
  actor: ActorContext,
  id: string,
): Promise<AccessRequest> {
  const request = await loadPendingOrThrow(id);
  const now = new Date().toISOString();
  await accessRequestRepository.updateStatus(id, "rejected", actor.userId, now);
  return { ...request, status: "rejected", reviewedAt: now, reviewedBy: actor.userId };
}

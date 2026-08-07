/**
 * Missions — proxied to grc-api's `/v1/missions` (ADR 0052: the single product API surface).
 *
 * **This is the whole of the "two Missions" fix.** The workspace used to read `policy_missions`, a
 * table written only by the previous-generation `apps/api` and disconnected from the Mission Engine
 * that actually runs the product's missions (ADR 0066 said so in its Context; nothing had repointed
 * the page). A customer could approve a governance mission end to end and still be told
 * "No missions yet".
 *
 * No data was copied and nothing is synchronised: the engine is asked, at read time, what missions
 * this tenant has. The legacy table is untouched — its rows, if a previous-generation deployment
 * ever wrote any, are still exactly where they were.
 */

import { ForbiddenError, NotFoundError, UpstreamError } from "@/lib/errors";
import type { ActorContext } from "@/lib/auth/actor";
import { logger } from "@/lib/observability/logger";
import { mintGrcApiServiceToken } from "@/lib/discovery/serviceToken";
import type { Mission } from "./types";

const AWAITING_APPROVAL = "awaiting_approval";

function grcApiBaseUrl(): string {
  return process.env.GRC_API_BASE_URL ?? "http://localhost:8000";
}

interface MissionDto {
  id: string;
  type: string;
  scope: string;
  status: string;
  created_at: number;
  updated_at: number;
}

/** grc-api reports timestamps as epoch seconds; the workspace renders ISO strings. */
function toIso(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toISOString();
}

function toMission(dto: MissionDto): Mission {
  return {
    id: dto.id,
    type: dto.type,
    scope: dto.scope,
    status: dto.status,
    awaitingApproval: dto.status === AWAITING_APPROVAL,
    createdAt: toIso(dto.created_at),
    updatedAt: toIso(dto.updated_at),
  };
}

/** Every mission the engine holds for the actor's tenant, newest first (CLAUDE.md §20 — the tenant
 * is asserted in the token, so the scope is the backend's to enforce, not this caller's to filter). */
export async function listMissions(actor: ActorContext): Promise<Mission[]> {
  const url = new URL("/v1/missions?page_size=100", grcApiBaseUrl());
  const token = mintGrcApiServiceToken({
    tenantId: actor.tenantId,
    principalId: actor.userId,
  });

  let response: Response;
  try {
    response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
  } catch (error) {
    logger.error("missions_upstream_unreachable", error, { url: url.toString() });
    throw new UpstreamError("Could not reach the missions backend.", true);
  }

  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as {
      error?: { message?: string };
    };
    const message = problem.error?.message ?? `Request failed (${response.status}).`;
    if (response.status === 403) throw new ForbiddenError(message);
    if (response.status === 404) throw new NotFoundError(message);
    logger.error("missions_upstream_error", { status: response.status, url: url.toString() });
    throw new UpstreamError(message);
  }

  const payload = (await response.json()) as { items: MissionDto[] };
  return payload.items.map(toMission);
}

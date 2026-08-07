/**
 * A Mission as the workspace lists it (CLAUDE.md §8).
 *
 * **One source of truth: the V2 Mission Engine** (ADR 0042), read through grc-api — the single
 * product API surface (ADR 0052). Nothing is copied here and nothing is synchronised; the engine
 * owns the mission and this is a projection of what it says right now.
 *
 * This shape is what the engine's LIST actually knows. It deliberately does not carry a step count
 * or an owner name: the read model does not project them, and columns that are permanently empty
 * tell a customer less than columns that are not there.
 */

/** The lifecycle, exactly as `mission_engine.lifecycle.MissionStatus` names it. Duplicated here
 * rather than inferred: this list is what the UI can label, and it should fail visibly when the
 * engine grows a state the workspace has never heard of. */
export const MISSION_STATUSES = [
  "created",
  "planned",
  "executing",
  "awaiting_approval",
  "resumed",
  "completed",
  "failed",
  "cancelled",
  "archived",
] as const;
export type MissionStatus = (typeof MISSION_STATUSES)[number];

export function isMissionStatus(value: string): value is MissionStatus {
  return (MISSION_STATUSES as readonly string[]).includes(value);
}

export interface Mission {
  id: string;
  /** The product's Mission Type id (`generate_governance_plan`, `gap_assessment`, …). */
  type: string;
  /** The human-readable subject the mission runs against. */
  scope: string;
  status: string;
  /** Derived, not stored: the engine pauses AT this status, so it is the same fact. */
  awaitingApproval: boolean;
  createdAt: string;
  updatedAt: string;
}

/**
 * The governance program's standing — the first thing shown in the program experience
 * (CLAUDE.md §3 pillar 10).
 *
 * Not a score. "Which program, assessed when, reviewed when, still active" is the question someone
 * opens the product with; the numbers come after, and only because they lead somewhere.
 *
 * Computes nothing new about governance. Every field is read from the active plan the Mission
 * Engine already produced — the one exception is the review date, which is a calendar fact about
 * the plan rather than a measurement of the organization.
 */

import type { ActorContext } from "@/lib/auth/actor";
import { getActivePlan } from "./service";
import type { PlanDetail } from "./types";

/**
 * How long a governance assessment stands before it should be redone.
 *
 * Ninety days is a product decision, not a regulatory one: it is short enough that a plan reflects
 * an organization that has changed, and long enough that the plan has a chance to be executed. It
 * lives here, named, so that changing it is one edit and an explicit choice — not a number
 * scattered through the interface.
 */
export const REVIEW_INTERVAL_DAYS = 90;

export type ProgramState = "none" | "active" | "reviewDue";

export interface ProgramStatus {
  state: ProgramState;
  version: number | null;
  /** When the assessment behind this plan was concluded. */
  assessedAt: string | null;
  /** `assessedAt` + the review interval. Null when there is no plan to review. */
  reviewDueAt: string | null;
  /** Negative once the review is overdue, which is what turns the state to `reviewDue`. */
  daysUntilReview: number | null;
  /** Carried so callers do not fetch the plan twice — the sections below all need it. */
  plan: PlanDetail | null;
}

const DAY_MS = 24 * 60 * 60 * 1000;

export async function getProgramStatus(actor: ActorContext): Promise<ProgramStatus> {
  const plan = await getActivePlan(actor);
  if (plan === null) {
    return {
      state: "none",
      version: null,
      assessedAt: null,
      reviewDueAt: null,
      daysUntilReview: null,
      plan: null,
    };
  }

  // `createdAt` is epoch seconds on the plan record; the interface works in ISO strings.
  const assessedAtMs = plan.plan.createdAt * 1000;
  const reviewDueAtMs = assessedAtMs + REVIEW_INTERVAL_DAYS * DAY_MS;
  const daysUntilReview = Math.ceil((reviewDueAtMs - Date.now()) / DAY_MS);

  return {
    state: daysUntilReview <= 0 ? "reviewDue" : "active",
    version: plan.plan.version,
    assessedAt: new Date(assessedAtMs).toISOString(),
    reviewDueAt: new Date(reviewDueAtMs).toISOString(),
    daysUntilReview,
    plan,
  };
}

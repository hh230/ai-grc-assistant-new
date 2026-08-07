/**
 * Governance events — meaningful ones only.
 *
 * Not a general timeline. "Logged in", "viewed a page", "uploaded a logo" are things that
 * happened; they are not things that happened *to the governance program*, and a feed that mixes
 * the two teaches a customer to stop reading it.
 *
 * The admitted vocabulary is closed and lives here:
 *
 *     assessmentCompleted  the interview concluded and produced a plan
 *     planApproved         a human approved the plan at its gate
 *     actionCompleted      a plan action was finished
 *     evidenceAdded        proof was linked to a control
 *     reviewDue            the program's review date has passed
 *
 * Adding a sixth means answering the pillar-10 question first: does it help the customer manage
 * their governance program? If not, it does not belong here either.
 *
 * This app has no domain-event store, so each entry is assembled from the timestamped record that
 * already proves it happened. Nothing is invented and nothing is inferred from absence.
 */

import type { ActorContext } from "@/lib/auth/actor";
import { ForbiddenError } from "@/lib/errors";
import { evidenceRepository } from "@/lib/evidence/repository";
import type { ProgramStatus } from "./programStatus";

export type GovernanceEventKind =
  | "assessmentCompleted"
  | "planApproved"
  | "actionCompleted"
  | "evidenceAdded"
  | "reviewDue";

export interface GovernanceEvent {
  id: string;
  kind: GovernanceEventKind;
  /** The subject, when there is one — an action's title, an evidence artifact's name. */
  subject: string | null;
  occurredAt: string;
}

const SHOWN = 6;

export async function getGovernanceActivity(
  actor: ActorContext,
  status: ProgramStatus,
): Promise<GovernanceEvent[]> {
  const events: GovernanceEvent[] = [];

  if (status.plan) {
    const { plan, items } = status.plan;
    // A plan exists only because a human approved it at the gate, and only because an assessment
    // concluded first. Both facts are carried by the plan record itself.
    events.push({
      id: `plan-${plan.id}`,
      kind: "planApproved",
      subject: `v${plan.version}`,
      occurredAt: new Date(plan.createdAt * 1000).toISOString(),
    });
    if (plan.sourceSessionId) {
      events.push({
        id: `assessment-${plan.sourceSessionId}`,
        kind: "assessmentCompleted",
        subject: null,
        occurredAt: new Date(plan.createdAt * 1000).toISOString(),
      });
    }
    for (const item of items) {
      if (item.status === "done" && item.completedAt !== null) {
        events.push({
          id: `action-${item.id}`,
          kind: "actionCompleted",
          subject: item.title,
          occurredAt: new Date(item.completedAt * 1000).toISOString(),
        });
      }
    }
  }

  if (status.state === "reviewDue" && status.reviewDueAt) {
    events.push({
      id: "review-due",
      kind: "reviewDue",
      subject: null,
      occurredAt: status.reviewDueAt,
    });
  }

  try {
    for (const evidence of await evidenceRepository.list(actor.tenantId)) {
      events.push({
        id: `evidence-${evidence.id}`,
        kind: "evidenceAdded",
        subject: evidence.title,
        occurredAt: evidence.createdAt,
      });
    }
  } catch (error) {
    // A role without evidence access contributes no evidence entries rather than emptying the
    // whole feed — the same discipline the older activity feed already follows.
    if (!(error instanceof ForbiddenError)) throw error;
  }

  return events
    .sort((a, b) => b.occurredAt.localeCompare(a.occurredAt))
    .slice(0, SHOWN);
}

/**
 * Real activity feed for the dashboard — this app has no dedicated domain-event/audit-log
 * store yet, so the feed is assembled from the timestamped, actor-attributed fields already
 * on the real records that exist (documents, analyses, policies, risks), sorted by time.
 * Tenant-scoped via each resource's own RBAC-gated service function; a role without read
 * access to one resource simply contributes no entries from it rather than failing the
 * whole feed.
 */

import type { ActorContext } from "@/lib/auth/actor";
import { ForbiddenError } from "@/lib/errors";
import { listDocuments } from "@/lib/documents/service";
import { listAnalyses } from "@/lib/analysis/service";
import { listPolicies } from "@/lib/policies/service";
import { listRisks } from "@/lib/risk/service";

export type ActivityActionKey =
  | "documentUploaded"
  | "analysisCompleted"
  | "analysisFailed"
  | "policyPublished"
  | "riskAccepted";

export type ActivityKind = "document" | "analysis" | "analysisFailed" | "policy" | "risk";

export interface ActivityItem {
  id: string;
  actorName: string;
  actionKey: ActivityActionKey;
  targetName: string;
  kind: ActivityKind;
  time: string;
  href: string;
}

/** Treats a `ForbiddenError` from an RBAC-gated list call as "no items" rather than a
 *  page-crashing failure — a role missing one permission shouldn't break the whole
 *  dashboard. Shared across the dashboard's real-data widgets. */
export async function safely<T>(fn: () => Promise<T[]>): Promise<T[]> {
  try {
    return await fn();
  } catch (error) {
    if (error instanceof ForbiddenError) return [];
    throw error;
  }
}

export async function getRecentActivity(actor: ActorContext, limit = 8): Promise<ActivityItem[]> {
  const [documents, analyses, policies, risks] = await Promise.all([
    safely(() => listDocuments(actor)),
    safely(() => listAnalyses(actor)),
    safely(() => listPolicies(actor)),
    safely(() => listRisks(actor)),
  ]);

  const items: ActivityItem[] = [];

  for (const d of documents) {
    items.push({
      id: `document-${d.id}`,
      actorName: d.uploadedByName,
      actionKey: "documentUploaded",
      targetName: d.fileName,
      kind: "document",
      time: d.createdAt,
      href: "/upload",
    });
  }

  for (const a of analyses) {
    if (a.status === "processed" && a.completedAt) {
      items.push({
        id: `analysis-${a.id}`,
        actorName: a.requestedByName,
        actionKey: "analysisCompleted",
        targetName: a.fileName,
        kind: "analysis",
        time: a.completedAt,
        href: `/analysis?doc=${a.documentId}`,
      });
    } else if (a.status === "failed") {
      items.push({
        id: `analysis-failed-${a.id}`,
        actorName: a.requestedByName,
        actionKey: "analysisFailed",
        targetName: a.fileName,
        kind: "analysisFailed",
        time: a.updatedAt,
        href: `/analysis?doc=${a.documentId}`,
      });
    }
  }

  for (const p of policies) {
    if (p.status === "published" && p.approvedAt && p.approvedByName) {
      items.push({
        id: `policy-${p.id}`,
        actorName: p.approvedByName,
        actionKey: "policyPublished",
        targetName: p.title,
        kind: "policy",
        time: p.approvedAt,
        href: "/policies",
      });
    }
  }

  for (const r of risks) {
    if (r.status === "accepted" && r.acceptedAt && r.acceptedByName) {
      items.push({
        id: `risk-${r.id}`,
        actorName: r.acceptedByName,
        actionKey: "riskAccepted",
        targetName: r.title,
        kind: "risk",
        time: r.acceptedAt,
        href: "/risk-register",
      });
    }
  }

  return items.sort((a, b) => b.time.localeCompare(a.time)).slice(0, limit);
}

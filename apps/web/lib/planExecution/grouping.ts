/**
 * Shared item-grouping/ranking logic (ADR 0066 §4, §8) — used identically by the live Plan Board
 * (`components/plan/PlanBoard.tsx`) and the pre-approval Governance Report
 * (`components/governance/GovernanceReport.tsx`) so "Quick Wins"/"Priority Roadmap"/"Timeline"
 * group the same item shape the same way in both places, before and after a plan is persisted.
 * Generic over any item shape carrying these four fields — a live `PlanItem` and the lighter
 * draft item shape the Report renders both satisfy it.
 */

import type { EffortSize, Priority, TimeframeBucket } from "./types";

export const TIMEFRAME_ORDER: TimeframeBucket[] = [
  "week_1",
  "week_2",
  "month_1",
  "month_3",
  "month_6",
  "year_1",
];

export const PRIORITY_ORDER: Priority[] = ["critical", "high", "medium", "low"];

export const PRIORITY_RANK: Record<Priority, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export type GroupBy = "timeline" | "priority" | "pillar";

export interface GroupableItem {
  pillar: string;
  priority: Priority;
  timeframeBucket: TimeframeBucket;
  dueAt: number | null;
}

/** Groups items by the chosen dimension, sorted within each group by priority then due date, and
 * orders the groups themselves (timeline/priority use the fixed ADR order; pillar is alphabetical
 * since there's no inherent pillar ranking). */
export function groupItems<T extends GroupableItem>(
  items: T[],
  groupBy: GroupBy,
): Array<[string, T[]]> {
  const buckets = new Map<string, T[]>();
  for (const item of items) {
    const key =
      groupBy === "timeline" ? item.timeframeBucket : groupBy === "priority" ? item.priority : item.pillar;
    const bucket = buckets.get(key);
    if (bucket) bucket.push(item);
    else buckets.set(key, [item]);
  }
  for (const bucket of buckets.values()) {
    bucket.sort((a, b) => {
      const byPriority = PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];
      if (byPriority !== 0) return byPriority;
      return (a.dueAt ?? Infinity) - (b.dueAt ?? Infinity);
    });
  }
  const order =
    groupBy === "timeline"
      ? TIMEFRAME_ORDER
      : groupBy === "priority"
        ? PRIORITY_ORDER
        : [...buckets.keys()].sort();
  return order.filter((key) => buckets.has(key)).map((key) => [key, buckets.get(key)!]);
}

export interface QuickWinCandidate {
  priority: Priority;
  effortSize: EffortSize;
  /** Absent entirely for draft (pre-approval) items — nothing can be "done" before a plan exists,
   * so the check degrades to just effort+priority in that case. */
  status?: string;
}

/** Small effort, high/critical urgency, not yet done (ADR 0066 §4) — the exact filter behind the
 * "Quick Wins" section, shared so the pre-approval Report and the live Plan Board agree on what
 * counts as a quick win. */
export function isQuickWin(item: QuickWinCandidate): boolean {
  return (
    (item.status === undefined || item.status === "not_started") &&
    item.effortSize === "small" &&
    (item.priority === "critical" || item.priority === "high")
  );
}

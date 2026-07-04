/**
 * Date-range selection — pure, dependency-free, safe to import from client components.
 * Kept separate from metrics.ts (which pulls in the Postgres-backed analysis repository)
 * so `DateRangeSelect.tsx` doesn't drag `pg` into the browser bundle.
 */

export const DASHBOARD_RANGE_DAYS = [7, 30, 90] as const;
export type DashboardRangeDays = (typeof DASHBOARD_RANGE_DAYS)[number];
export const DEFAULT_DASHBOARD_RANGE: DashboardRangeDays = 90;

export function parseDashboardRange(value: string | string[] | undefined): DashboardRangeDays {
  const raw = Array.isArray(value) ? value[0] : value;
  const parsed = Number(raw);
  return (DASHBOARD_RANGE_DAYS as readonly number[]).includes(parsed)
    ? (parsed as DashboardRangeDays)
    : DEFAULT_DASHBOARD_RANGE;
}

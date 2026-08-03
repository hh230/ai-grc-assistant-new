/**
 * The Mission record (CLAUDE.md §8) as apps/web reads it. Backed by `policy_missions` +
 * `policy_mission_steps` (0015_policy_missions.sql) — today the only Mission producer is the
 * Policy Intelligence pipeline (Policy Hunter/Analyst/Builder), so this stays a thin,
 * tenant-scoped read model rather than a generic cross-capability Mission Engine (that lives
 * in `v2/`'s Mission Engine, not yet integrated with apps/web — see the audit report).
 */

export const MISSION_STATUSES = [
  "planned",
  "executing",
  "completed",
  "failed",
  "cancelled",
] as const;
export type MissionStatus = (typeof MISSION_STATUSES)[number];

export function isMissionStatus(value: string): value is MissionStatus {
  return (MISSION_STATUSES as readonly string[]).includes(value);
}

export interface MissionStep {
  id: string;
  position: number;
  step: string;
  detail: string;
  citations: string[];
  createdAt: string;
}

export interface Mission {
  id: string;
  agent: string;
  goal: string;
  status: string;
  awaitingApproval: boolean;
  createdByName: string;
  createdAt: string;
  updatedAt: string;
  stepCount: number;
  lastStep: string | null;
}

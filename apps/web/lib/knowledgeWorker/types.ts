/** Domain types for the AI Worker Control Center (Knowledge Intelligence KI-P5, ADR-0029) —
 * camelCase mirrors of apps/api's `/knowledge-worker/*` response shapes. */

export type WorkerCycleState = "idle" | "in_progress";

export interface WorkerStatus {
  enabled: boolean;
  running: boolean;
  currentCycle: WorkerCycleState;
  currentTask: string | null;
  intervalHours: number;
  manualTriggerRequested: boolean;
  lastRunAt: string | null;
  lastRunReason: string | null;
  nextRunAt: string | null;
  updatedBy: string | null;
  updatedAt: string;
}

export type WorkerEventType =
  | "cycle_started"
  | "questions_loaded"
  | "gap_detected"
  | "source_searched"
  | "knowledge_discovered"
  | "item_saved"
  | "error"
  | "cycle_completed"
  | "worker_enabled"
  | "worker_disabled"
  | "interval_changed"
  | "manual_trigger_requested";

export interface WorkerEvent {
  id: string;
  eventType: WorkerEventType;
  questionId: string | null;
  message: string;
  metadata: Record<string, string>;
  actorUserId: string | null;
  actorTenantId: string | null;
  occurredAt: string;
}

export interface WorkerRun {
  id: string;
  reason: string;
  startedAt: string;
  completedAt: string | null;
  questionsConsidered: number;
  gapsDetected: number;
  itemsSaved: number;
  errorCount: number;
}

export interface LearningReports {
  totalItems: number;
  verified: number;
  needsReview: number;
  outdated: number;
  discovered: number;
  addedThisCycle: number;
  updated: number;
}

export interface ScheduleUpdate {
  enabled?: boolean;
  intervalHours?: number;
}

export interface WorkerControl {
  id: string;
  enabled: boolean;
  intervalHours: number;
  manualTriggerRequestedAt: string | null;
  updatedAt: string;
  updatedBy: string | null;
}

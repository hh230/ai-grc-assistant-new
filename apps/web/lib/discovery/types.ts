/**
 * Discovery domain types (ADR 0066) — the shapes `lib/discovery/service.ts` returns to route
 * handlers and, from there, to the interview UI. Deliberately jargon-free at this boundary: no
 * "Signal"/"Framework"/"Rule" concept crosses into the frontend, only what a question needs to be
 * rendered and answered.
 */

export type QuestionValueType =
  | "boolean"
  | "enum"
  | "numeric"
  | "date"
  | "percentage"
  | "text"
  | "evidence_backed";

export type QuestionUiHint = "dropdown" | "buttons" | "chips" | "number" | "date" | "short_text";

export interface DiscoveryQuestion {
  id: string;
  promptKey: string;
  valueType: QuestionValueType;
  options: string[] | null;
  uiHint: QuestionUiHint | null;
  allowMultiple: boolean;
  required: boolean;
  stage: string;
}

export interface DiscoveryProgress {
  stage: string;
  stageIndex: number;
  stageCount: number;
}

export type DiscoverySessionStatus = "in_progress" | "concluded" | "abandoned";

export interface DiscoveryTurn {
  sessionId: string;
  status: DiscoverySessionStatus;
  question: DiscoveryQuestion | null;
  progress: DiscoveryProgress | null;
}

export interface DiscoveryGoBackTarget {
  question: DiscoveryQuestion;
  previousAnswer: unknown;
}

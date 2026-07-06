import {
  CheckCircle2,
  Clock,
  FileCheck2,
  ListChecks,
  Power,
  PowerOff,
  ScanSearch,
  Search,
  Sparkles,
  TriangleAlert,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { Tone } from "@/lib/design/tone";
import type { WorkerEventType } from "@/lib/knowledgeWorker/types";

/** Icon + tone per operational event type — the activity timeline never renders raw model
 * reasoning, only these already-public, structured facts (CLAUDE.md §19). */
export const EVENT_META: Record<WorkerEventType, { icon: LucideIcon; tone: Tone }> = {
  cycle_started: { icon: Clock, tone: "accent" },
  questions_loaded: { icon: ListChecks, tone: "neutral" },
  gap_detected: { icon: ScanSearch, tone: "warning" },
  source_searched: { icon: Search, tone: "neutral" },
  knowledge_discovered: { icon: Sparkles, tone: "accent" },
  item_saved: { icon: FileCheck2, tone: "success" },
  error: { icon: TriangleAlert, tone: "danger" },
  cycle_completed: { icon: CheckCircle2, tone: "success" },
  worker_enabled: { icon: Power, tone: "success" },
  worker_disabled: { icon: PowerOff, tone: "warning" },
  interval_changed: { icon: Clock, tone: "accent" },
  manual_trigger_requested: { icon: Zap, tone: "accent" },
};

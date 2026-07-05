/** Tone mappings for Policy Intelligence's severity/category vocabularies, composed from the
 * shared tone system (`lib/design/tone.ts`) rather than hand-rolled per component — the same
 * pattern `RiskRegister`'s severity badges use. */

import type { Tone } from "@/lib/design/tone";
import type { GapCategory, ObligationSeverity } from "./types";

export const SEVERITY_TONE: Record<ObligationSeverity, Tone> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "neutral",
  informational: "neutral",
};

export const GAP_CATEGORY_TONE: Record<GapCategory, Tone> = {
  unmapped_regulatory_obligation: "danger",
  missing_required_policy: "danger",
  incomplete_coverage: "warning",
  outdated_policy: "warning",
};

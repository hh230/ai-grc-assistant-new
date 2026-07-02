import type { ComponentType } from "react";
import type { AnalysisRecord } from "@/lib/analysis/types";

export interface AnalysisModuleProps {
  analysis: AnalysisRecord;
}

/** A category-specific set of sections rendered into the adaptive-layout slot. */
export type AnalysisModule = ComponentType<AnalysisModuleProps>;

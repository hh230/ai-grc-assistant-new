import { StrengthsWeaknesses } from "@/components/analysis/StrengthsWeaknesses";
import { FrameworkChecks } from "@/components/analysis/FrameworkChecks";
import { Recommendations } from "@/components/analysis/Recommendations";
import { FindingsList } from "@/components/analysis/FindingsList";
import type { DocumentCategory } from "@/lib/documents/types";
import type { AnalysisModule, AnalysisModuleProps } from "./types";

/**
 * Today's generic findings/recommendations view — used by every category without a
 * bespoke override below, so this is what every document renders right now.
 */
function DefaultModule({ analysis }: AnalysisModuleProps) {
  return (
    <>
      <StrengthsWeaknesses strengths={analysis.strengths} weaknesses={analysis.weaknesses} />
      <FrameworkChecks frameworks={analysis.frameworks} />
      <Recommendations recommendations={analysis.recommendations} />
      <FindingsList findings={analysis.findings} />
    </>
  );
}

/**
 * Adaptive-layout registry (V2-P3 design proposal §8/§12) — Framework-Engine-style
 * extensibility: category-specific analysis sections (e.g. Contracts -> Legal Review /
 * Missing Clauses / Contract Risks) are added here as they're built, keyed by
 * `DocumentCategory` (`lib/documents/types.ts`). No other file needs to change to add one.
 *
 * Empty today — every category resolves to `DefaultModule`, so this phase ships the slot
 * with zero visible change. The four example modules from the design proposal are future
 * scope, not built here.
 */
const CATEGORY_MODULES: Partial<Record<DocumentCategory, AnalysisModule>> = {};

export function getAnalysisModule(category: DocumentCategory | undefined): AnalysisModule {
  if (category && CATEGORY_MODULES[category]) return CATEGORY_MODULES[category];
  return DefaultModule;
}

import { ComplianceOverview } from "@/components/analysis/ComplianceOverview";
import { StrengthsWeaknesses } from "@/components/analysis/StrengthsWeaknesses";
import { FrameworkChecks } from "@/components/analysis/FrameworkChecks";
import { FindingsList } from "@/components/analysis/FindingsList";
import { CriticalRisks } from "@/components/analysis/CriticalRisks";
import { GapAnalysis } from "@/components/analysis/GapAnalysis";
import { Recommendations } from "@/components/analysis/Recommendations";
import { ImpactAndPriority } from "@/components/analysis/ImpactAndPriority";
import { References } from "@/components/analysis/References";
import { NextActions } from "@/components/analysis/NextActions";
import type { DocumentCategory } from "@/lib/documents/types";
import type { AnalysisModule, AnalysisModuleProps } from "./types";

/**
 * Today's generic consulting-report view — used by every category without a bespoke
 * override below, so this is what every document renders right now. Section order follows
 * the V2 Production Polish report structure: Compliance Overview, Framework Alignment,
 * Strengths/Weaknesses, Key Findings, Critical Risks, Gap Analysis, Recommended Changes,
 * Business Impact & Priority, References, Next Actions. (Executive Summary renders above
 * this module, in AnalysisDetail.)
 */
function DefaultModule({ analysis }: AnalysisModuleProps) {
  return (
    <>
      <ComplianceOverview overview={analysis.complianceOverview} />
      <FrameworkChecks frameworks={analysis.frameworks} />
      <StrengthsWeaknesses strengths={analysis.strengths} weaknesses={analysis.weaknesses} />
      <FindingsList findings={analysis.findings} />
      <CriticalRisks risks={analysis.criticalRisks} />
      <GapAnalysis gaps={analysis.gaps} />
      <Recommendations recommendations={analysis.recommendations} />
      <ImpactAndPriority
        businessImpact={analysis.businessImpact}
        priority={analysis.overallPriority}
      />
      <References references={analysis.references} />
      <NextActions actions={analysis.nextActions} />
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

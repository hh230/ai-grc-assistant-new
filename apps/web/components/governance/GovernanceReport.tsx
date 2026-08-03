"use client";

import { useTranslations } from "next-intl";
import { CheckCircle2, Loader2, Sparkles, TrendingUp } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { MaturityStars } from "./MaturityStars";
import {
  CriticalGapsSection,
  BusinessImpactSection,
} from "./ReportGapsSection";
import {
  ActionTasksSection,
  PriorityRoadmapSection,
  QuickWinsSection,
  TimelineSection,
} from "./ReportItemGroups";
import { MethodologySection } from "./ReportMethodology";
import { GovernanceVisionSection } from "./ReportVision";
import { MATURITY_DIMENSION_ORDER } from "@/lib/planExecution/types";
import type { GovernanceReportDraft } from "@/lib/planGeneration/types";

interface GovernanceReportProps {
  report: GovernanceReportDraft;
  canApprove: boolean;
  approving: boolean;
  approveError: string | null;
  onApprove: () => void;
}

/**
 * The full 10-section consulting-style report (ADR 0066 §4), sourced from the `generate_governance_
 * plan` Mission's `draft_plan` output while it waits at the ADR 0044 human-approval gate. This
 * replaces the Phase-2 `DiscoveryResultPreview` stopgap entirely — one Report, not a preview plus
 * a "real" version later. Ends in the one action that actually crosses the gate.
 */
export function GovernanceReport({
  report,
  canApprove,
  approving,
  approveError,
  onApprove,
}: GovernanceReportProps) {
  const t = useTranslations("governanceReport");

  return (
    <div className="space-y-5">
      {/* 1. AI Executive Brief */}
      <Card grain>
        <div className="mb-2 flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-accent-foreground" strokeWidth={1.75} />
          <h3 className="text-sm font-medium text-foreground">{t("executiveBrief.title")}</h3>
        </div>
        <p className="text-sm leading-relaxed text-foreground-secondary">{report.executiveSummary}</p>
      </Card>

      {/* 2. Current Maturity */}
      <Card>
        <div className="mb-3 flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-accent-foreground" strokeWidth={1.75} />
          <h3 className="text-sm font-medium text-foreground">{t("currentMaturity.title")}</h3>
        </div>
        <ul className="space-y-2.5">
          {MATURITY_DIMENSION_ORDER.map((dimension) => {
            const rating = report.maturityBaseline[dimension];
            if (!rating) return null;
            return (
              <li key={dimension} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-foreground-secondary">{t(`dimensions.${dimension}` as never)}</span>
                <span className="flex items-center gap-2">
                  <MaturityStars stars={rating.stars} />
                  <Badge tone="neutral">{t(`maturityLabels.${rating.label}` as never)}</Badge>
                </span>
              </li>
            );
          })}
        </ul>
      </Card>

      {/* 3–4. Critical Gaps / Business Impact */}
      <CriticalGapsSection topRisks={report.topRisks} />
      <BusinessImpactSection topRisks={report.topRisks} />

      {/* 5–8. Quick Wins / Priority Roadmap / Timeline / Action Tasks */}
      <QuickWinsSection items={report.items} />
      <PriorityRoadmapSection items={report.items} />
      <TimelineSection items={report.items} />
      <ActionTasksSection items={report.items} />

      {/* 9. Methodology & Standards */}
      <MethodologySection frameworks={report.inferredFrameworks} />

      {/* 10. Governance Vision */}
      <GovernanceVisionSection baseline={report.maturityBaseline} vision={report.maturityVision} />

      {/* Approve & Activate — the ADR 0044 human-approval gate, made visible */}
      <Card grain className="flex flex-col items-center gap-3 py-8 text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-elevated shadow-soft">
          <CheckCircle2 className="h-5 w-5 text-accent-foreground" strokeWidth={1.75} />
        </div>
        <div className="max-w-md space-y-1.5">
          <p className="text-sm font-medium text-foreground">{t("approve.title")}</p>
          <p className="text-xs text-foreground-muted">
            {canApprove ? t("approve.description") : t("approve.noPermission")}
          </p>
        </div>
        {approveError && <p className="text-sm text-danger">{approveError}</p>}
        <button
          type="button"
          disabled={!canApprove || approving}
          onClick={onApprove}
          className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {approving && <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />}
          {t("approve.cta")}
        </button>
      </Card>
    </div>
  );
}

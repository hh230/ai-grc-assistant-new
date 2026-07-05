"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  ExternalLink,
  ListChecks,
  Loader2,
  ScanSearch,
  SearchCheck,
  ShieldQuestion,
} from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { usePolicies } from "@/hooks/usePolicies";
import {
  useCoverageGaps,
  useObligations,
  usePolicyQualityReview,
} from "@/hooks/usePolicyIntelligence";
import { GAP_CATEGORY_TONE, SEVERITY_TONE } from "@/lib/policyIntelligence/tone";
import type {
  GapFinding,
  ObligationEvidence,
  ObligationSeverity,
  QualityFinding,
} from "@/lib/policyIntelligence/types";
import { cn } from "@/lib/utils";

type View = "obligations" | "coverage-gaps" | "quality-review";

const CONTROL_DOMAINS = [
  "governance",
  "risk_management",
  "access_control",
  "data_protection",
  "asset_management",
  "physical_security",
  "human_resources_security",
  "incident_management",
  "business_continuity",
  "third_party_management",
  "compliance_monitoring",
  "other",
] as const;

function confidencePct(confidence: number): string {
  return `${Math.round(confidence * 100)}%`;
}

const selectClass =
  "h-9 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground outline-none focus:border-hairline-strong";

export function PolicyIntelligenceWorkspace() {
  const t = useTranslations("policyIntelligenceWorkspace");
  const [view, setView] = useState<View>("obligations");

  const views: { key: View; label: string; icon: typeof ListChecks }[] = [
    { key: "obligations", label: t("tabs.obligations"), icon: ListChecks },
    { key: "coverage-gaps", label: t("tabs.coverageGaps"), icon: ScanSearch },
    { key: "quality-review", label: t("tabs.qualityReview"), icon: SearchCheck },
  ];

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        {views.map(({ key, label, icon: Icon }) => {
          const active = key === view;
          return (
            <button
              key={key}
              type="button"
              onClick={() => setView(key)}
              className={cn(
                "flex items-center gap-2.5 rounded-xl border px-4 py-3 text-start transition-colors",
                active
                  ? "border-accent/40 bg-accent-soft text-accent-foreground"
                  : "border-hairline bg-surface text-foreground-secondary hover:border-hairline-strong",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
              <span className="text-sm font-medium">{label}</span>
            </button>
          );
        })}
      </div>

      {view === "obligations" && <ObligationsView />}
      {view === "coverage-gaps" && <CoverageGapsView />}
      {view === "quality-review" && <QualityReviewView />}
    </div>
  );
}

function ControlDomainFilter({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const t = useTranslations("policyIntelligenceWorkspace");
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className={selectClass}>
      <option value="">{t("filters.allControlDomains")}</option>
      {CONTROL_DOMAINS.map((domain) => (
        <option key={domain} value={domain}>
          {t(`controlDomain.${domain}`)}
        </option>
      ))}
    </select>
  );
}

function SeverityBadge({ severity }: { severity: ObligationSeverity }) {
  const t = useTranslations("policyIntelligenceWorkspace");
  return <Badge tone={SEVERITY_TONE[severity]}>{t(`severity.${severity}`)}</Badge>;
}

function CitationLink({ sourceUrl, citation }: { sourceUrl: string; citation: string }) {
  return (
    <a
      href={sourceUrl}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-2xs text-accent-foreground hover:underline"
    >
      {citation}
      <ExternalLink className="h-3 w-3" strokeWidth={1.75} />
    </a>
  );
}

function LoadingCard({ label }: { label: string }) {
  return (
    <Card className="flex items-center justify-center gap-2 py-12 text-sm text-foreground-muted">
      <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
      {label}
    </Card>
  );
}

function ErrorCard({ message }: { message: string }) {
  return <Card className="py-10 text-center text-sm text-danger">{message}</Card>;
}

function EmptyCard({ title, description }: { title: string; description: string }) {
  return (
    <Card grain className="flex flex-col items-center gap-3 py-14 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2">
        <ShieldQuestion className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-xs text-foreground-muted">{description}</p>
      </div>
    </Card>
  );
}

function ObligationsView() {
  const t = useTranslations("policyIntelligenceWorkspace");
  const [controlDomain, setControlDomain] = useState("");
  const { data, isLoading, isError, error } = useObligations(controlDomain || undefined);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-2xs text-foreground-muted">
          {t("obligationCount", { count: data?.length ?? 0 })}
        </p>
        <ControlDomainFilter value={controlDomain} onChange={setControlDomain} />
      </div>

      {isLoading ? (
        <LoadingCard label={t("loadingObligations")} />
      ) : isError ? (
        <ErrorCard message={(error as Error)?.message ?? t("loadFailed")} />
      ) : !data || data.length === 0 ? (
        <EmptyCard
          title={t("obligationsEmptyTitle")}
          description={t("obligationsEmptyDescription")}
        />
      ) : (
        <div className="grid gap-3">
          {data.map((obligation) => (
            <ObligationCard key={obligation.obligationId} obligation={obligation} />
          ))}
        </div>
      )}
    </div>
  );
}

function ObligationCard({ obligation }: { obligation: ObligationEvidence }) {
  const t = useTranslations("policyIntelligenceWorkspace");
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={obligation.severity} />
            <Badge tone="neutral">{t(`controlDomain.${obligation.controlDomain}`)}</Badge>
          </div>
          <p className="text-sm text-foreground">{obligation.obligationText}</p>
          <p className="text-2xs text-foreground-muted">
            {t("suggestedPolicy", { title: obligation.suggestedPolicyTitle })}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5 text-end">
          <span className="text-2xs text-foreground-muted">
            {t("confidence", { value: confidencePct(obligation.classificationConfidence) })}
          </span>
          <CitationLink sourceUrl={obligation.sourceUrl} citation={obligation.citation} />
        </div>
      </div>
    </Card>
  );
}

function CoverageGapsView() {
  const t = useTranslations("policyIntelligenceWorkspace");
  const [controlDomain, setControlDomain] = useState("");
  const { data, isLoading, isError, error } = useCoverageGaps(controlDomain || undefined);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-2xs text-foreground-muted">
          {data
            ? t("coverageSummary", {
                scanned: data.obligationsScanned,
                policies: data.policiesConsidered,
                gaps: data.findings.length,
              })
            : ""}
        </p>
        <ControlDomainFilter value={controlDomain} onChange={setControlDomain} />
      </div>

      {isLoading ? (
        <LoadingCard label={t("loadingCoverageGaps")} />
      ) : isError ? (
        <ErrorCard message={(error as Error)?.message ?? t("loadFailed")} />
      ) : !data || data.findings.length === 0 ? (
        <EmptyCard
          title={t("coverageGapsEmptyTitle")}
          description={t("coverageGapsEmptyDescription")}
        />
      ) : (
        <div className="grid gap-3">
          {data.findings.map((finding) => (
            <GapFindingCard key={`${finding.obligationId}-${finding.gapCategory}`} finding={finding} />
          ))}
        </div>
      )}
    </div>
  );
}

function GapFindingCard({ finding }: { finding: GapFinding }) {
  const t = useTranslations("policyIntelligenceWorkspace");
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1.5">
          <Badge tone={GAP_CATEGORY_TONE[finding.gapCategory]}>
            {t(`gapCategory.${finding.gapCategory}`)}
          </Badge>
          <p className="text-sm text-foreground">{finding.rationale}</p>
          <p className="text-2xs text-foreground-muted">
            {finding.matchedPolicyTitle
              ? t("matchedPolicy", { title: finding.matchedPolicyTitle })
              : t("noMatchedPolicy")}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5 text-end">
          <span className="text-2xs text-foreground-muted">
            {t("confidence", { value: confidencePct(finding.confidence) })}
          </span>
          <CitationLink sourceUrl={finding.sourceUrl} citation={finding.citation} />
        </div>
      </div>
    </Card>
  );
}

function QualityReviewView() {
  const t = useTranslations("policyIntelligenceWorkspace");
  const { data: policies, isLoading: policiesLoading } = usePolicies();
  const [policyId, setPolicyId] = useState<string | null>(null);
  const { data, isLoading, isError, error } = usePolicyQualityReview(policyId);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-2xs text-foreground-muted">{t("selectPolicyLabel")}</p>
        <select
          value={policyId ?? ""}
          onChange={(e) => setPolicyId(e.target.value || null)}
          className={selectClass}
          disabled={policiesLoading || !policies || policies.length === 0}
        >
          <option value="">{t("selectPolicyPlaceholder")}</option>
          {policies?.map((policy) => (
            <option key={policy.id} value={policy.id}>
              {policy.title}
            </option>
          ))}
        </select>
      </div>

      {!policyId ? (
        <EmptyCard
          title={t("qualityReviewEmptyTitle")}
          description={t("qualityReviewEmptyDescription")}
        />
      ) : isLoading ? (
        <LoadingCard label={t("loadingQualityReview")} />
      ) : isError ? (
        <ErrorCard message={(error as Error)?.message ?? t("loadFailed")} />
      ) : !data || data.findings.length === 0 ? (
        <EmptyCard
          title={t("qualityReviewNoFindingsTitle")}
          description={t("qualityReviewNoFindingsDescription")}
        />
      ) : (
        <div className="space-y-3">
          <p className="text-2xs text-foreground-muted">
            {t("obligationsConsidered", { count: data.obligationsConsidered })}
          </p>
          <div className="grid gap-3">
            {data.findings.map((finding, index) => (
              <QualityFindingCard key={`${finding.findingType}-${index}`} finding={finding} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function QualityFindingCard({ finding }: { finding: QualityFinding }) {
  const t = useTranslations("policyIntelligenceWorkspace");
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={finding.severity} />
            <Badge tone="neutral">{t(`findingType.${finding.findingType}`)}</Badge>
          </div>
          <p className="text-sm text-foreground">{finding.evidence}</p>
          <p className="text-2xs text-foreground-secondary">
            {t("recommendation", { text: finding.recommendation })}
          </p>
          {finding.relatedObligationId && (
            <p className="text-2xs text-foreground-muted">
              {t("relatedObligation", { id: finding.relatedObligationId })}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5 text-end">
          <span className="text-2xs text-foreground-muted">
            {t("confidence", { value: confidencePct(finding.confidence) })}
          </span>
          <span className="text-2xs text-foreground-muted">{finding.citation}</span>
        </div>
      </div>
    </Card>
  );
}

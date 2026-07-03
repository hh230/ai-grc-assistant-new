"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, FileText, Loader2, RefreshCw, Sparkles } from "lucide-react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Card } from "@/components/ui/Card";
import { DocumentStatusBadge } from "@/components/documents/DocumentStatusBadge";
import { AnalysisScoreCards } from "@/components/analysis/AnalysisScoreCards";
import { VersionHistory } from "@/components/analysis/VersionHistory";
import { useAnalysisVersions, useStartAnalysis } from "@/hooks/useAnalyses";
import { useDocuments } from "@/hooks/useDocuments";
import { getAnalysisModule } from "@/lib/analysis/modules/registry";
import type { AnalysisRecord } from "@/lib/analysis/types";
import { recordVisit } from "@/lib/workspace/recentlyViewed";
import { formatNumber } from "@/lib/utils";

const PIPELINE_STEP_KEYS = ["parse", "chunk", "embed", "index", "assess", "score"] as const;

export function AnalysisDetail({ documentId, canRun }: { documentId: string; canRun: boolean }) {
  const t = useTranslations("analysisDetail");
  const { data: versions, isLoading } = useAnalysisVersions(documentId);
  const start = useStartAnalysis(documentId);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const latest = versions?.[0] ?? null;
  const selected = versions?.find((v) => v.id === selectedId) ?? latest;

  // Follow the latest version by default (e.g. right after starting a new run); the user can
  // still pick an older version from the history panel below.
  useEffect(() => {
    if (latest && !selectedId) setSelectedId(latest.id);
  }, [latest, selectedId]);

  if (isLoading) {
    return (
      <Card className="flex items-center justify-center gap-2 py-16 text-sm text-foreground-muted">
        <Loader2 className="h-4 w-4 animate-spin" strokeWidth={1.75} />
        {t("loading")}
      </Card>
    );
  }

  // Not yet analyzed
  if (!selected) {
    return (
      <Card grain className="flex flex-col items-center gap-4 py-16 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2">
          <Sparkles className="h-5 w-5 text-accent-foreground" strokeWidth={1.75} />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">
            {t("emptyTitle")}
          </p>
          <p className="max-w-sm text-xs text-foreground-muted">
            {t("emptyDescription")}
          </p>
        </div>
        {canRun && (
          <RunButton
            onClick={() => start.mutate()}
            pending={start.isPending}
            label={t("runAnalysis")}
          />
        )}
        {start.isError && <p className="text-2xs text-danger">{(start.error as Error).message}</p>}
      </Card>
    );
  }

  if (selected.status === "processing" || selected.status === "queued") {
    return (
      <Card grain className="flex flex-col items-center gap-4 py-16 text-center">
        <Loader2 className="h-7 w-7 animate-spin text-accent-foreground" strokeWidth={1.5} />
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">{t("analyzing", { name: selected.fileName })}</p>
          <p className="text-xs text-foreground-muted">
            {t("analyzingDescription")}
          </p>
        </div>
        <div className="flex flex-wrap justify-center gap-1.5 text-2xs text-foreground-muted">
          {PIPELINE_STEP_KEYS.map((step) => (
            <span
              key={step}
              className="rounded-full border border-hairline bg-surface/60 px-2 py-0.5"
            >
              {t(`pipelineSteps.${step}`)}
            </span>
          ))}
        </div>
      </Card>
    );
  }

  if (selected.status === "failed") {
    return (
      <Card className="flex flex-col items-center gap-4 py-14 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-danger/30 bg-danger-soft">
          <AlertTriangle className="h-5 w-5 text-danger" strokeWidth={1.75} />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">{t("analysisFailed")}</p>
          <p className="max-w-md text-xs text-danger">
            {selected.error ?? t("unexpectedError")}
          </p>
        </div>
        {canRun && (
          <RunButton
            onClick={() => start.mutate()}
            pending={start.isPending}
            label={t("retryAnalysis")}
          />
        )}
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <ProcessedAnalysis analysis={selected} canRun={canRun} onRerun={() => start.mutate()} pending={start.isPending} />
      {versions && versions.length > 1 && (
        <VersionHistory
          documentId={documentId}
          versions={versions}
          selectedId={selected.id}
          onSelect={setSelectedId}
        />
      )}
    </div>
  );
}

function ProcessedAnalysis({
  analysis,
  canRun,
  onRerun,
  pending,
}: {
  analysis: AnalysisRecord;
  canRun: boolean;
  onRerun: () => void;
  pending: boolean;
}) {
  const t = useTranslations("analysisDetail");
  // Adaptive-layout slot (design proposal §8/§12): selects the section set for this
  // document's category. Empty registry today, so every category renders the same
  // generic module DefaultModule already did — this lookup has zero visible effect
  // until a category-specific module is registered.
  const { data: documents } = useDocuments();
  const category = documents?.find((doc) => doc.id === analysis.documentId)?.category;
  const Module = getAnalysisModule(category);

  useEffect(() => {
    recordVisit({
      id: analysis.documentId,
      type: "analysis",
      title: analysis.title,
      subtitle: `v${analysis.version}`,
      href: `/analysis?doc=${analysis.documentId}`,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysis.id]);

  return (
    <div className="space-y-5">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-hairline bg-surface-2">
              <FileText className="h-4 w-4 text-foreground-secondary" strokeWidth={1.75} />
            </span>
            <div>
              <p className="text-sm font-semibold text-foreground">{analysis.title}</p>
              <p className="text-2xs text-foreground-muted">
                {t("analyzedBy", { name: analysis.requestedByName })}
                {analysis.durationMs ? ` · ${t("durationSuffix", { seconds: (analysis.durationMs / 1000).toFixed(1) })}` : ""}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <DocumentStatusBadge status={analysis.status} />
            {canRun && (
              <RunButton onClick={onRerun} pending={pending} label={t("rerunAnalysis")} compact />
            )}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metric
            label={t("metrics.pages")}
            value={analysis.pageCount ? formatNumber(analysis.pageCount) : "—"}
          />
          <Metric label={t("metrics.chunksIndexed")} value={formatNumber(analysis.chunkCount)} />
          <Metric label={t("metrics.characters")} value={formatNumber(analysis.charCount)} />
          <Metric label={t("metrics.findings")} value={formatNumber(analysis.findings.length)} />
        </div>
      </Card>

      <AnalysisScoreCards
        complianceScore={analysis.complianceScore}
        riskScore={analysis.riskScore}
        maturityLevel={analysis.maturityLevel}
        findings={analysis.findings}
      />

      {analysis.executiveSummary && (
        <Card>
          <h2 className="text-sm font-semibold tracking-tight text-foreground">
            {t("executiveSummary")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-foreground-secondary">
            {analysis.executiveSummary}
          </p>
          {analysis.keyTerms.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {analysis.keyTerms.map((term) => (
                <span
                  key={term}
                  className="rounded-full border border-hairline bg-surface/60 px-2 py-0.5 text-2xs text-foreground-secondary"
                >
                  {term}
                </span>
              ))}
            </div>
          )}
        </Card>
      )}

      <Module analysis={analysis} />

      <div className="flex items-center gap-3">
        <Link
          href="/upload"
          className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground"
        >
          <FileText className="h-4 w-4" strokeWidth={1.75} />
          {t("backToDocuments")}
        </Link>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-hairline bg-surface/40 px-3 py-2.5">
      <p className="text-lg font-semibold tracking-tight text-foreground">{value}</p>
      <p className="text-2xs text-foreground-muted">{label}</p>
    </div>
  );
}

function RunButton({
  onClick,
  pending,
  label,
  compact = false,
}: {
  onClick: () => void;
  pending: boolean;
  label: string;
  compact?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending}
      className={
        compact
          ? "inline-flex h-8 items-center gap-1.5 rounded-lg border border-hairline bg-surface px-2.5 text-2xs font-medium text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:text-foreground disabled:opacity-60"
          : "inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-3.5 text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98] disabled:opacity-60"
      }
    >
      {pending ? (
        <Loader2 className={compact ? "h-3.5 w-3.5 animate-spin" : "h-4 w-4 animate-spin"} strokeWidth={2} />
      ) : (
        <RefreshCw className={compact ? "h-3.5 w-3.5" : "h-4 w-4"} strokeWidth={2} />
      )}
      {label}
    </button>
  );
}

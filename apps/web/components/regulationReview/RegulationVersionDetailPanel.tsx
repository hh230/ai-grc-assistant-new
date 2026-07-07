"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Loader2, X } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  useApproveRegulationVersion,
  useRegulationVersionDetail,
  useRejectRegulationVersion,
} from "@/hooks/useRegulationReview";
import type { RegulationSection } from "@/lib/regulationReview/types";

interface RegulationVersionDetailPanelProps {
  versionId: string | null;
  onDecided: () => void;
}

function SectionRow({ section }: { section: RegulationSection }) {
  const isChapter = section.sectionType === "chapter";
  return (
    <li className={isChapter ? "pt-3 first:pt-0" : "py-2 ps-4"}>
      {isChapter ? (
        <p className="text-xs font-semibold uppercase tracking-wide text-foreground-muted">
          {section.code}
          {section.titleAr ? ` — ${section.titleAr}` : ""}
        </p>
      ) : (
        <div className="rounded-lg border border-hairline bg-surface-elevated p-3">
          <p className="text-xs font-medium text-foreground-muted">{section.code}</p>
          {section.textAr && (
            <p className="mt-1 text-sm text-foreground" dir="rtl">
              {section.textAr}
            </p>
          )}
          {section.amendmentNoteAr && (
            <p className="mt-2 text-xs text-foreground-muted" dir="rtl">
              {section.amendmentNoteAr}
            </p>
          )}
        </div>
      )}
    </li>
  );
}

export function RegulationVersionDetailPanel({
  versionId,
  onDecided,
}: RegulationVersionDetailPanelProps) {
  const t = useTranslations("regulationReviewWorkspace.detail");
  const { data: detail, isLoading } = useRegulationVersionDetail(versionId);
  const approveMutation = useApproveRegulationVersion();
  const rejectMutation = useRejectRegulationVersion();
  const [feedback, setFeedback] = useState<string | null>(null);

  if (!versionId) {
    return (
      <Card>
        <p className="text-sm text-foreground-secondary">{t("empty")}</p>
      </Card>
    );
  }

  if (isLoading || !detail) {
    return (
      <Card>
        <Skeleton className="h-64 w-full" />
      </Card>
    );
  }

  const handleApprove = async () => {
    setFeedback(null);
    const result = await approveMutation.mutateAsync(versionId);
    setFeedback(
      t("approvedFeedback", {
        embedded: result.sectionsEmbedded,
        failed: result.sectionsFailed,
      }),
    );
    onDecided();
  };

  const handleReject = async () => {
    setFeedback(null);
    await rejectMutation.mutateAsync(versionId);
    onDecided();
  };

  const allSections = detail.documents.flatMap((document) => document.sections);
  const articleCount = allSections.filter((section) => section.sectionType === "article").length;

  return (
    <Card flush>
      <div className="border-b border-hairline p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
              {detail.source.authority}
            </p>
            <h2 className="mt-1 text-sm font-semibold text-foreground">{detail.source.titleAr}</h2>
            {detail.source.titleEn && (
              <p className="mt-0.5 text-xs text-foreground-muted">{detail.source.titleEn}</p>
            )}
          </div>
          <Badge tone="warning">{detail.status}</Badge>
        </div>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-2xs text-foreground-muted sm:grid-cols-3">
          <div>
            <dt>{t("versionLabel")}</dt>
            <dd className="font-medium text-foreground">{detail.versionLabel}</dd>
          </div>
          <div>
            <dt>{t("articleCount")}</dt>
            <dd className="font-medium text-foreground">{articleCount}</dd>
          </div>
          {detail.officialCitation && (
            <div className="col-span-2 sm:col-span-1">
              <dt>{t("officialCitation")}</dt>
              <dd className="font-medium text-foreground">{detail.officialCitation}</dd>
            </div>
          )}
        </dl>
      </div>

      <div className="max-h-[28rem] overflow-y-auto p-5">
        {detail.documents.map((document) => (
          <ul key={document.id} className="divide-y divide-hairline">
            {document.sections.map((section) => (
              <SectionRow key={section.id} section={section} />
            ))}
          </ul>
        ))}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-hairline p-5">
        {feedback ? (
          <p className="text-xs text-foreground-secondary">{feedback}</p>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleReject}
            disabled={rejectMutation.isPending || approveMutation.isPending}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline px-4 text-sm font-medium text-foreground-secondary transition-colors hover:bg-surface-elevated disabled:cursor-not-allowed disabled:opacity-50"
          >
            {rejectMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <X className="h-4 w-4" strokeWidth={1.75} />
            )}
            {t("reject")}
          </button>
          <button
            type="button"
            onClick={handleApprove}
            disabled={approveMutation.isPending || rejectMutation.isPending}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-accent px-4 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {approveMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" strokeWidth={1.75} />
            )}
            {t("approve")}
          </button>
        </div>
      </div>
    </Card>
  );
}

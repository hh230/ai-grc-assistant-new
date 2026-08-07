import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { getActor } from "@/lib/auth/actor";
import { requireSession } from "@/lib/auth/server";
import { NotFoundError } from "@/lib/errors";
import { pageTitle } from "@/lib/pageMetadata";
import { Link } from "@/i18n/navigation";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import {
  getActiveReleaseId,
  getRelease,
  isKnowledgeApprover,
  listActivations,
} from "@/lib/knowledge/service";
import { NotKnowledgeApprover } from "@/components/knowledge/NotKnowledgeApprover";
import { QuestionReview } from "@/components/knowledge/QuestionReview";
import { ReleaseActions } from "@/components/knowledge/ReleaseActions";
import { ReleaseStatusBadge } from "@/components/knowledge/ReleaseStatusBadge";

export async function generateMetadata(): Promise<Metadata> {
  return pageTitle("knowledgeConsole.review.title");
}

/**
 * One release, under review — every question with the case for its existence, the provenance that
 * makes it reproducible, and the lifecycle actions available from its current state.
 *
 * This is the only screen in the product that shows `whyWeAsk`, and the reason the reviewer/customer
 * split exists at all: the decision here is whether a question deserves to be asked, which the
 * question text alone cannot answer.
 */
export default async function ReleaseReviewPage({
  params,
}: {
  params: Promise<{ releaseId: string }>;
}) {
  await requireSession();
  const t = await getTranslations("knowledgeConsole");
  const actor = await getActor();
  if (!actor || !isKnowledgeApprover(actor)) return <NotKnowledgeApprover />;

  const { releaseId } = await params;
  let release;
  try {
    release = await getRelease(actor, releaseId);
  } catch (error) {
    if (error instanceof NotFoundError) notFound();
    throw error;
  }

  const [activeReleaseId, activations] = await Promise.all([
    getActiveReleaseId(actor, release.industrySlug),
    listActivations(actor, release.industrySlug),
  ]);
  const isLive = activeReleaseId === release.id;

  return (
    <div className="mx-auto max-w-4xl">
      <header className="pb-7">
        <Link
          href="/knowledge"
          className="inline-flex items-center gap-1 text-2xs text-foreground-muted hover:text-foreground"
        >
          <ArrowLeft className="h-3 w-3" strokeWidth={2} />
          {t("review.back")}
        </Link>
        <h1 className="mt-2 flex flex-wrap items-center gap-2.5 text-2xl font-semibold tracking-tight text-foreground">
          {release.industrySlug}
          <span className="text-base font-normal text-foreground-muted">v{release.version}</span>
          <span className="text-2xs">
            <ReleaseStatusBadge status={release.status} />
          </span>
        </h1>
        <p className="mt-1 text-sm text-foreground-secondary">
          {t("review.questionCount", { count: release.questions?.length ?? 0 })}
        </p>
      </header>

      <div className="space-y-4">
        <Card grain>
          <SectionHeader title={t("review.decision")} description={t("review.decisionHint")} />
          <div className="mt-3.5">
            <ReleaseActions release={release} isLive={isLive} />
          </div>
        </Card>

        <Card grain>
          {/* The three facts behind "how was this question written?", a year from now. Kept on the
              review screen rather than a debug panel: a reviewer approving generated text should
              see which model and which prompt produced it. */}
          <SectionHeader
            title={t("review.provenance")}
            description={t("review.provenanceHint")}
          />
          <dl className="mt-3.5 grid gap-2 text-2xs sm:grid-cols-2">
            {(
              [
                ["model", release.generatedByModel],
                ["prompt", release.promptVersion],
                ["commit", release.generatorCommit],
                ["createdBy", release.createdBy],
                ["approvedBy", release.approvedBy ?? "—"],
              ] as const
            ).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-3 rounded-lg bg-surface px-2.5 py-1.5">
                <dt className="text-foreground-muted">{t(`review.${key}`)}</dt>
                <dd className="truncate font-mono text-foreground-secondary">{value}</dd>
              </div>
            ))}
          </dl>
        </Card>

        <Card grain>
          <SectionHeader title={t("review.questions")} description={t("review.questionsHint")} />
          <ul className="mt-3.5 space-y-2.5">
            {(release.questions ?? []).map((question) => (
              <QuestionReview key={question.questionId} question={question} />
            ))}
          </ul>
        </Card>

        {activations.length > 0 && (
          <Card grain>
            {/* Append-only, and the reason "what was live on the day of that report?" stays
                answerable. */}
            <SectionHeader title={t("review.history")} description={t("review.historyHint")} />
            <ul className="mt-3.5 space-y-1.5">
              {activations.map((activation) => (
                <li
                  key={`${activation.releaseId}-${activation.activatedAt}`}
                  className="flex flex-wrap items-baseline justify-between gap-2 rounded-lg bg-surface px-2.5 py-1.5 text-2xs"
                >
                  <span className="text-foreground-secondary">
                    {activation.reason || t("review.noReason")}
                  </span>
                  <span className="font-mono text-foreground-muted">
                    {activation.activatedBy} · {new Date(activation.activatedAt).toISOString().slice(0, 16).replace("T", " ")}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  );
}

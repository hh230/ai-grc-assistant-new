import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";
import { getActor } from "@/lib/auth/actor";
import { requireSession } from "@/lib/auth/server";
import { pageTitle } from "@/lib/pageMetadata";
import {
  getActiveReleaseId,
  isKnowledgeApprover,
  listIndustries,
  listReleases,
} from "@/lib/knowledge/service";
import { KnowledgeConsole, type IndustryOverview } from "@/components/knowledge/KnowledgeConsole";
import { NotKnowledgeApprover } from "@/components/knowledge/NotKnowledgeApprover";

export async function generateMetadata(): Promise<Metadata> {
  return pageTitle("knowledgeConsole.title");
}

/**
 * The Knowledge Review Console (ADR 0067) — where a human decides whether generated sector
 * questions are fit to be asked, and which version customers actually see.
 *
 * Gated server-side. The nav entry is hidden for everyone else, but a hidden link is not a
 * permission: this page refuses to fetch anything before checking, and grc-api refuses again.
 */
export default async function KnowledgePage() {
  await requireSession();
  const t = await getTranslations("knowledgeConsole");
  const actor = await getActor();

  if (!actor || !isKnowledgeApprover(actor)) return <NotKnowledgeApprover />;

  const [industries, releases] = await Promise.all([listIndustries(actor), listReleases(actor)]);
  const overviews: IndustryOverview[] = await Promise.all(
    industries.map(async (industry) => ({
      industry,
      releases: releases.filter((release) => release.industrySlug === industry.slug),
      // The pointer, not "the newest released version" — after a rollback those disagree, and the
      // disagreement is precisely what a reviewer needs to see.
      activeReleaseId: await getActiveReleaseId(actor, industry.slug),
    })),
  );

  return (
    <div className="mx-auto max-w-4xl">
      <header className="pb-7">
        <p className="text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("eyebrow")}
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <p className="mt-1 text-sm text-foreground-secondary">{t("description")}</p>
      </header>

      <KnowledgeConsole overviews={overviews} />
    </div>
  );
}

import type { Metadata } from "next";
import { ArrowLeft } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { can } from "@/lib/auth/permissions";
import { requireSession } from "@/lib/auth/server";
import { AnalysisDetail } from "@/components/analysis/AnalysisDetail";
import { AnalysisHistory } from "@/components/analysis/AnalysisHistory";

export const metadata: Metadata = {
  title: "Analysis · Sentinel GRC",
};

export default async function AnalysisPage({
  searchParams,
}: {
  searchParams: Promise<{ doc?: string }>;
}) {
  const session = await requireSession();
  const t = await getTranslations("analysisPage");
  const canRun = can(session.roles, "execute", "knowledge_source");
  const { doc } = await searchParams;

  return (
    <div>
      <header className="pb-7">
        {doc && (
          <Link
            href="/analysis"
            className="inline-flex items-center gap-1.5 text-2xs font-medium text-foreground-muted transition-colors duration-150 hover:text-foreground-secondary"
          >
            <ArrowLeft className="h-3.5 w-3.5 flip-rtl" strokeWidth={1.75} />
            {t("allAnalyses")}
          </Link>
        )}
        <p className="mt-2 text-2xs font-medium uppercase tracking-wider text-foreground-muted">
          {t("eyebrow")}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
          {doc ? t("documentAnalysisTitle") : t("title")}
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-foreground-secondary">
          {doc ? t("documentAnalysisDescription") : t("description")}
        </p>
      </header>

      {doc ? <AnalysisDetail documentId={doc} canRun={canRun} /> : <AnalysisHistory />}
    </div>
  );
}

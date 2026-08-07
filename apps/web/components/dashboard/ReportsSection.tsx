import { FileText, Download, FileBarChart } from "lucide-react";
import { getTranslations } from "next-intl/server";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Link } from "@/i18n/navigation";
import { getActor } from "@/lib/auth/actor";
import { listDocuments } from "@/lib/documents/service";
import { listPolicies } from "@/lib/policies/service";
import { listRisks } from "@/lib/risk/service";
import { safely } from "@/lib/dashboard/activity";
import { REPORT_KINDS } from "@/lib/reports/types";

export async function ReportsSection() {
  const t = await getTranslations("dashboard.reportsSection");
  const actor = await getActor();

  const [documents, policies, risks] = actor
    ? await Promise.all([
        safely(() => listDocuments(actor)),
        safely(() => listPolicies(actor)),
        safely(() => listRisks(actor)),
      ])
    : [[], [], []];
  const hasAnyData = documents.length > 0 || policies.length > 0 || risks.length > 0;

  return (
    <Card flush>
      <div className="p-5 pb-4">
        <SectionHeader
          title={t("title")}
          description={t("description")}
          action={
            <Link href="/reports" className="text-2xs font-medium text-accent-foreground hover:underline">
              {t("viewLibrary")}
            </Link>
          }
        />
      </div>

      {!hasAnyData ? (
        <div className="flex flex-col items-center gap-3 px-5 py-12 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-elevated">
            <FileBarChart className="h-5 w-5 text-foreground-muted" strokeWidth={1.75} />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">{t("emptyTitle")}</p>
            <p className="max-w-xs text-xs text-foreground-muted">{t("emptyDescription")}</p>
          </div>
        </div>
      ) : (
        <div className="border-t border-hairline">
          {REPORT_KINDS.map((kind, index) => (
            <div
              key={kind}
              className={`flex items-center gap-3 px-5 py-3.5 transition-colors duration-150 hover:bg-white/[0.02] ${
                index !== REPORT_KINDS.length - 1 ? "border-b border-hairline" : ""
              }`}
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-hairline bg-surface-elevated">
                <FileText className="h-4 w-4 text-foreground-secondary" strokeWidth={1.75} />
              </span>
              <Link href="/reports" className="min-w-0 flex-1">
                <p className="truncate text-sm text-foreground">{t(`kinds.${kind}.title`)}</p>
                <p className="mt-0.5 truncate text-2xs text-foreground-muted">
                  {t(`kinds.${kind}.description`)}
                </p>
              </Link>
              <Badge tone="success">{t("status.ready")}</Badge>
              <a
                href={`/api/reports/${kind}/export?format=pdf`}
                aria-label={t("downloadReport")}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-hairline text-foreground-muted transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-hover hover:text-foreground"
              >
                <Download className="h-4 w-4" strokeWidth={1.75} />
              </a>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

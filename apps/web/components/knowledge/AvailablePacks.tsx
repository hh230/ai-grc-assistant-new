"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Check, Download, Loader2, TriangleAlert } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { importAuthoredPack } from "@/lib/knowledge/client";
import type { AuthoredPack } from "@/lib/knowledge/types";

/**
 * The authored packs this deployment ships — where deploying a new sector starts.
 *
 * Before this, a sector went live through a sequence somebody had to remember: register the
 * industry, call an endpoint with the right slug, then find the release. The pack file already
 * declares its slug and its Arabic name, so none of that was a decision — only ceremony. Importing
 * is one click, and everything a human genuinely decides still follows it.
 *
 * A pack whose file is broken is listed WITH its problem rather than hidden. A sector that silently
 * fails to appear is a worse failure than one that says why.
 */
export function AvailablePacks({
  packs,
  importedSlugs,
}: {
  packs: AuthoredPack[];
  importedSlugs: string[];
}) {
  const t = useTranslations("knowledgeConsole");
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [, startTransition] = useTransition();

  if (packs.length === 0) return null;

  async function importPack(slug: string) {
    setBusy(slug);
    setError(null);
    try {
      await importAuthoredPack(slug);
      startTransition(() => router.refresh());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card grain>
      <SectionHeader title={t("packs.title")} description={t("packs.description")} />

      {error && <p className="mt-3 text-2xs text-danger">{error}</p>}

      <ul className="mt-3.5 space-y-2">
        {packs.map((pack) => {
          const imported = importedSlugs.includes(pack.industrySlug);
          return (
            <li
              key={pack.industrySlug}
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-hairline bg-surface px-3.5 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground" dir="rtl">
                  {pack.canonicalNameAr}
                </p>
                <p className="mt-0.5 text-2xs text-foreground-muted">
                  {pack.industrySlug}
                  {pack.problem === null &&
                    ` · ${t("packs.questions", { count: pack.questionCount })}`}
                </p>
                {pack.problem && (
                  <p className="mt-1 flex items-start gap-1.5 text-2xs text-danger">
                    <TriangleAlert className="mt-px h-3 w-3 shrink-0" strokeWidth={2} aria-hidden />
                    {pack.problem}
                  </p>
                )}
              </div>

              {pack.problem === null && (
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void importPack(pack.industrySlug)}
                  className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-lg border border-hairline px-2.5 text-2xs font-medium text-foreground-secondary transition-colors duration-150 hover:text-foreground disabled:opacity-50"
                >
                  {busy === pack.industrySlug ? (
                    <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />
                  ) : imported ? (
                    <Check className="h-3 w-3" strokeWidth={2} />
                  ) : (
                    <Download className="h-3 w-3" strokeWidth={1.75} />
                  )}
                  {/* Re-importing is legitimate and mints a NEW version — that is how an edited
                      pack reaches customers. The label says so rather than pretending the button
                      is spent. */}
                  {imported ? t("packs.importAgain") : t("packs.import")}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

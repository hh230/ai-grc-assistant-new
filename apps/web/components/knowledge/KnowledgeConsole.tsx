"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Loader2, Plus, Sparkles } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { Link } from "@/i18n/navigation";
import { generateRelease, registerIndustry } from "@/lib/knowledge/client";
import type { Industry, KnowledgeRelease } from "@/lib/knowledge/types";
import { ReleaseStatusBadge } from "./ReleaseStatusBadge";

export interface IndustryOverview {
  industry: Industry;
  releases: KnowledgeRelease[];
  activeReleaseId: string | null;
}

/**
 * The console's landing view: one row per sector, showing what is LIVE and what is waiting.
 *
 * "Live" comes from the activation pointer, never from "the newest released version" — those are
 * different questions, and after a rollback they give different answers. A sector whose newest
 * release is v4 while v3 is live is not a bug to hide; it is the state a reviewer most needs to
 * see.
 */
export function KnowledgeConsole({ overviews }: { overviews: IndustryOverview[] }) {
  const t = useTranslations("knowledgeConsole");
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [slug, setSlug] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [, startTransition] = useTransition();

  async function run(key: string, action: () => Promise<unknown>) {
    setBusy(key);
    setError(null);
    try {
      await action();
      startTransition(() => router.refresh());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      {error && (
        <p className="rounded-lg border border-danger/30 bg-danger/5 px-3.5 py-2.5 text-sm text-danger">
          {error}
        </p>
      )}

      <Card grain>
        <SectionHeader
          title={t("industries.title")}
          description={t("industries.description")}
          action={
            <button
              type="button"
              onClick={() => setAdding((open) => !open)}
              className="inline-flex h-7 items-center gap-1 rounded-lg border border-hairline px-2.5 text-2xs font-medium text-foreground-secondary hover:text-foreground"
            >
              <Plus className="h-3 w-3" strokeWidth={2} />
              {t("industries.add")}
            </button>
          }
        />

        {adding && (
          <form
            className="mt-3.5 flex flex-wrap items-end gap-2 rounded-lg border border-hairline bg-surface px-3 py-2.5"
            onSubmit={(event) => {
              event.preventDefault();
              void run("register", async () => {
                await registerIndustry(slug.trim(), nameAr.trim());
                setSlug("");
                setNameAr("");
                setAdding(false);
              });
            }}
          >
            <label className="flex flex-col gap-1 text-2xs text-foreground-muted">
              {t("industries.slug")}
              <input
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                required
                pattern="[a-z][a-z0-9_]*"
                className="h-8 rounded-lg border border-hairline bg-surface-elevated px-2 text-sm text-foreground"
              />
            </label>
            <label className="flex flex-col gap-1 text-2xs text-foreground-muted">
              {t("industries.nameAr")}
              <input
                value={nameAr}
                onChange={(event) => setNameAr(event.target.value)}
                required
                dir="rtl"
                className="h-8 rounded-lg border border-hairline bg-surface-elevated px-2 text-sm text-foreground"
              />
            </label>
            <button
              type="submit"
              disabled={busy === "register"}
              className="inline-flex h-8 items-center gap-1 rounded-lg bg-accent px-3 text-2xs font-medium text-white disabled:opacity-60"
            >
              {busy === "register" && <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />}
              {t("industries.save")}
            </button>
          </form>
        )}

        {overviews.length === 0 ? (
          <p className="mt-3.5 text-sm text-foreground-muted">{t("industries.empty")}</p>
        ) : (
          <ul className="mt-3.5 space-y-2.5">
            {overviews.map(({ industry, releases, activeReleaseId }) => {
              const live = releases.find((release) => release.id === activeReleaseId) ?? null;
              const waiting = releases.filter((release) =>
                ["draft", "in_review", "approved"].includes(release.status),
              );
              return (
                <li
                  key={industry.slug}
                  className="rounded-lg border border-hairline bg-surface px-3.5 py-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground" dir="rtl">
                        {industry.canonicalNameAr}
                      </p>
                      <p className="mt-0.5 text-2xs text-foreground-muted">{industry.slug}</p>
                    </div>
                    <button
                      type="button"
                      disabled={busy === industry.slug || industry.status === "retired"}
                      onClick={() =>
                        void run(industry.slug, () => generateRelease(industry.slug))
                      }
                      className="inline-flex h-7 shrink-0 items-center gap-1 rounded-lg border border-hairline px-2.5 text-2xs font-medium text-foreground-secondary hover:text-foreground disabled:opacity-50"
                    >
                      {busy === industry.slug ? (
                        <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />
                      ) : (
                        <Sparkles className="h-3 w-3" strokeWidth={1.75} />
                      )}
                      {t("industries.generate")}
                    </button>
                  </div>

                  <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-2xs">
                    {live ? (
                      <Link
                        href={`/knowledge/releases/${live.id}`}
                        className="text-foreground-secondary hover:text-foreground"
                      >
                        {t("industries.live", { version: live.version })}
                      </Link>
                    ) : (
                      <span className="text-foreground-muted">{t("industries.nothingLive")}</span>
                    )}
                    {waiting.length > 0 && (
                      <span className="text-foreground-muted">
                        {t("industries.waiting", { count: waiting.length })}
                      </span>
                    )}
                  </div>

                  {releases.length > 0 && (
                    <ul className="mt-2.5 space-y-1">
                      {releases.map((release) => (
                        <li key={release.id} className="flex items-center gap-2 text-2xs">
                          <Link
                            href={`/knowledge/releases/${release.id}`}
                            className="text-foreground-secondary hover:text-foreground"
                          >
                            v{release.version}
                          </Link>
                          <ReleaseStatusBadge status={release.status} />
                          {release.id === activeReleaseId && (
                            <span className="rounded-md bg-accent-soft px-1.5 py-0.5 font-medium text-accent-foreground">
                              {t("status.live")}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}

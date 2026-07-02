"use client";

import { Sparkles, FileSearch, GitCompareArrows, ArrowRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { Badge } from "@/components/ui/Badge";

const ACTIONS = [
  { key: "analyzeContract", icon: FileSearch, href: "/upload" },
  { key: "gapAnalysis", icon: GitCompareArrows, href: undefined },
] as const;

const rowClass =
  "group flex w-full items-center gap-3 rounded-xl border border-hairline bg-surface-2/60 px-3.5 py-3 text-start backdrop-blur-sm transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-hover";

export function AiWorkspaceCard() {
  const t = useTranslations("dashboard.aiWorkspaceCard");

  return (
    <section className="relative overflow-hidden rounded-2xl border border-accent/20 bg-surface p-5 shadow-soft">
      {/* Glass accent glow — appropriate here as a feature surface, not on data cards. */}
      <div className="pointer-events-none absolute -end-16 -top-20 h-56 w-56 rounded-full bg-accent/20 blur-3xl" />
      <div className="pointer-events-none absolute inset-0 bg-accent-fade" />

      <div className="relative">
        <div className="flex items-center justify-between">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl border border-accent/30 bg-accent-soft backdrop-blur-sm">
            <Sparkles className="h-[18px] w-[18px] text-accent-foreground" strokeWidth={1.75} />
          </span>
          <Badge tone="accent" dot>
            {t("agentsOnline", { count: 6 })}
          </Badge>
        </div>

        <h2 className="mt-4 text-base font-semibold tracking-tight text-foreground">
          {t("title")}
        </h2>
        <p className="mt-1.5 text-sm leading-relaxed text-foreground-secondary">
          {t("description")}
        </p>

        <div className="mt-5 space-y-2">
          {ACTIONS.map((action) => {
            const Icon = action.icon;
            const inner = (
              <>
                <Icon className="h-4 w-4 text-accent-foreground" strokeWidth={1.75} />
                <span className="flex-1 text-sm text-foreground">{t(action.key)}</span>
                <ArrowRight
                  className="h-4 w-4 text-foreground-muted transition-transform duration-150 group-hover:translate-x-0.5 flip-rtl"
                  strokeWidth={1.75}
                />
              </>
            );
            return action.href ? (
              <Link key={action.key} href={action.href} className={rowClass}>
                {inner}
              </Link>
            ) : (
              <button key={action.key} type="button" className={rowClass}>
                {inner}
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}

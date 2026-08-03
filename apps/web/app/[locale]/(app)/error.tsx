"use client";

import { useEffect } from "react";
import * as Sentry from "@sentry/nextjs";
import { useTranslations } from "next-intl";
import { RotateCw, TriangleAlert } from "lucide-react";
import { Card } from "@/components/ui/Card";

/**
 * Error boundary for every authenticated workspace page (nothing existed before this — any
 * uncaught throw anywhere under `(app)` white-screened with Next.js's generic "Application
 * error" message; see the `/discovery` crash fixed alongside this, ADR-less bug fix). Catches
 * genuinely-broken-but-reachable backend failures that `lib/*\/service.ts` call sites
 * deliberately keep throwing (per the graceful-degradation policy in `lib/errors.ts` — only an
 * *unreachable* backend degrades silently; a reachable one returning errors is a real incident,
 * still logged/reported here, just not with a raw crash screen.
 */
export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useTranslations("appError");

  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <Card grain className="mx-auto mt-10 flex max-w-md flex-col items-center gap-4 py-14 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-danger/30 bg-danger-soft">
        <TriangleAlert className="h-5 w-5 text-danger" strokeWidth={1.75} />
      </div>
      <div className="space-y-1.5">
        <h1 className="text-base font-semibold tracking-tight text-foreground">{t("title")}</h1>
        <p className="max-w-xs text-xs text-foreground-muted">{t("description")}</p>
      </div>
      <button
        type="button"
        onClick={() => reset()}
        className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground-secondary transition-colors duration-150 hover:border-hairline-strong hover:bg-surface-2 hover:text-foreground"
      >
        <RotateCw className="h-4 w-4" strokeWidth={1.75} />
        {t("retry")}
      </button>
    </Card>
  );
}

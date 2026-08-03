"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { ArrowRight, CheckCircle2, Loader2, Mail, TriangleAlert } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { LogoMark } from "@/components/ui/Logo";
import { requestPasswordReset } from "@/lib/passwordReset/client";

export function ForgotPasswordForm() {
  const t = useTranslations("forgotPasswordPage");

  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : t("genericError"));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-sm">
      <div className="mb-8 flex flex-col items-center text-center">
        <LogoMark size={44} priority />
        <h1 className="mt-4 text-xl font-semibold tracking-tight text-foreground">
          {t("title")}
        </h1>
        <p className="mt-1 text-sm text-foreground-secondary">{t("subtitle")}</p>
      </div>

      {sent ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-hairline bg-surface/40 px-4 py-6 text-center">
          <CheckCircle2 className="h-8 w-8 text-success" strokeWidth={1.75} />
          <p className="text-sm text-foreground">{t("sentMessage", { email })}</p>
          <Link
            href="/login"
            className="mt-2 text-sm font-medium text-accent-foreground hover:underline"
          >
            {t("backToLogin")}
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>
          {error && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-3 py-2.5 text-sm text-foreground"
            >
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-danger" strokeWidth={1.75} />
              <span>{error}</span>
            </div>
          )}

          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-foreground-secondary">
              {t("emailLabel")}
            </span>
            <span className="relative block">
              <Mail
                className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
                strokeWidth={1.75}
              />
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={t("emailPlaceholder")}
                className="h-10 w-full rounded-lg border border-hairline bg-surface/60 ps-9 pe-3 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-foreground-muted focus:border-hairline-strong focus:bg-surface-2"
              />
            </span>
          </label>

          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-accent text-sm font-medium text-white shadow-glow transition-opacity duration-150 hover:opacity-90 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
                {t("submitting")}
              </>
            ) : (
              <>
                {t("submit")}
                <ArrowRight className="h-4 w-4" strokeWidth={2} />
              </>
            )}
          </button>

          <p className="text-center text-sm text-foreground-secondary">
            <Link href="/login" className="font-medium text-accent-foreground hover:underline">
              {t("backToLogin")}
            </Link>
          </p>
        </form>
      )}
    </div>
  );
}

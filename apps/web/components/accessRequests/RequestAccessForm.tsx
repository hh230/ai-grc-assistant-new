"use client";

import { useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { Building2, CheckCircle2, Loader2, Mail, TriangleAlert, User } from "lucide-react";
import { submitAccessRequest } from "@/lib/accessRequests/client";

export function RequestAccessForm() {
  const t = useTranslations("requestAccessPage.form");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await submitAccessRequest({
        name,
        email,
        organizationName,
        roleTitle,
        message: message.trim() || undefined,
      });
      setSubmitted(true);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : t("genericError"));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-hairline-strong bg-surface-2 shadow-soft">
          <CheckCircle2 className="h-5 w-5 text-accent" strokeWidth={1.75} />
        </div>
        <h2 className="text-lg font-semibold text-foreground">{t("successTitle")}</h2>
        <p className="max-w-sm text-sm text-foreground-secondary">{t("successDescription")}</p>
      </div>
    );
  }

  return (
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
          {t("nameLabel")}
        </span>
        <span className="relative block">
          <User
            className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
            strokeWidth={1.75}
          />
          <input
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("namePlaceholder")}
            className="h-10 w-full rounded-lg border border-hairline bg-surface/60 ps-9 pe-3 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-foreground-muted focus:border-hairline-strong focus:bg-surface-2"
          />
        </span>
      </label>

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
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("emailPlaceholder")}
            className="h-10 w-full rounded-lg border border-hairline bg-surface/60 ps-9 pe-3 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-foreground-muted focus:border-hairline-strong focus:bg-surface-2"
          />
        </span>
      </label>

      <label className="block">
        <span className="mb-1.5 block text-xs font-medium text-foreground-secondary">
          {t("organizationLabel")}
        </span>
        <span className="relative block">
          <Building2
            className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
            strokeWidth={1.75}
          />
          <input
            type="text"
            required
            value={organizationName}
            onChange={(e) => setOrganizationName(e.target.value)}
            placeholder={t("organizationPlaceholder")}
            className="h-10 w-full rounded-lg border border-hairline bg-surface/60 ps-9 pe-3 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-foreground-muted focus:border-hairline-strong focus:bg-surface-2"
          />
        </span>
      </label>

      <label className="block">
        <span className="mb-1.5 block text-xs font-medium text-foreground-secondary">
          {t("roleLabel")}
        </span>
        <input
          type="text"
          required
          value={roleTitle}
          onChange={(e) => setRoleTitle(e.target.value)}
          placeholder={t("rolePlaceholder")}
          className="h-10 w-full rounded-lg border border-hairline bg-surface/60 px-3 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-foreground-muted focus:border-hairline-strong focus:bg-surface-2"
        />
      </label>

      <label className="block">
        <span className="mb-1.5 block text-xs font-medium text-foreground-secondary">
          {t("messageLabel")}
        </span>
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder={t("messagePlaceholder")}
          rows={3}
          className="w-full resize-none rounded-lg border border-hairline bg-surface/60 px-3 py-2 text-sm text-foreground outline-none transition-colors duration-150 placeholder:text-foreground-muted focus:border-hairline-strong focus:bg-surface-2"
        />
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
          t("submit")
        )}
      </button>
    </form>
  );
}

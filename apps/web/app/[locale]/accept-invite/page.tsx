import type { Metadata } from "next";
import { Suspense } from "react";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { AcceptInviteForm } from "@/components/auth/AcceptInviteForm";
import { LanguageSwitcher } from "@/components/navigation/LanguageSwitcher";

export const metadata: Metadata = {
  title: "Accept Invitation · Rasheed",
  description: "Set your password and join your organization on Rasheed.",
};

export default async function AcceptInvitePage() {
  const t = await getTranslations("login");
  const tCommon = await getTranslations("common");
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-12">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-accent-fade"
        aria-hidden
      />
      <Link
        href="/"
        className="absolute start-6 top-6 text-sm font-semibold tracking-tight text-foreground transition-opacity hover:opacity-80"
      >
        {tCommon("appName")}
      </Link>
      <div className="absolute end-6 top-6">
        <LanguageSwitcher />
      </div>
      <div className="relative z-10 flex w-full justify-center">
        <Suspense fallback={null}>
          <AcceptInviteForm />
        </Suspense>
      </div>
      <p className="absolute bottom-6 text-2xs text-foreground-muted">
        {t("footer", { year: new Date().getFullYear() })}
      </p>
    </main>
  );
}

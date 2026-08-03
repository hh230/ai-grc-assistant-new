import type { Metadata } from "next";
import { pageTitle } from "@/lib/pageMetadata";
import { Suspense } from "react";
import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";
import { ForgotPasswordForm } from "@/components/auth/ForgotPasswordForm";
import { LanguageSwitcher } from "@/components/navigation/LanguageSwitcher";
import { Logo } from "@/components/ui/Logo";

export async function generateMetadata(): Promise<Metadata> {
  return pageTitle("forgotPasswordPage.title", {
    description: "Reset the password for your Rasheed account.",
  });
}

export default async function ForgotPasswordPage() {
  const t = await getTranslations("login");
  const tCommon = await getTranslations("common");
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4 py-12">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-80 bg-accent-fade"
        aria-hidden
      />
      <Link href="/" className="absolute start-6 top-6 transition-opacity hover:opacity-80">
        <Logo size={22} wordmark={tCommon("appName")} wordmarkClassName="text-sm font-semibold" />
      </Link>
      <div className="absolute end-6 top-6">
        <LanguageSwitcher />
      </div>
      <div className="relative z-10 flex w-full justify-center">
        <Suspense fallback={null}>
          <ForgotPasswordForm />
        </Suspense>
      </div>
      <p className="absolute bottom-6 text-2xs text-foreground-muted">
        {t("footer", { year: new Date().getFullYear() })}
      </p>
    </main>
  );
}

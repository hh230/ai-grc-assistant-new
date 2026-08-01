import type { Metadata, Viewport } from "next";
import { getLocale } from "next-intl/server";
import { ibmPlexSansArabic, notoSansArabic } from "@/lib/fonts";
import { cn } from "@/lib/utils";
import "./globals.css";

// Resolves the absolute URL for the app/opengraph-image.png / app/icon.png file
// conventions below. Prefers an explicit override, then Vercel's own
// system env var for the project's production domain (auto-injected on every
// deployment, no dashboard config needed — see
// https://vercel.com/docs/environment-variables/system-environment-variables),
// then falls back to localhost in local dev.
const SITE_URL =
  process.env.NEXT_PUBLIC_APP_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "Rasheed",
  description:
    "Enterprise Governance, Risk, Compliance and AI platform — real-time posture across regulated frameworks.",
};

export const viewport: Viewport = {
  themeColor: "#fbf8f3",
};

// True root layout — stays outside the `[locale]` segment because `app/api/*` routes must
// not be locale-prefixed. `lang`/`dir` are still locale-driven: `getLocale()` resolves the
// locale next-intl's middleware negotiated for this request (V2-P3 design proposal §15).
// The Arabic font variables are always loaded (self-hosted, no runtime cost either way) but
// `font-sans-arabic` — which actually applies them — is only the active body font for `ar`;
// `en` keeps the existing Latin `font-sans` stack (design proposal §5).
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const dir = locale === "ar" ? "rtl" : "ltr";
  return (
    <html
      lang={locale}
      dir={dir}
      className={cn(ibmPlexSansArabic.variable, notoSansArabic.variable)}
    >
      <body
        className={cn(
          "min-h-screen bg-background text-foreground antialiased",
          locale === "ar" ? "font-sans-arabic" : "font-sans",
        )}
      >
        {children}
      </body>
    </html>
  );
}

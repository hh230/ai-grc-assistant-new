import type { Metadata, Viewport } from "next";
import { getLocale } from "next-intl/server";
import { ibmPlexSansArabic, notoSansArabic } from "@/lib/fonts";
import { cn } from "@/lib/utils";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sentinel GRC",
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

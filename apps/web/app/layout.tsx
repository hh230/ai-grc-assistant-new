import type { Metadata, Viewport } from "next";
import { getLocale } from "next-intl/server";
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
// The Arabic/Latin font stack itself is applied per-locale in `app/[locale]/layout.tsx`.
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  const dir = locale === "ar" ? "rtl" : "ltr";
  return (
    <html lang={locale} dir={dir}>
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        {children}
      </body>
    </html>
  );
}

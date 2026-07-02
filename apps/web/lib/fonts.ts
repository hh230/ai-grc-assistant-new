import { IBM_Plex_Sans_Arabic, Noto_Sans_Arabic } from "next/font/google";

/**
 * Arabic typeface stack (V2-P3 design proposal §5): IBM Plex Sans Arabic is primary —
 * enterprise/financial type system, strong x-height and digit/letter distinction at small
 * sizes for dense compliance tables and long-form report reading. Noto Sans Arabic is the
 * fallback/safety net (broadest glyph/hinting coverage). Tajawal was evaluated and
 * deprioritized — too rounded/consumer-feeling for this product's personality (proposal §1).
 * Both are self-hosted via `next/font` (no runtime Google Fonts request, no layout shift).
 */
export const ibmPlexSansArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ibm-plex-sans-arabic",
  display: "swap",
});

export const notoSansArabic = Noto_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-noto-sans-arabic",
  display: "swap",
});

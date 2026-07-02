import { defineRouting } from "next-intl/routing";

/**
 * Locale routing config — single source of truth for next-intl's middleware, navigation
 * helpers, and request config. Arabic is the default locale (Product Owner decision,
 * V2-P3 design proposal §11/§15): a visitor with no stored preference lands on `/ar`.
 */
export const routing = defineRouting({
  locales: ["ar", "en"],
  defaultLocale: "ar",
  localePrefix: "always",
});

export type AppLocale = (typeof routing.locales)[number];

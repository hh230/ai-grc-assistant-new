/**
 * Resolves the caller's UI locale inside Route Handlers under `app/api/*`. Those routes sit
 * outside the `[locale]` segment (CLAUDE.md — API routes are never locale-prefixed, see
 * `middleware.ts`), so `next-intl/server`'s `getLocale()` has no request-scoped locale to
 * read. next-intl's middleware still sets the `NEXT_LOCALE` cookie on every page response
 * (routing.ts `localeCookie`, default next-intl behavior) to remember the visitor's locale
 * choice — reading it directly here is the explicit, dependency-free way to know which
 * language an AI-generated response (analysis, chat, report) should be produced in.
 * Node-only.
 */

import { cookies } from "next/headers";
import { routing, type AppLocale } from "@/i18n/routing";

const LOCALE_COOKIE = "NEXT_LOCALE";

export async function getRequestLocale(): Promise<AppLocale> {
  const value = (await cookies()).get(LOCALE_COOKIE)?.value;
  return (routing.locales as readonly string[]).includes(value ?? "")
    ? (value as AppLocale)
    : routing.defaultLocale;
}

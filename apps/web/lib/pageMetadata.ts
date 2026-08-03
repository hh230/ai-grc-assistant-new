import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

/**
 * Builds a locale-aware `<title>` ("X · Rasheed") from any next-intl message key, e.g.
 * "dashboard.pageHeader.title" or "missionsPage.title". Every page's `generateMetadata`
 * uses this so the browser tab follows the active locale instead of a hardcoded English
 * string. `extra` merges in any other static `Metadata` fields (e.g. `description`) a page
 * already declares.
 */
export async function pageTitle(key: string, extra?: Omit<Metadata, "title">): Promise<Metadata> {
  const [namespace, ...rest] = key.split(".");
  const t = await getTranslations(namespace);
  return { title: `${t(rest.join("."))} · Rasheed`, ...extra };
}

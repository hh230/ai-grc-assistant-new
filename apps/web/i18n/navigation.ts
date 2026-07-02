import { createNavigation } from "next-intl/navigation";
import { routing } from "./routing";

/**
 * Locale-aware drop-in replacements for `next/link` and `next/navigation`. Every internal
 * `href`/`redirect`/`router.push` in `(app)` and `(marketing)` components must use these
 * (not the plain `next/*` versions) so links stay on the current locale automatically —
 * see V2-P3 design proposal §11 (Navigation) / §15 (Arabic/RTL).
 */
const nav = createNavigation(routing);

export const { Link, usePathname, useRouter, getPathname } = nav;

/**
 * Re-typed as `(...) => never` explicitly — destructuring `nav.redirect` directly loses
 * TypeScript's "code after this call is unreachable" narrowing for callers (the inferred
 * type from `createNavigation`'s generics doesn't collapse to a bare `never` return on
 * destructure), which broke `if (!actor) redirect(...)` guards across several pages.
 */
export function redirect(...args: Parameters<typeof nav.redirect>): never {
  return nav.redirect(...args);
}

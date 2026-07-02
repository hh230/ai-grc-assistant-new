import { NextResponse, type NextRequest } from "next/server";
import {
  DEFAULT_AUTHENTICATED_PATH,
  LOGIN_PATH,
  PUBLIC_MARKETING_PATHS,
  SESSION_COOKIE,
} from "@/lib/auth/config";
import { verifySessionToken } from "@/lib/auth/session";

/**
 * Edge auth gate — the primary protection for every page route. Unauthenticated requests
 * are redirected to login (preserving the intended destination), except for the public
 * marketing site (V2 — no login wall before a visitor understands the product). Authenticated
 * requests to the login page are bounced to the dashboard. Server-side `requireSession()` in
 * the authenticated layout backs this up as defense-in-depth.
 */
export async function middleware(request: NextRequest): Promise<NextResponse> {
  const { pathname, search } = request.nextUrl;
  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const session = token ? await verifySessionToken(token) : null;
  const isLoginRoute = pathname === LOGIN_PATH;
  const isPublicMarketingRoute = (PUBLIC_MARKETING_PATHS as readonly string[]).includes(
    pathname,
  );

  if (!session && !isLoginRoute && !isPublicMarketingRoute) {
    const url = request.nextUrl.clone();
    url.pathname = LOGIN_PATH;
    url.search = "";
    url.searchParams.set("next", `${pathname}${search}`);
    return NextResponse.redirect(url);
  }

  if (session && isLoginRoute) {
    const url = request.nextUrl.clone();
    url.pathname = DEFAULT_AUTHENTICATED_PATH;
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  // Run on everything except auth endpoints, Next internals, and static assets.
  matcher: [
    "/((?!api/auth|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};

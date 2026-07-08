import createNextIntlPlugin from "next-intl/plugin";

/** @type {import('next').NextConfig} */

const withNextIntl = createNextIntlPlugin("./i18n/request.ts");

// Security headers applied to every response. A pragmatic Content-Security-Policy is used;
// tightening script-src to a per-request nonce is the recommended production follow-up.
//
// Next's dev server bundles modules with `eval(...)` wrappers for HMR/source-maps, which
// the browser blocks under a strict CSP — the page still renders (SSR HTML) but the client
// bundle never executes, so React never hydrates and no event handlers attach. `unsafe-eval`
// is therefore only added outside production, where webpack doesn't need it.
const isDev = process.env.NODE_ENV !== "production";
const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self'",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const SECURITY_HEADERS = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-DNS-Prefetch-Control", value: "off" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  { key: "Content-Security-Policy", value: CONTENT_SECURITY_POLICY },
];

const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@grc/ui", "@grc/contracts", "@grc/i18n"],
  typedRoutes: true,
  // Optimized, self-contained output for container/serverless deployment.
  output: "standalone",
  // Keep heavy CJS/native document parsers out of the webpack server bundle — they are
  // required at runtime from node_modules instead (fixes pdfjs/mammoth bundling errors).
  // unpdf (PDF text extraction) is pure JS with no native deps, so it bundles normally and
  // doesn't need to be listed here.
  serverExternalPackages: ["mammoth", "exceljs", "pdf-lib"],
  // Do not leak the framework version.
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
};

export default withNextIntl(nextConfig);

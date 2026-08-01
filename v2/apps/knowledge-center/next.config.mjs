/** @type {import('next').NextConfig} */
const nextConfig = {
  // The Knowledge Center reads generated JSON artifacts from disk at request time via the
  // services layer, so pages are always dynamically rendered (never statically cached).
  reactStrictMode: true,
};

export default nextConfig;

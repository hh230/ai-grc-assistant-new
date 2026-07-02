# Production image for @grc/web (Next.js standalone output) in a pnpm monorepo.
# Build from the REPO ROOT:  docker build -f apps/web/Dockerfile -t grc-web .

# ── deps: install workspace dependencies ────────────────────────────────────
FROM node:22-alpine AS deps
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json tsconfig.base.json ./
COPY apps/web/package.json apps/web/
COPY packages/ui/package.json packages/ui/
COPY packages/contracts/package.json packages/contracts/
COPY packages/i18n/package.json packages/i18n/
RUN pnpm install --frozen-lockfile

# ── build: compile the standalone server bundle ─────────────────────────────
FROM node:22-alpine AS build
RUN corepack enable
WORKDIR /repo
COPY --from=deps /repo/node_modules ./node_modules
COPY --from=deps /repo/apps/web/node_modules ./apps/web/node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
# AUTH_SECRET is only needed at runtime; a build-time placeholder keeps `next build` happy.
ENV AUTH_SECRET=build-time-placeholder-secret-least-32-chars-000
RUN pnpm --filter @grc/web build

# ── runner: minimal runtime ─────────────────────────────────────────────────
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

# Next standalone output preserves the monorepo layout under apps/web.
COPY --from=build --chown=nextjs:nodejs /repo/apps/web/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=nextjs:nodejs /repo/apps/web/public ./apps/web/public

USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
# STORAGE_DIR should point at a mounted volume; AUTH_SECRET + OPENAI_API_KEY come from secrets.
CMD ["node", "apps/web/server.js"]

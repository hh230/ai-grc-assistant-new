# Image for the Next.js web app. Scaffold placeholder.
FROM node:22-slim
ENV NODE_ENV=production
RUN corepack enable
WORKDIR /app
# COPY + pnpm install + pnpm build added in a later PR.
CMD ["node", "-e", "console.log('web scaffold — not yet implemented')"]

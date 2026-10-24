# Build-context: de root van de repo (de composities staan in packages/).
FROM node:22-bookworm-slim

# Systeembibliotheken voor Chrome Headless Shell (zie remotion.dev/docs/miscellaneous/linux-dependencies).
RUN apt-get update && apt-get install -y --no-install-recommends \
      libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 libxkbcommon-dev \
      libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages ./packages
COPY apps/render ./apps/render
# pnpm wil alle workspace-manifesten zien, ook als die niet geinstalleerd worden.
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile --filter @flow/render...

WORKDIR /repo/apps/render
RUN pnpm exec tsx scripts/ensure-browser.ts

ENV NODE_ENV=production RENDER_PORT=3001
EXPOSE 3001
CMD ["pnpm", "exec", "tsx", "src/server.ts"]

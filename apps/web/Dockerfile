# Build-context: de root van de repo.
FROM node:22-bookworm-slim AS build
RUN corepack enable
WORKDIR /repo
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json ./
COPY packages ./packages
COPY apps/web ./apps/web
# pnpm wil alle workspace-manifesten zien, ook als die niet geinstalleerd worden.
COPY apps/render/package.json ./apps/render/package.json
RUN pnpm install --frozen-lockfile --filter @flow/web...
RUN pnpm --filter @flow/web build

FROM nginx:1.27-alpine
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/web/dist /usr/share/nginx/html
EXPOSE 80

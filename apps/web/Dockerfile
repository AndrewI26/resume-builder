# Build context is the repo root. The app itself is packages/ui, shared with
# the desktop shell; this image is only its browser deployment, which is the
# static bundle plus an nginx to serve it.

FROM oven/bun:1-alpine AS dependencies
WORKDIR /repo
COPY package.json bun.lock bunfig.toml ./
COPY packages/ui/package.json packages/ui/package.json
# --ignore-scripts: the root "prepare" runs husky, which needs a .git it does
# not have here
RUN bun install --frozen-lockfile --ignore-scripts


# bun installs the lockfile, but node runs the build: react-router's default
# server entry prerenders the SPA fallback through react-dom/server's node
# streams, which bun's runtime cannot render.
FROM node:24-alpine AS build
WORKDIR /repo
COPY --from=dependencies /repo/node_modules node_modules
COPY package.json bunfig.toml tsconfig.json ./
COPY packages/ui packages/ui

# vite reads its env from the repo root (see packages/ui/vite.config.ts), and the
# API URL is baked into the bundle at build time because the app is a SPA that
# calls the API straight from the browser.
ARG VITE_API_BASE_URL=http://localhost:8000
RUN printf 'VITE_API_BASE_URL=%s\n' "$VITE_API_BASE_URL" > .env \
 && cd packages/ui && ../../node_modules/.bin/react-router build


# react-router.config.ts sets ssr: false, so the build is a static bundle and
# nginx is all it takes to serve it.
FROM nginx:1.29-alpine
COPY docker/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/packages/ui/build/client /usr/share/nginx/html
EXPOSE 80

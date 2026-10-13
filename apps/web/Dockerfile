# Build context is the repo root, for the lockfile. The image is the SPA's
# static bundle and nothing to serve it: running it copies the bundle into
# /out for the host's reverse proxy to serve.

FROM oven/bun:1-alpine AS dependencies
WORKDIR /repo
COPY package.json bun.lock bunfig.toml ./
COPY apps/web/package.json apps/web/package.json
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
COPY apps/web apps/web

# vite reads its env from the repo root (see apps/web/vite.config.ts), and the
# API URL is baked into the bundle at build time because the app is a SPA that
# calls the API straight from the browser. The default is the reverse proxy's
# route to the API, on the same origin as the page.
ARG VITE_API_BASE_URL=/api
RUN printf 'VITE_API_BASE_URL=%s\n' "$VITE_API_BASE_URL" > .env \
 && cd apps/web && ../../node_modules/.bin/react-router build


# react-router.config.ts sets ssr: false, so the build is a static bundle.
# Files from earlier builds are left in place: their fingerprinted names never
# collide, and a page still open from before the deploy keeps loading them.
FROM alpine:3.22
COPY --from=build /repo/apps/web/build/client /site
CMD ["cp", "-R", "/site/.", "/out/"]

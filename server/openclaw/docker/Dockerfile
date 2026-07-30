# syntax=docker/dockerfile:1.7

FROM node:24-bookworm

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    g++ \
    make \
    python3 \
    tini \
  && rm -rf /var/lib/apt/lists/*

RUN corepack enable

WORKDIR /workspace/openclaw

# Keep the GitHub source in app/ and build from there.
COPY app/ ./app/

WORKDIR /workspace/openclaw/app

RUN pnpm install --frozen-lockfile
RUN pnpm build:docker && pnpm ui:build

ENV NODE_ENV=production

ENTRYPOINT ["tini", "-s", "--"]
CMD ["node", "openclaw.mjs", "gateway", "--bind", "0.0.0.0", "--port", "18789"]

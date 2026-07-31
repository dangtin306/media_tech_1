#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker compose -f "$ROOT_DIR/docker/compose.dev.yml" up -d --no-build

for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  if curl -fsS "http://127.0.0.1:${OPENCLAW_GATEWAY_PORT:-8803}/healthz" >/dev/null; then
    exit 0
  fi
  sleep 2
done

echo "OpenClaw dev health check failed" >&2
exit 1

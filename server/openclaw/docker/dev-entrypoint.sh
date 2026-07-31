#!/usr/bin/env bash
set -euo pipefail

cd /workspace/openclaw/app

if [ ! -d node_modules ] || [ ! -f node_modules/.modules.yaml ]; then
  pnpm install --frozen-lockfile
fi

if [ "$#" -eq 0 ]; then
  exec pnpm gateway:watch:raw
fi

exec "$@"

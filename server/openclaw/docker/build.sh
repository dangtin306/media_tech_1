#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_TAG="${OPENCLAW_IMAGE:-openclaw:local}"

docker build -f "$ROOT_DIR/docker/Dockerfile" -t "$IMAGE_TAG" "$ROOT_DIR"

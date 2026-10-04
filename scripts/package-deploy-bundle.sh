#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_ID="${1:?usage: package-deploy-bundle.sh <release-id>}"
OUTPUT_DIR="${ROOT_DIR}/build/deploy-bundles"
OUTPUT_PATH="${OUTPUT_DIR}/medrag-prod-${RELEASE_ID}.tgz"

mkdir -p "${OUTPUT_DIR}"

tar -C "${ROOT_DIR}" -czf "${OUTPUT_PATH}" \
  docker-compose.prod.yml \
  deploy/app.env.prod \
  deploy/nginx/default.conf \
  scripts/deploy-prod.sh \
  scripts/teardown-app.sh

printf '%s\n' "${OUTPUT_PATH}"

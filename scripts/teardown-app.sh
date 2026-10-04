#!/usr/bin/env bash
set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/medrag}"
APP_ROOT="${DEPLOY_ROOT}/app"
CURRENT_LINK="${APP_ROOT}/current"
RUNTIME_ENV_FILE="${DEPLOY_ROOT}/runtime/app.env"

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

if [[ -f "${RUNTIME_ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "${RUNTIME_ENV_FILE}"
  set +a
fi

if [[ -f "${CURRENT_LINK}/docker-compose.prod.yml" ]]; then
  log "Stopping MedRAG application stack"
  docker compose -f "${CURRENT_LINK}/docker-compose.prod.yml" --env-file "${RUNTIME_ENV_FILE}" down -v --remove-orphans || true
fi

log "Removing application directories"
rm -rf "${APP_ROOT}" \
       "${DEPLOY_ROOT}/runtime" \
       "${DEPLOY_ROOT}/data/qdrant" \
       "${DEPLOY_ROOT}/data/medrag"

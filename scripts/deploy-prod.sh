#!/usr/bin/env bash
set -euo pipefail

DEPLOY_ROOT="${DEPLOY_ROOT:-/opt/medrag}"
APP_ROOT="${DEPLOY_ROOT}/app"
RELEASES_DIR="${APP_ROOT}/releases"
CURRENT_LINK="${APP_ROOT}/current"
RUNTIME_DIR="${DEPLOY_ROOT}/runtime"
RUNTIME_ENV_FILE="${RUNTIME_DIR}/app.env"
PREVIOUS_ENV_FILE="${RUNTIME_DIR}/app.env.previous"
TMP_ROOT="${DEPLOY_ROOT}/tmp"
SECRET_FILE_TO_CLEANUP=""

AWS_REGION="${AWS_REGION:?AWS_REGION is required}"
RELEASE_ID="${RELEASE_ID:?RELEASE_ID is required}"
APP_IMAGE="${APP_IMAGE:?APP_IMAGE is required}"
SECRET_ID="${SECRET_ID:?SECRET_ID is required}"
BUNDLE_URI="${BUNDLE_URI:-}"
BUNDLE_LOCAL_PATH="${BUNDLE_LOCAL_PATH:-}"

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

cleanup() {
  if [[ -n "${SECRET_FILE_TO_CLEANUP}" && -f "${SECRET_FILE_TO_CLEANUP}" ]]; then
    rm -f "${SECRET_FILE_TO_CLEANUP}"
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  }
}

rollback() {
  if [[ -z "${PREVIOUS_RELEASE_DIR:-}" || ! -d "${PREVIOUS_RELEASE_DIR:-}" || ! -f "${PREVIOUS_ENV_FILE}" ]]; then
    log "No previous release metadata available; skipping rollback"
    return 1
  fi

  log "Rolling back to previous release ${PREVIOUS_RELEASE_DIR}"
  cp "${PREVIOUS_ENV_FILE}" "${RUNTIME_ENV_FILE}"
  ln -sfn "${PREVIOUS_RELEASE_DIR}" "${CURRENT_LINK}"
  set -a
  # shellcheck disable=SC1090
  . "${RUNTIME_ENV_FILE}"
  set +a
  docker compose -f "${CURRENT_LINK}/docker-compose.prod.yml" --env-file "${RUNTIME_ENV_FILE}" up -d qdrant api ui proxy
}

wait_for_health() {
  local attempt
  for attempt in $(seq 1 60); do
    if curl -fsS http://127.0.0.1:8000/health | grep -q '"collection_ready":true'; then
      if curl -fsS http://127.0.0.1/ >/dev/null 2>&1; then
        return 0
      fi
    fi
    sleep 5
  done
  return 1
}

render_runtime_env() {
  local template_file="$1"
  local secret_file="$2"

  cp "${template_file}" "${RUNTIME_ENV_FILE}"
  {
    printf 'APP_IMAGE=%s\n' "${APP_IMAGE}"
    printf 'OPENAI_API_KEY=%s\n' "$(jq -er '.OPENAI_API_KEY' "${secret_file}")"
    printf 'LLAMA_CLOUD_API_KEY=%s\n' "$(jq -er '.LLAMA_CLOUD_API_KEY' "${secret_file}")"
  } >> "${RUNTIME_ENV_FILE}"
  chmod 600 "${RUNTIME_ENV_FILE}"
}

stage_bundle() {
  local bundle_path="$1"
  local release_dir="${RELEASES_DIR}/${RELEASE_ID}"
  rm -rf "${release_dir}"
  mkdir -p "${release_dir}"
  tar -xzf "${bundle_path}" -C "${release_dir}"
  ln -sfn "${release_dir}" "${CURRENT_LINK}"
}

main() {
  require_command aws
  require_command curl
  require_command docker
  require_command jq
  require_command tar

  install -d -m 0755 "${RELEASES_DIR}" "${RUNTIME_DIR}" "${TMP_ROOT}"

  PREVIOUS_RELEASE_DIR=""
  if [[ -L "${CURRENT_LINK}" ]]; then
    PREVIOUS_RELEASE_DIR="$(readlink -f "${CURRENT_LINK}")"
  fi
  if [[ -f "${RUNTIME_ENV_FILE}" ]]; then
    cp "${RUNTIME_ENV_FILE}" "${PREVIOUS_ENV_FILE}"
  fi

  local bundle_path
  if [[ -n "${BUNDLE_LOCAL_PATH}" ]]; then
    bundle_path="${BUNDLE_LOCAL_PATH}"
  elif [[ -n "${BUNDLE_URI}" ]]; then
    bundle_path="${TMP_ROOT}/${RELEASE_ID}.tgz"
    log "Downloading deployment bundle from ${BUNDLE_URI}"
    aws s3 cp "${BUNDLE_URI}" "${bundle_path}" --region "${AWS_REGION}"
  else
    printf 'Either BUNDLE_LOCAL_PATH or BUNDLE_URI must be provided.\n' >&2
    exit 1
  fi

  log "Staging release ${RELEASE_ID}"
  stage_bundle "${bundle_path}"

  local secret_file
  secret_file="$(mktemp "${TMP_ROOT}/secret.XXXXXX.json")"
  SECRET_FILE_TO_CLEANUP="${secret_file}"
  trap cleanup EXIT

  log "Fetching runtime secrets from Secrets Manager"
  aws secretsmanager get-secret-value \
    --secret-id "${SECRET_ID}" \
    --query SecretString \
    --output text \
    --region "${AWS_REGION}" > "${secret_file}"

  render_runtime_env "${CURRENT_LINK}/deploy/app.env.prod" "${secret_file}"

  set -a
  # shellcheck disable=SC1090
  . "${RUNTIME_ENV_FILE}"
  set +a

  log "Authenticating Docker to ECR"
  aws ecr get-login-password --region "${AWS_REGION}" \
    | docker login --username AWS --password-stdin "$(printf '%s' "${APP_IMAGE}" | cut -d/ -f1)"

  log "Pulling updated images"
  docker compose -f "${CURRENT_LINK}/docker-compose.prod.yml" --env-file "${RUNTIME_ENV_FILE}" pull

  log "Starting qdrant"
  docker compose -f "${CURRENT_LINK}/docker-compose.prod.yml" --env-file "${RUNTIME_ENV_FILE}" up -d qdrant

  log "Running indexer"
  docker compose -f "${CURRENT_LINK}/docker-compose.prod.yml" --env-file "${RUNTIME_ENV_FILE}" run --rm indexer

  log "Starting api, ui, and proxy"
  docker compose -f "${CURRENT_LINK}/docker-compose.prod.yml" --env-file "${RUNTIME_ENV_FILE}" up -d api ui proxy

  log "Waiting for health checks"
  if ! wait_for_health; then
    log "Health checks failed after deploy"
    rollback || true
    exit 1
  fi

  log "Deployment succeeded for release ${RELEASE_ID}"
}

main "$@"

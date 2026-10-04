#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

install_compose_plugin() {
  local plugin_dir="/usr/local/libexec/docker/cli-plugins"
  local plugin_path="${plugin_dir}/docker-compose"

  log "Installing Docker Compose plugin"
  install -d -m 0755 "${plugin_dir}"
  curl -fsSL \
    "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
    -o "${plugin_path}"
  chmod 0755 "${plugin_path}"
  ln -sfn "${plugin_path}" /usr/local/bin/docker-compose
}

log "Installing Docker and deploy helpers"
dnf update -y
dnf install -y docker jq tar gzip unzip awscli
install_compose_plugin

log "Ensuring Docker and SSM agent are running"
systemctl enable --now docker
systemctl enable --now amazon-ssm-agent || true

log "Preparing runtime directories"
install -d -m 0755 /opt/medrag/app/releases
install -d -m 0755 /opt/medrag/data/qdrant
install -d -m 0755 /opt/medrag/data/medrag
install -d -m 0755 /opt/medrag/runtime

if id ec2-user >/dev/null 2>&1; then
  usermod -aG docker ec2-user || true
  chown -R ec2-user:ec2-user /opt/medrag
fi

docker --version
docker compose version
docker-compose --version
log "Bootstrap complete"

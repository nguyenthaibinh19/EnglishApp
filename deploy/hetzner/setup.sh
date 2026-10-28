#!/bin/bash
# Cài Language Guard trên Ubuntu 24.04 mới của Hetzner.
# Chạy từ thư mục gốc của source đã tải lên:
#   sudo bash deploy/hetzner/setup.sh ten-mien-cua-ban
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Chay bang sudo."
  exit 1
fi

DOMAIN="${1:-}"
if [[ -z "${DOMAIN}" || "${DOMAIN}" == *" "* ]]; then
  echo "Dung: sudo bash deploy/hetzner/setup.sh ten-mien-cua-ban"
  exit 1
fi

SRC="$(cd "$(dirname "$0")/../.." && pwd)"
APP_DIR="/opt/language-guard"
APP_USER="guard"
# Import closure of account_server.py. Sync modules are copied so the process
# can start with STUDY_SYNC_ENABLED unset; that flag must stay off in production.
FILES=(
  account_server.py
  account_store.py
  ai_teacher.py
  config.py
  languages.py
  listening.py
  listening_content.py
  reading_schema.py
  sync_http.py
  sync_store.py
  text_utils.py
  vocab_identity.py
  vocabulary_model.py
  ai/__init__.py
  ai/base.py
  ai/service.py
  ai/openai_provider.py
  sync_backup.py
  sync_alert.py
  requirements-server.txt
)

for name in "${FILES[@]}"; do
  if [[ "${name}" == *.py ]]; then
    if [[ ! -f "${SRC}/app/${name}" ]]; then
      echo "Thieu ${SRC}/app/${name}"
      exit 1
    fi
  elif [[ ! -f "${SRC}/${name}" ]]; then
    echo "Thieu ${SRC}/${name}"
    exit 1
  fi
done

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip curl debian-keyring debian-archive-keyring apt-transport-https ca-certificates gnupg ufw

if [[ ! -f /usr/share/keyrings/caddy-stable-archive-keyring.gpg ]]; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  chmod 644 /usr/share/keyrings/caddy-stable-archive-keyring.gpg
fi
if [[ ! -f /etc/apt/sources.list.d/caddy-stable.list ]]; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  apt-get update
fi
apt-get install -y caddy

if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  useradd --system --home "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
fi

mkdir -p "${APP_DIR}/deploy/hetzner" /var/backups/language-guard
for name in "${FILES[@]}"; do
  if [[ "${name}" == *.py ]]; then
    mkdir -p "${APP_DIR}/$(dirname "${name}")"
    cp "${SRC}/app/${name}" "${APP_DIR}/${name}"
  else
    cp "${SRC}/${name}" "${APP_DIR}/${name}"
  fi
done
cp "${SRC}/deploy/hetzner/backup_accounts.py" "${APP_DIR}/deploy/hetzner/backup_accounts.py"
# Copied for a later ops step. The daily timer still runs backup_accounts.py only.
cp "${SRC}/deploy/hetzner/backup_sync.py" "${APP_DIR}/deploy/hetzner/backup_sync.py"
# Sync timer units stay in the app tree. Do not copy them into systemd and do
# not enable them. Phase 18B.8 is the installation milestone.
cp "${SRC}/deploy/hetzner/language-guard-sync-backup.service" "${APP_DIR}/deploy/hetzner/language-guard-sync-backup.service"
cp "${SRC}/deploy/hetzner/language-guard-sync-backup.timer" "${APP_DIR}/deploy/hetzner/language-guard-sync-backup.timer"
cp "${SRC}/deploy/hetzner/language-guard.service" /etc/systemd/system/language-guard.service
cp "${SRC}/deploy/hetzner/language-guard-backup.service" /etc/systemd/system/language-guard-backup.service
cp "${SRC}/deploy/hetzner/language-guard-backup.timer" /etc/systemd/system/language-guard-backup.timer

if [[ ! -f "${APP_DIR}/.env" ]]; then
  if [[ -f "${SRC}/.env" ]]; then
    grep -E '^(OPENAI_API_KEY|OPENAI_MODEL)=' "${SRC}/.env" > "${APP_DIR}/.env" || true
  fi
fi
if ! grep -Eq '^OPENAI_API_KEY=.+' "${APP_DIR}/.env" 2>/dev/null \
  || grep -Eq '^OPENAI_API_KEY=sk-\.\.\.$' "${APP_DIR}/.env"; then
  cp "${SRC}/deploy/hetzner/server.env.example" "${APP_DIR}/.env"
  echo "Hay sua ${APP_DIR}/.env, dien OPENAI_API_KEY, roi chay lai lenh nay."
  chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}" /var/backups/language-guard
  chmod 600 "${APP_DIR}/.env"
  exit 1
fi
chmod 600 "${APP_DIR}/.env"

if [[ ! -x "${APP_DIR}/venv/bin/python" ]]; then
  python3 -m venv "${APP_DIR}/venv"
fi
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements-server.txt"

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}" /var/backups/language-guard

sed "s/TEN_MIEN/${DOMAIN}/g" "${SRC}/deploy/hetzner/Caddyfile" > /etc/caddy/Caddyfile

ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

systemctl daemon-reload
systemctl enable --now language-guard.service
systemctl enable --now language-guard-backup.timer
systemctl enable caddy
systemctl reload caddy || systemctl restart caddy

echo "Server noi bo: systemctl status language-guard --no-pager"
echo "Khi DNS da tro ${DOMAIN} ve may nay, mo: https://${DOMAIN}"

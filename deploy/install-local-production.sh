#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/tim/git/Daiy"
SERVICE_NAME="daiy.service"
CADDYFILE="/etc/caddy/Caddyfile"
CADDY_DROPIN_DIR="/etc/systemd/system/caddy.service.d"
ENV_DIR="/etc/daiy"
ENV_FILE="${ENV_DIR}/daiy.env"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo ${REPO_DIR}/deploy/install-local-production.sh" >&2
  exit 1
fi

install -d -m 0755 "${ENV_DIR}"
if [ ! -f "${ENV_FILE}" ]; then
  install -m 0644 "${REPO_DIR}/deploy/env/daiy.env" "${ENV_FILE}"
fi

install -m 0644 "${REPO_DIR}/deploy/systemd/daiy.service" "/etc/systemd/system/${SERVICE_NAME}"
install -m 0644 "${REPO_DIR}/deploy/systemd/flexdns-daiy.service" "/etc/systemd/system/flexdns-daiy.service"
install -m 0644 "${REPO_DIR}/deploy/systemd/flexdns-daiy.timer" "/etc/systemd/system/flexdns-daiy.timer"

install -d -m 0755 "${CADDY_DROPIN_DIR}"
install -m 0644 "${REPO_DIR}/deploy/systemd/caddy-daiy-env.conf" "${CADDY_DROPIN_DIR}/daiy-env.conf"

if ! grep -q "DAIY_PUBLIC_HOST" "${CADDYFILE}"; then
  cp "${CADDYFILE}" "${CADDYFILE}.bak.$(date +%Y%m%d-%H%M%S)"
  {
    printf "\n# Daiy Flask app\n"
    cat "${REPO_DIR}/deploy/caddy/daiy.caddy"
  } >> "${CADDYFILE}"
fi

systemctl daemon-reload
caddy validate --config "${CADDYFILE}" --adapter caddyfile
systemctl enable --now "${SERVICE_NAME}"
if [ -x /usr/local/sbin/update-flexdns-daiy ]; then
  systemctl enable --now flexdns-daiy.timer
else
  echo "FlexDNS timer not enabled: /usr/local/sbin/update-flexdns-daiy is missing or not executable"
fi
systemctl restart caddy

echo "Daiy installed. Current host: $(grep '^DAIY_PUBLIC_HOST=' "${ENV_FILE}" | cut -d= -f2-)"
echo "Check with: systemctl status ${SERVICE_NAME}"

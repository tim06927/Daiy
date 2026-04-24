#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo $0 <hostname>" >&2
  exit 1
fi

if [ "$#" -ne 1 ]; then
  echo "Usage: sudo $0 <hostname>" >&2
  echo "Example: sudo $0 snap-to-cart.daiy.de" >&2
  exit 1
fi

NEW_HOST="$1"
ENV_FILE="/etc/daiy/daiy.env"
FLEXDNS_ENV="/etc/flexdns-daiy.env"
FLEXDNS_SCRIPT="/usr/local/sbin/update-flexdns-daiy"
STATE_FILE="/var/lib/flexdns-daiy/last_ipv6"

if [[ ! "${NEW_HOST}" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "Invalid hostname: ${NEW_HOST}" >&2
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  echo "Missing ${ENV_FILE}. Run deploy/install-local-production.sh first." >&2
  exit 1
fi

OLD_HOST="$(grep -E '^DAIY_PUBLIC_HOST=' "${ENV_FILE}" | tail -n1 | cut -d= -f2- || true)"
if [ -z "${OLD_HOST}" ]; then
  OLD_HOST="app.daiy.de"
fi

sed -i "s/^DAIY_PUBLIC_HOST=.*/DAIY_PUBLIC_HOST=${NEW_HOST}/" "${ENV_FILE}"

if [ -f "${FLEXDNS_ENV}" ]; then
  sed -i "s/^FLEXDNS_HOSTNAME=.*/FLEXDNS_HOSTNAME=${NEW_HOST}/" "${FLEXDNS_ENV}"
fi

if [ -f "${FLEXDNS_SCRIPT}" ]; then
  sed -i "s/${OLD_HOST//./\\.}/${NEW_HOST}/g" "${FLEXDNS_SCRIPT}"
fi

rm -f "${STATE_FILE}"
systemctl start flexdns-daiy.service
systemctl restart caddy

echo "Daiy public host switched from ${OLD_HOST} to ${NEW_HOST}."
echo "Verify with: curl -I https://${NEW_HOST}/health"

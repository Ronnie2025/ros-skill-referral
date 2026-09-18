#!/usr/bin/env bash
# One-time Aliyun install for https://dbskill.site/referral/
# Run as root on the ECS host. Does not download or execute remote scripts.
set -Eeuo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run as root: sudo ./install-on-aliyun.sh" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }
command -v nginx >/dev/null || { echo "nginx is required" >&2; exit 1; }
command -v systemctl >/dev/null || { echo "systemctl is required" >&2; exit 1; }

install -d -m 0755 /usr/local/libexec/dbskill-referral/public
install -d -m 0755 /var/lib/dbskill-referral
install -m 0755 "$ROOT/referral_api.py" /usr/local/libexec/dbskill-referral/referral_api.py
install -m 0644 "$ROOT/public/index.html" /usr/local/libexec/dbskill-referral/public/index.html
install -m 0644 "$ROOT/dbskill-referral.service" /etc/systemd/system/dbskill-referral.service
install -d -m 0755 /etc/nginx/snippets
install -m 0644 "$ROOT/nginx-referral.location.conf" /etc/nginx/snippets/dbskill-referral.location.conf

id www-data >/dev/null 2>&1 || useradd --system --home /var/lib/dbskill-referral --shell /usr/sbin/nologin www-data
chown -R www-data:www-data /var/lib/dbskill-referral

LIVE_VHOST=/etc/nginx/sites-available/dbskill.site
DEPLOY_TEMPLATE=/usr/local/libexec/dbskill/nginx/dbskill.site.conf
[[ -f "$LIVE_VHOST" && -f "$DEPLOY_TEMPLATE" ]] || {
  echo "Expected dbskill.site live vhost and deploy template are required" >&2
  exit 1
}

BACKUP_ROOT="$(mktemp -d)"
cp -p "$LIVE_VHOST" "$BACKUP_ROOT/live.conf"
cp -p "$DEPLOY_TEMPLATE" "$BACKUP_ROOT/template.conf"
rollback() (
  set +e
  cp -p "$BACKUP_ROOT/live.conf" "$LIVE_VHOST"
  cp -p "$BACKUP_ROOT/template.conf" "$DEPLOY_TEMPLATE"
  nginx -t && systemctl reload nginx || true
)
trap 'rollback; rm -rf "$BACKUP_ROOT"' ERR
trap 'rm -rf "$BACKUP_ROOT"' EXIT

python3 "$ROOT/patch_nginx.py" "$LIVE_VHOST" "$ROOT/nginx-referral.location.conf"
python3 "$ROOT/patch_nginx.py" "$DEPLOY_TEMPLATE" "$ROOT/nginx-referral.location.conf"

nginx -t
systemctl daemon-reload
systemctl enable dbskill-referral
systemctl restart dbskill-referral
systemctl reload nginx

healthy=0
for attempt in 1 2 3 4 5; do
  if curl --fail --silent --max-time 2 http://127.0.0.1:8788/referral/health >/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done
[[ "$healthy" -eq 1 ]] || { echo "referral api failed its local health check" >&2; false; }
trap - ERR
echo "referral api is up on 127.0.0.1:8788"
echo "public page: https://dbskill.site/referral/"

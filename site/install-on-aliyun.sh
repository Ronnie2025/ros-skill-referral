#!/usr/bin/env bash
# One-time Aliyun install for https://dbskill.site/referral/
# Run as root on the ECS host. Does not download or execute remote scripts.
set -euo pipefail

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

patch_vhost() {
  local file="$1"
  [[ -e "$file" ]] || return 0
  file="$(readlink -f "$file")"
  if grep -q 'location ^~ /referral/' "$file"; then
    return 0
  fi
  python3 - "$file" "$ROOT/nginx-referral.location.conf" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
block = Path(sys.argv[2]).read_text(encoding="utf-8").rstrip() + "\n"
text = path.read_text(encoding="utf-8")
needle = "    location / {\n"
if needle in text:
    text = text.replace(needle, block + "\n" + needle, 1)
else:
    text = text.replace("\n}", "\n" + block + "\n}", 1)
path.write_text(text, encoding="utf-8")
PY
}

patch_vhost /etc/nginx/sites-available/dbskill.site
patch_vhost /usr/local/libexec/dbskill/nginx/dbskill.site.conf

nginx -t
systemctl daemon-reload
systemctl enable --now dbskill-referral
systemctl reload nginx

curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8788/referral/health >/dev/null
echo "referral api is up on 127.0.0.1:8788"
echo "public page: https://dbskill.site/referral/"

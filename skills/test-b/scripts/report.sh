#!/usr/bin/env bash
# Send one referral event. Never blocks the caller: network errors are ignored.
set -u

EVENT="${1:-}"
case "$EVENT" in
  setup_success|first_use_success|install_success) ;;
  *)
    echo "usage: report.sh setup_success|first_use_success|install_success" >&2
    exit 2
    ;;
esac

if [[ -n "${ROS_NO_TELEMETRY:-}" ]]; then
  echo "telemetry disabled"
  exit 0
fi

ENDPOINT="${ROS_REFERRAL_ENDPOINT:-https://dbskill.site/referral/e}"
TARGET_SKILL="test-b"
CACHE_DIR="${ROS_CLIP_CACHE:-$HOME/.cache/test-b}"
REF_FILE="${ROS_REFERRAL_FILE:-$HOME/.config/skill-referrals/test-b.json}"
if [[ ! -f "$REF_FILE" ]]; then
  echo "no referral consent"
  exit 0
fi
STAMP_DIR="$CACHE_DIR/reported"
mkdir -p "$CACHE_DIR" "$STAMP_DIR" 2>/dev/null || true

new_id() {
  if command -v uuidgen >/dev/null 2>&1; then
    uuidgen | tr 'A-Z' 'a-z'
    return
  fi
  python3 -c 'import uuid; print(uuid.uuid4())' 2>/dev/null && return
  date +%s%N
}

INSTALL_ID_FILE="$CACHE_DIR/install-id"
if [[ ! -s "$INSTALL_ID_FILE" ]]; then
  new_id > "$INSTALL_ID_FILE" 2>/dev/null || true
fi
INSTALL_ID="$(tr -d '[:space:]' < "$INSTALL_ID_FILE" 2>/dev/null || true)"
[[ -n "$INSTALL_ID" ]] || exit 0

STAMP_FILE="$STAMP_DIR/$EVENT"
if [[ -f "$STAMP_FILE" ]]; then
  echo "already reported $EVENT"
  exit 0
fi

REFERRER=""
SOURCE_SKILL=""
CAMPAIGN=""
if [[ -f "$REF_FILE" ]]; then
  eval "$(python3 - "$REF_FILE" <<'PY'
import json, sys
path = sys.argv[1]
try:
    data = json.load(open(path, encoding="utf-8"))
except Exception:
    data = {}
def emit(key):
    value = data.get(key, "")
    if not isinstance(value, str):
        value = ""
    safe = "".join(ch for ch in value if ch.isalnum() or ch in "._-")[:80]
    print(f"{key.upper()}='{safe}'")
emit("referrer")
emit("source_skill")
emit("campaign")
PY
)" || true
fi

if [[ -z "$REFERRER" || -z "$SOURCE_SKILL" ]]; then
  echo "no referral consent"
  exit 0
fi

EVENT_ID="$(new_id)"
PAYLOAD=$(printf '{"event":"%s","referrer":"%s","source_skill":"%s","target_skill":"%s","campaign":"%s","installation_id":"%s","event_id":"%s"}' \
  "$EVENT" "$REFERRER" "$SOURCE_SKILL" "$TARGET_SKILL" "$CAMPAIGN" "$INSTALL_ID" "$EVENT_ID")

send() {
  if command -v curl >/dev/null 2>&1; then
    if curl --fail -sS -m 3 -X POST "$ENDPOINT" \
      -H 'content-type: application/json' \
      --data "$PAYLOAD" >/dev/null; then
      return 0
    else
      curl_status=$?
      [[ "$curl_status" -eq 22 ]] && return "$curl_status"
    fi
  fi
  python3 - "$ENDPOINT" "$PAYLOAD" <<'PY'
import sys, urllib.request
req = urllib.request.Request(
    sys.argv[1],
    data=sys.argv[2].encode("utf-8"),
    headers={"content-type": "application/json"},
    method="POST",
)
urllib.request.urlopen(req, timeout=3).read()
PY
}

if send 2>/dev/null; then
  date -u +%FT%TZ > "$STAMP_FILE" 2>/dev/null || true
  echo "reported $EVENT"
else
  echo "report skipped" >&2
fi
exit 0

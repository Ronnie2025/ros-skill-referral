#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export HOME="$TMP/home"
mkdir -p "$HOME"
export ROS_NO_TELEMETRY=1
export ROS_CLIP_CACHE="$TMP/cache"
export ROS_REFERRAL_FILE="$TMP/ref.json"
chmod +x "$ROOT/skills/ros-clip-draft/scripts/report.sh"
chmod +x "$ROOT/skills/ros-clip-draft/scripts/first-run.sh"
chmod +x "$ROOT/skills/dbs-recommend-ros-clip/scripts/recommend.sh"

out="$("$ROOT/skills/ros-clip-draft/scripts/first-run.sh")"
[[ "$out" == *disabled* ]]

unset ROS_NO_TELEMETRY
export ROS_REFERRAL_ENDPOINT="http://127.0.0.1:9/referral/e"
out="$("$ROOT/skills/ros-clip-draft/scripts/report.sh" setup_success || true)"
[[ "$out" == *skipped* || "$out" == *reported* || -z "$out" ]]

mkdir -p "$HOME/.agents/skills/ros-clip-draft"
printf '%s\n' '---' 'name: ros-clip-draft' '---' > "$HOME/.agents/skills/ros-clip-draft/SKILL.md"
check="$("$ROOT/skills/dbs-recommend-ros-clip/scripts/recommend.sh" --check)"
[[ "$check" == already_installed* ]]
install_out="$("$ROOT/skills/dbs-recommend-ros-clip/scripts/recommend.sh" --install --referrer dontbesilent)"
[[ "$install_out" == already_installed* ]]

if grep -R -nE 'curl[^|#]*\|[[:space:]]*(bash|sh)|wget[^|#]*\|[[:space:]]*(bash|sh)' \
  "$ROOT/skills"/*/scripts "$ROOT/site"/*.sh "$ROOT/site"/*.py; then
  echo "remote script pipe found" >&2
  exit 1
fi

echo "script checks passed"

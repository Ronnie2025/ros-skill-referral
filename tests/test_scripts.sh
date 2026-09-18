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
out="$("$ROOT/skills/ros-clip-draft/scripts/report.sh" setup_success)"
[[ "$out" == *"no referral consent"* ]]
[[ ! -e "$ROS_CLIP_CACHE/reported/setup_success" ]]

printf '%s\n' '{"referrer":"dontbesilent","source_skill":"dbs-recommend-ros-clip","campaign":"test"}' > "$ROS_REFERRAL_FILE"
mkdir -p "$TMP/bin"
cat > "$TMP/bin/curl" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' called >> "$MOCK_CURL_CALLS"
exit "$MOCK_CURL_EXIT"
MOCK
chmod +x "$TMP/bin/curl"
export PATH="$TMP/bin:$PATH"
export MOCK_CURL_CALLS="$TMP/curl-calls"
export MOCK_CURL_EXIT=22
out="$("$ROOT/skills/ros-clip-draft/scripts/report.sh" setup_success 2>&1)"
[[ "$out" == *"report skipped"* ]]
[[ ! -e "$ROS_CLIP_CACHE/reported/setup_success" ]]
export MOCK_CURL_EXIT=0
out="$("$ROOT/skills/ros-clip-draft/scripts/report.sh" setup_success)"
[[ "$out" == *"reported setup_success"* ]]
[[ -f "$ROS_CLIP_CACHE/reported/setup_success" ]]
out="$("$ROOT/skills/ros-clip-draft/scripts/report.sh" setup_success)"
[[ "$out" == *"already reported"* ]]
[[ "$(wc -l < "$MOCK_CURL_CALLS")" -eq 2 ]]

mkdir -p "$HOME/.agents/skills/ros-clip-draft"
printf '%s\n' '---' 'name: ros-clip-draft' '---' > "$HOME/.agents/skills/ros-clip-draft/SKILL.md"
check="$("$ROOT/skills/dbs-recommend-ros-clip/scripts/recommend.sh" --check)"
[[ "$check" == already_installed* ]]
install_out="$("$ROOT/skills/dbs-recommend-ros-clip/scripts/recommend.sh" --install --referrer dontbesilent)"
[[ "$install_out" == already_installed* ]]
mkdir -p "$HOME/.config/skill-referrals"
printf '%s\n' '{"referrer":"dontbesilent"}' > "$HOME/.config/skill-referrals/ros-clip-draft.json"
export ROS_NO_TELEMETRY=1
install_out="$("$ROOT/skills/dbs-recommend-ros-clip/scripts/recommend.sh" --install)"
[[ "$install_out" == already_installed* ]]
[[ ! -e "$HOME/.config/skill-referrals/ros-clip-draft.json" ]]

if grep -R -nE 'curl[^|#]*\|[[:space:]]*(bash|sh)|wget[^|#]*\|[[:space:]]*(bash|sh)' \
  "$ROOT/skills"/*/scripts "$ROOT/site"/*.sh "$ROOT/site"/*.py; then
  echo "remote script pipe found" >&2
  exit 1
fi

echo "script checks passed"

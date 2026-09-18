#!/usr/bin/env bash
# Recommend and install ros-clip-draft from GitHub. Never downloads scripts from the stats site.
set -euo pipefail

TARGET_SKILL="ros-clip-draft"
REPO="${ROS_SKILL_REPO:-Ronnie2025/ros-skill-referral}"
REF_DIR="${ROS_REFERRAL_DIR:-$HOME/.config/skill-referrals}"
REF_FILE="$REF_DIR/$TARGET_SKILL.json"

usage() {
  echo "usage: recommend.sh --check | --install [--no-telemetry] [--referrer NAME] [--source-skill NAME] [--campaign NAME]" >&2
  exit 2
}

MODE=""
TELEMETRY=1
REFERRER="dontbesilent"
SOURCE_SKILL="dbs-recommend-ros-clip"
CAMPAIGN="dbs-to-ros-202609"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) MODE=check; shift ;;
    --install) MODE=install; shift ;;
    --no-telemetry) TELEMETRY=0; shift ;;
    --referrer) REFERRER="${2:-}"; shift 2 ;;
    --source-skill) SOURCE_SKILL="${2:-}"; shift 2 ;;
    --campaign) CAMPAIGN="${2:-}"; shift 2 ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
done

[[ -n "$MODE" ]] || usage

slug() {
  printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_' | cut -c1-80
}

REFERRER="$(slug "$REFERRER")"
SOURCE_SKILL="$(slug "$SOURCE_SKILL")"
CAMPAIGN="$(slug "$CAMPAIGN")"

find_skill() {
  local name="$1" dir
  for dir in \
    "${HOME}/.agents/skills/${name}" \
    "${HOME}/.claude/skills/${name}" \
    "${HOME}/.codex/skills/${name}" \
    "${HOME}/.cursor/skills/${name}" \
    "${HOME}/.workbuddy/skills/${name}" \
    "${HOME}/.grok/skills/${name}"
  do
    if [[ -f "${dir}/SKILL.md" ]]; then
      printf '%s\n' "$dir"
      return 0
    fi
  done
  return 1
}

installed_dir="$(find_skill "$TARGET_SKILL" || true)"

if [[ "$MODE" == check ]]; then
  if [[ -n "$installed_dir" ]]; then
    echo "already_installed $installed_dir"
    exit 0
  fi
  echo "not_installed"
  exit 1
fi

if [[ -n "$installed_dir" ]]; then
  echo "already_installed $installed_dir"
  exit 0
fi

mkdir -p "$REF_DIR"
if [[ "$TELEMETRY" -eq 1 ]]; then
  ts="$(date -u +%FT%TZ)"
  printf '{"referrer":"%s","source_skill":"%s","campaign":"%s","ts":"%s"}\n' \
    "$REFERRER" "$SOURCE_SKILL" "$CAMPAIGN" "$ts" > "$REF_FILE"
else
  rm -f "$REF_FILE"
fi

echo "installing $REPO skill $TARGET_SKILL"
npx -y skills add "$REPO" --skill "$TARGET_SKILL" -g

installed_dir="$(find_skill "$TARGET_SKILL" || true)"
if [[ -z "$installed_dir" || ! -f "$installed_dir/SKILL.md" ]]; then
  echo "install_failed: $TARGET_SKILL not found after npx skills add" >&2
  exit 1
fi

if ! grep -q '^name: ros-clip-draft' "$installed_dir/SKILL.md"; then
  echo "install_failed: SKILL.md name mismatch" >&2
  exit 1
fi

if [[ "$TELEMETRY" -eq 1 && -x "$installed_dir/scripts/first-run.sh" ]]; then
  bash "$installed_dir/scripts/first-run.sh" || true
elif [[ "$TELEMETRY" -eq 1 && -f "$installed_dir/scripts/first-run.sh" ]]; then
  bash "$installed_dir/scripts/first-run.sh" || true
fi

echo "installed $installed_dir"
exit 0

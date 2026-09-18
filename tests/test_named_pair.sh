#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export HOME="$TMP/home"
export TEST_FIRST_RUN_LOG="$TMP/first-run.log"
export TEST_NPX_LOG="$TMP/npx.log"
mkdir -p "$HOME" "$TMP/bin"
cat > "$TMP/bin/npx" <<'MOCK'
#!/usr/bin/env bash
[[ "$1" == -y && "$2" == skills && "$3" == add ]] || exit 90
# Without the installer's own yes flag this fixture models an unanswered prompt.
installer_yes=0
for arg in "${@:4}"; do
  [[ "$arg" == -y || "$arg" == --yes ]] && installer_yes=1
done
[[ "$installer_yes" -eq 1 ]] || exit 91
printf '%s\n' called >> "$TEST_NPX_LOG"
target="$HOME/.agents/skills/test-b"
mkdir -p "$target/scripts"
printf '%s\n' '---' 'name: test-b' '---' > "$target/SKILL.md"
cat > "$target/scripts/first-run.sh" <<'FIRST_RUN'
#!/usr/bin/env bash
printf '%s\n' called >> "$TEST_FIRST_RUN_LOG"
FIRST_RUN
chmod +x "$target/scripts/first-run.sh"
MOCK
chmod +x "$TMP/bin/npx"
export PATH="$TMP/bin:$PATH"

script="$ROOT/skills/test-a/scripts/recommend.sh"
if "$script" --check > "$TMP/check.out"; then
  echo "test-B unexpectedly installed" >&2
  exit 1
fi
grep -q '^not_installed$' "$TMP/check.out"

"$script" --install > "$TMP/install.out"
grep -q '^installed ' "$TMP/install.out"
grep -q '"source_skill":"test-a"' "$HOME/.config/skill-referrals/test-b.json"
[[ "$(wc -l < "$TEST_NPX_LOG")" -eq 1 ]]
[[ "$(wc -l < "$TEST_FIRST_RUN_LOG")" -eq 1 ]]

"$script" --install --no-telemetry > "$TMP/again.out"
grep -q '^already_installed ' "$TMP/again.out"
[[ ! -e "$HOME/.config/skill-referrals/test-b.json" ]]
[[ "$(wc -l < "$TEST_NPX_LOG")" -eq 1 ]]

# A fresh opt-out install still proceeds, without invoking the reporting hook.
mv "$HOME/.agents/skills/test-b" "$TMP/installed-snapshot"
"$script" --install --no-telemetry > "$TMP/optout.out"
grep -q '^installed ' "$TMP/optout.out"
[[ ! -e "$HOME/.config/skill-referrals/test-b.json" ]]
[[ "$(wc -l < "$TEST_NPX_LOG")" -eq 2 ]]
[[ "$(wc -l < "$TEST_FIRST_RUN_LOG")" -eq 1 ]]
echo "named pair checks passed"

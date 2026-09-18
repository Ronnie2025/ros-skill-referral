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
echo "named pair checks passed"

#!/usr/bin/env bash
# Mark this environment as set up and report once. Safe to call repeatedly.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$ROOT/report.sh" setup_success
exit 0

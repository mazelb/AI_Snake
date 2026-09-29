#!/usr/bin/env bash
# Validate every spec artifact in the repo. Used by /spec-check and CI.
set -uo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORST=0
run() { python3 "$S/$1" $2 2>/dev/null; c=$?; [ $c -gt $WORST ] && WORST=$c; return 0; }
shopt -s nullglob
for f in specs/*/prd.md;        do run validate_prd.py "$f"; done
for f in specs/*/plan.md;       do run validate_plan.py "$f"; done
for f in specs/*/acceptance.md; do run validate_acceptance.py "$f"; done
# Only if the optional delivery layer is attached.
if [ -f "$S/validate_delivery.py" ]; then
  for f in specs/*/delivery.md; do run validate_delivery.py "$f"; done
fi
python3 "$S/coverage.py" 2>/dev/null
exit $WORST

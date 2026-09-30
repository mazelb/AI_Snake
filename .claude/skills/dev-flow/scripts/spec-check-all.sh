#!/usr/bin/env bash
# Validate spec artifacts. Used by /spec-check and CI.
#
#   spec-check-all.sh                every artifact in the repo, then coverage
#   spec-check-all.sh PATH           one prd.md, plan.md or acceptance.md
#   spec-check-all.sh ISSUE          the artifacts in specs/ISSUE-*/, then its coverage
#
# An empty argument means none, so /spec-check can pass "$ARGUMENTS" as it is: the
# choice is made here because a /spec-check preprocessing line holding an `if` is
# refused outside auto mode (build item 29). Exits with the worst validator code.
set -uo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARG="${1:-}"
WORST=0
run() { python3 "$S/$1" $2 2>/dev/null; c=$?; [ $c -gt $WORST ] && WORST=$c; return 0; }
by_name() {
  case "$1" in
    *prd.md)        run validate_prd.py "$1" ;;
    *plan.md)       run validate_plan.py "$1" ;;
    *acceptance.md) run validate_acceptance.py "$1" ;;
  esac
}
shopt -s nullglob
if [ -z "$ARG" ]; then
  for f in specs/*/prd.md;        do run validate_prd.py "$f"; done
  for f in specs/*/plan.md;       do run validate_plan.py "$f"; done
  for f in specs/*/acceptance.md; do run validate_acceptance.py "$f"; done
  # Only if the optional delivery layer is attached.
  if [ -f "$S/validate_delivery.py" ]; then
    for f in specs/*/delivery.md; do run validate_delivery.py "$f"; done
  fi
  python3 "$S/coverage.py" 2>/dev/null
elif [ -f "$ARG" ]; then
  by_name "$ARG"
else
  dirs=(specs/"$ARG"-*/)
  # With nullglob, no match would hand coverage.py no directory, and it would
  # report every spec instead of none.
  if [ "${#dirs[@]}" = 0 ]; then
    echo "No file '$ARG' and no spec directory specs/$ARG-*/."
    exit 1
  fi
  for f in specs/"$ARG"-*/prd.md specs/"$ARG"-*/plan.md specs/"$ARG"-*/acceptance.md; do
    by_name "$f"
  done
  python3 "$S/coverage.py" "${dirs[@]}" 2>&1
fi
exit $WORST

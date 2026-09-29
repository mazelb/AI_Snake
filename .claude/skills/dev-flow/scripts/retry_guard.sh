#!/usr/bin/env bash
# Retry counter for /verify. Uncapped retry loops on a coding harness burn money
# and fail silently; two attempts is where the marginal value of another
# autonomous try stops justifying the spend.
set -uo pipefail

ISSUE="${1:?usage: retry_guard.sh <issue> [status|bump|reset]}"
ACTION="${2:-status}"
MAX=2
DIR=".claude/spec-pipeline/retries"
FILE="$DIR/$ISSUE"
mkdir -p "$DIR"
COUNT=$(cat "$FILE" 2>/dev/null || echo 0)

case "$ACTION" in
  status)
    echo "attempt $COUNT of $MAX"
    [ "$COUNT" -ge "$MAX" ] && echo "EXHAUSTED — hand back to the human, do not retry" && exit 1
    exit 0 ;;
  bump)
    COUNT=$((COUNT + 1)); echo "$COUNT" > "$FILE"
    echo "attempt $COUNT of $MAX"
    [ "$COUNT" -ge "$MAX" ] && echo "EXHAUSTED — hand back to the human, do not retry" && exit 1
    exit 0 ;;
  reset)
    rm -f "$FILE"; echo "retry counter reset for issue $ISSUE"; exit 0 ;;
  *)
    echo "unknown action: $ACTION" >&2; exit 64 ;;
esac
